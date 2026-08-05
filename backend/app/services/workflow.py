"""
Маршруты согласования — портировано 1:1 из исходного Code.gs (Google Apps Script),
дополнено SLA/эскалацией и делегированием (замещением согласующего).

ДОГОВОР:
  Закупщик создаёт
  → Юрист + Маркетинг (параллельно, Маркетинг опционален — needs_marketing)
  → Фин. директор
  → Бухгалтер (финал — вносит в реестр)

ЗАКУПКА:
  Инициатор создаёт
  → Маркетинг
  → Директор
  → Закупщик (финал — исполняет)

ДОП. СОГЛАШЕНИЕ: та же цепочка, что и договор.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app import models
from app.services import notifications

CONTRACT_CHAIN = [
    ["Юрист", "Маркетинг"],  # параллельно
    "Фин. директор",
    "Бухгалтер",
]

PURCHASE_CHAIN = ["Маркетинг", "Директор", "Закупщик"]

AMENDMENT_CHAIN = [
    ["Юрист", "Маркетинг"],
    "Фин. директор",
    "Бухгалтер",
]

STATUS_PENDING = "На согласовании"
STATUS_APPROVED = "Согласовано"
STATUS_REJECTED = "Отклонено"

CHAINS = {
    "contract": CONTRACT_CHAIN,
    "amendment": AMENDMENT_CHAIN,
    "purchase": PURCHASE_CHAIN,
}

STATUS_MODEL = {
    "contract": models.Contract,
    "amendment": models.Amendment,
    "purchase": models.Purchase,
}

# SLA в часах на роль — портировано из DEFAULT_SLA в исходном Code.gs.
# Роль, на которую SLA не задан явно, получает дефолт (48ч).
DEFAULT_SLA_HOURS = {
    "Юрист": 48, "Маркетинг": 48, "Фин. директор": 24,
    "Бухгалтер": 24, "Директор": 24, "Закупщик": 48, "Склад": 48,
}
FALLBACK_SLA_HOURS = 48

# Роль, которой эскалируется просроченный этап (директор видит всё, что "горит").
ESCALATION_ROLE = "Директор"


def gen_id(db: Session, prefix: str) -> str:
    """
    Человекочитаемый ID вида ДОГ-2026-000123. Атомарность обеспечивается
    блокировкой строки счётчика (SELECT ... FOR UPDATE) — портируемо между
    Postgres/Supabase (прод) и SQLite (тесты), без дублей при параллельных
    запросах на создание документов.
    """
    counter = db.query(models.IdCounter).filter(models.IdCounter.name == "global").with_for_update().first()
    if not counter:
        # На случай если сид из миграции не применился — создаём на лету.
        counter = models.IdCounter(name="global", value=0)
        db.add(counter)
        db.flush()
        counter = db.query(models.IdCounter).filter(models.IdCounter.name == "global").with_for_update().first()
    counter.value += 1
    db.flush()
    return f"{prefix}-{datetime.now().year}-{counter.value:06d}"


def add_log(db: Session, email: str, role: str, action: str, entity_type: str, entity_id: str, comment: str = ""):
    db.add(models.LogEntry(
        user_email=email or "system", role=role or "", action=action,
        entity_type=entity_type, entity_id=entity_id, comment=comment or "",
    ))


def _chain_for(entity_type: str, needs_marketing: bool):
    chain = CHAINS[entity_type]
    result = []
    for stage in chain:
        if isinstance(stage, list):
            roles = [r for r in stage if r != "Маркетинг" or needs_marketing]
            if roles:
                result.append(roles)
        else:
            result.append([stage])
    return result


def _sla_deadline(role: str) -> datetime:
    hours = DEFAULT_SLA_HOURS.get(role, FALLBACK_SLA_HOURS)
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _activate(approvals: list[models.Approval]):
    """Помечает этап активным и проставляет дедлайн по SLA роли."""
    now = datetime.now(timezone.utc)
    for a in approvals:
        a.state = "active"
        a.activated_at = now
        a.deadline = _sla_deadline(a.approver_role)


def start_approval(db: Session, entity_type: str, entity_id: str, needs_marketing: bool = False,
                    revision: int = 1, subject: str = ""):
    """Создаёт цепочку согласований для сущности (или нового раунда после доработки)."""
    chain = _chain_for(entity_type, needs_marketing)
    now = datetime.now(timezone.utc)
    first_stage_approvals = []
    for stage_idx, roles in enumerate(chain):
        for role in roles:
            a = models.Approval(
                approval_id=gen_id(db, "SOG"),
                entity_type=entity_type,
                entity_id=entity_id,
                stage=stage_idx,
                approver_role=role,
                decision="Ожидает",
                state="active" if stage_idx == 0 else "pending",
                revision=revision,
            )
            db.add(a)
            if stage_idx == 0:
                first_stage_approvals.append(a)
    db.flush()
    for a in first_stage_approvals:
        a.activated_at = now
        a.deadline = _sla_deadline(a.approver_role)
        notifications.notify_new_stage(db, entity_type, entity_id, a.approver_role, subject)
    db.flush()


def get_active_stage_approvals(db: Session, entity_type: str, entity_id: str):
    return db.query(models.Approval).filter(
        models.Approval.entity_type == entity_type,
        models.Approval.entity_id == entity_id,
        models.Approval.state == "active",
    ).all()


def decide(db: Session, entity_type: str, entity_id: str, approver_role: str,
           approver_email: str, decision: str, comment: str = ""):
    """
    Обрабатывает решение по этапу. decision: 'Согласовано' | 'Отклонено'.
    Если отклонено — вся сущность переходит в статус "Отклонено".
    Если это был последний согласующий на этапе — открывается следующий этап
    (либо, если этапов больше нет, сущность переходит в "Согласовано").

    ВАЖНО: строка сущности блокируется через SELECT ... FOR UPDATE на время
    транзакции. Это сериализует все decide()-вызовы по одной и той же сущности —
    без этого два параллельных согласующих на одном этапе могли бы оба увидеть
    "остались другие активные" = False и одновременно открыть следующий этап
    дважды, либо наоборот — не открыть его вовсе.
    """
    model = STATUS_MODEL[entity_type]
    entity = db.query(model).filter(model.id == entity_id).with_for_update().first()
    if not entity:
        raise ValueError("Сущность не найдена.")

    # Пока держим блокировку сущности, дальнейшие SELECT/UPDATE по approvals
    # этой же сущности гарантированно не пересекутся с параллельным decide().
    approval = db.query(models.Approval).filter(
        models.Approval.entity_type == entity_type,
        models.Approval.entity_id == entity_id,
        models.Approval.approver_role == approver_role,
        models.Approval.state == "active",
    ).with_for_update().first()
    if not approval:
        raise ValueError("Активный этап согласования для вашей роли не найден, либо решение уже принято.")

    approval.decision = decision
    approval.decision_date = datetime.now(timezone.utc)
    approval.comment = comment
    approval.approver_email = approver_email
    approval.state = "done"

    if decision == STATUS_REJECTED:
        entity.status = STATUS_REJECTED
        # закрываем остальные незавершённые этапы
        db.query(models.Approval).filter(
            models.Approval.entity_type == entity_type,
            models.Approval.entity_id == entity_id,
            models.Approval.state.in_(["active", "pending"]),
        ).update({"state": "skipped"}, synchronize_session=False)
        add_log(db, approver_email, approver_role, "Отклонил", entity_type, entity_id, comment)
        db.flush()
        return {"status": STATUS_REJECTED, "finished": True}

    # проверяем, остались ли ещё активные (не решённые) согласующие на этом же этапе
    remaining_on_stage = db.query(models.Approval).filter(
        models.Approval.entity_type == entity_type,
        models.Approval.entity_id == entity_id,
        models.Approval.stage == approval.stage,
        models.Approval.state == "active",
    ).count()

    add_log(db, approver_email, approver_role, "Согласовал", entity_type, entity_id, comment)

    if remaining_on_stage > 0:
        db.flush()
        return {"status": STATUS_PENDING, "finished": False}

    # этап полностью пройден — открываем следующий
    next_stage = approval.stage + 1
    next_approvals = db.query(models.Approval).filter(
        models.Approval.entity_type == entity_type,
        models.Approval.entity_id == entity_id,
        models.Approval.stage == next_stage,
    ).all()

    if not next_approvals:
        entity.status = STATUS_APPROVED
        db.flush()
        return {"status": STATUS_APPROVED, "finished": True}

    _activate(next_approvals)
    db.flush()
    for a in next_approvals:
        notifications.notify_new_stage(db, entity_type, entity_id, a.approver_role, entity.subject)
    return {"status": STATUS_PENDING, "finished": False}


def get_approval_trail(db: Session, entity_type: str, entity_id: str, revision: int = None):
    """
    Маршрут согласования. По умолчанию возвращает только последний раунд
    (revision) — после доработки отклонённого документа старые раунды не
    перемешиваются с текущим, но остаются в БД для полной истории.
    """
    if revision is None:
        latest = db.query(models.Approval.revision).filter(
            models.Approval.entity_type == entity_type,
            models.Approval.entity_id == entity_id,
        ).order_by(models.Approval.revision.desc()).first()
        revision = latest[0] if latest else 1
    rows = db.query(models.Approval).filter(
        models.Approval.entity_type == entity_type,
        models.Approval.entity_id == entity_id,
        models.Approval.revision == revision,
    ).order_by(models.Approval.stage.asc()).all()
    return rows


def pending_for_role(db: Session, entity_type: str, role: str):
    """Список этапов, ожидающих решения от указанной роли (без учёта делегирования)."""
    return db.query(models.Approval).filter(
        models.Approval.entity_type == entity_type,
        models.Approval.approver_role == role,
        models.Approval.state == "active",
    ).all()


# ══════════════════════════════════════════════════════════════
# ДЕЛЕГИРОВАНИЕ
# ══════════════════════════════════════════════════════════════

def get_effective_roles(db: Session, user_email: str, user_role: str) -> set[str]:
    """
    Роли, от имени которых пользователь сейчас может принимать решения:
    своя роль + роли всех, кого он замещает по активным делегированиям.
    """
    now = datetime.now(timezone.utc)
    roles = {user_role}
    delegations = db.query(models.Delegation).filter(
        models.Delegation.delegate_email == user_email,
        models.Delegation.starts_at <= now,
        models.Delegation.ends_at >= now,
    ).all()
    for d in delegations:
        roles.add(d.delegator_role)
    return roles


def pending_for_user(db: Session, entity_type: str, user_email: str, user_role: str):
    """Как pending_for_role, но с учётом делегирования (для 'Мои согласования')."""
    roles = get_effective_roles(db, user_email, user_role)
    return db.query(models.Approval).filter(
        models.Approval.entity_type == entity_type,
        models.Approval.approver_role.in_(roles),
        models.Approval.state == "active",
    ).all()


def resolve_approver_role(db: Session, entity_type: str, entity_id: str, user_email: str, user_role: str) -> str:
    """
    Находит, под какой ролью пользователь может принять решение по конкретному
    документу прямо сейчас (либо своя роль, либо роль того, кого он замещает).
    Бросает ValueError, если подходящего активного этапа нет.
    """
    roles = get_effective_roles(db, user_email, user_role)
    approval = db.query(models.Approval).filter(
        models.Approval.entity_type == entity_type,
        models.Approval.entity_id == entity_id,
        models.Approval.approver_role.in_(roles),
        models.Approval.state == "active",
    ).first()
    if not approval:
        raise ValueError("Активный этап согласования для вас не найден, либо решение уже принято.")
    return approval.approver_role


# ══════════════════════════════════════════════════════════════
# SLA / ЭСКАЛАЦИЯ
# ══════════════════════════════════════════════════════════════

def check_overdue(db: Session):
    """
    Находит активные этапы с истёкшим дедлайном, ещё не эскалированные,
    помечает их escalated=True и пишет в лог запись об эскалации директору.
    Предназначено для вызова по расписанию (cron/APScheduler) — см. README.
    Возвращает список эскалированных этапов (для рассылки уведомлений).
    """
    now = datetime.now(timezone.utc)
    overdue = db.query(models.Approval).filter(
        models.Approval.state == "active",
        models.Approval.escalated.is_(False),
        models.Approval.deadline.isnot(None),
        models.Approval.deadline < now,
    ).all()

    escalated = []
    for a in overdue:
        a.escalated = True
        add_log(
            db, "system", ESCALATION_ROLE, "Просрочен SLA, эскалировано",
            a.entity_type, a.entity_id,
            f"Этап «{a.approver_role}» просрочен (дедлайн {a.deadline.strftime('%d.%m.%Y %H:%M')})",
        )
        notifications.notify_escalation(db, a.entity_type, a.entity_id, a.approver_role,
                                         a.deadline.strftime("%d.%m.%Y %H:%M"))
        escalated.append(a)
    db.flush()
    return escalated


# ══════════════════════════════════════════════════════════════
# ДОРАБОТКА ОТКЛОНЁННОГО ДОКУМЕНТА
# ══════════════════════════════════════════════════════════════

def begin_new_round(db: Session, entity, entity_type: str, needs_marketing: bool = False) -> int:
    """
    Открывает новый раунд согласования для уже существующей (ранее отклонённой)
    сущности: увеличивает revision, сбрасывает статус в "На согласовании" и
    создаёт свежую цепочку approvals с этим revision. Старые approvals (все
    предыдущие раунды) остаются в БД нетронутыми — это полная история.
    Вызывающая сторона должна была загрузить entity через with_for_update().
    """
    entity.revision = (entity.revision or 1) + 1
    entity.status = STATUS_PENDING
    start_approval(db, entity_type, entity.id, needs_marketing=needs_marketing,
                    revision=entity.revision, subject=entity.subject)
    return entity.revision
