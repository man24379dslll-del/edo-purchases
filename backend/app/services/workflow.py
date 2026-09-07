"""
Маршрут согласования договора — определяется АВТОМАТИЧЕСКИ при создании
(по категории, типу и сумме), а не решением Директора по ходу дела:

  Уровень 1 (Юрист → Бухгалтер → Директор, по очереди, все трое):
    - категория "Товар/производство", "Аренда имущества" или
      "Специализированные услуги и схемы" — независимо от суммы;
    - ЛИБО разовая закупка на сумму свыше 500 000 ₽.

  Уровень 2 (только Директор):
    - категория "Прочие услуги", "Ремонтные работы", "Прочее" — независимо от суммы;
    - ЛИБО разовая закупка на сумму от 100 000 до 500 000 ₽ (и ниже 100 000 — тоже,
      как безопасный минимум, если сумма не уточнена).

  Отклонить может любой согласующий на своём активном этапе — договор
  сразу переходит в "Отклонено", маршрут дальше не идёт.
"""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from app import models

STATUS_PENDING = "На согласовании"
STATUS_APPROVED = "Согласовано"
STATUS_REJECTED = "Отклонено"

CATEGORIES = [
    "Товар/производство", "Аренда имущества", "Специализированные услуги и схемы",
    "Прочие услуги", "Ремонтные работы", "Прочее",
]
CONTRACT_TYPES = ["Системный", "Разовая закупка"]

TIER1_CATEGORIES = {"Товар/производство", "Аренда имущества", "Специализированные услуги и схемы"}
ONE_OFF_TIER1_THRESHOLD = Decimal("500000")
ONE_OFF_TIER2_MIN = Decimal("100000")

TIER1_CHAIN = ["Юрист", "Бухгалтер", "Директор"]
TIER2_CHAIN = ["Директор"]


def determine_tier(category: str, contract_type: str, amount) -> int:
    """
    Возвращает 1 или 2 — уровень согласования. amount может быть None
    (для длительных договоров без известной итоговой цены на момент создания).
    """
    if category in TIER1_CATEGORIES:
        return 1
    if contract_type == "Разовая закупка" and amount is not None and amount > ONE_OFF_TIER1_THRESHOLD:
        return 1
    return 2


def chain_for_tier(tier: int) -> list[str]:
    return TIER1_CHAIN if tier == 1 else TIER2_CHAIN


def gen_id(db: Session, prefix: str) -> str:
    """
    Человекочитаемый ID вида ДОГ-2026-000123. Атомарность обеспечивается
    блокировкой строки счётчика (SELECT ... FOR UPDATE) — портируемо между
    Postgres/Supabase (прод) и SQLite (тесты), без дублей при параллельных
    запросах на создание документов.
    """
    counter = db.query(models.IdCounter).filter(models.IdCounter.name == "global").with_for_update().first()
    if not counter:
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


def start_approval(db: Session, contract_id: str, tier: int):
    """Создаёт всю цепочку согласования сразу (по уровню), первый этап — активный."""
    chain = chain_for_tier(tier)
    for stage, role in enumerate(chain):
        db.add(models.Approval(
            approval_id=gen_id(db, "SOG"), contract_id=contract_id,
            stage=stage, approver_role=role, decision="Ожидает",
            state="active" if stage == 0 else "pending",
        ))
    db.flush()


def get_approval_trail(db: Session, contract_id: str):
    return db.query(models.Approval).filter(
        models.Approval.contract_id == contract_id,
    ).order_by(models.Approval.stage.asc()).all()


def pending_for_role(db: Session, role: str):
    return db.query(models.Approval).filter(
        models.Approval.approver_role == role,
        models.Approval.state == "active",
    ).all()


def decide(db: Session, contract_id: str, role: str, email: str, decision: str, comment: str = ""):
    """
    Обрабатывает решение по договору: продвигает по заранее построенной
    цепочке (см. start_approval). Бросает ValueError с понятным сообщением,
    если для роли нет активного этапа.
    """
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).with_for_update().first()
    if not contract:
        raise ValueError("Договор не найден.")

    approval = db.query(models.Approval).filter(
        models.Approval.contract_id == contract_id,
        models.Approval.approver_role == role,
        models.Approval.state == "active",
    ).with_for_update().first()
    if not approval:
        raise ValueError("Активный этап согласования для вашей роли не найден, либо решение уже принято.")

    approval.decision = decision
    approval.decision_date = datetime.now(timezone.utc)
    approval.comment = comment
    approval.approver_email = email
    approval.state = "done"

    if decision == STATUS_REJECTED:
        contract.status = STATUS_REJECTED
        add_log(db, email, role, "Отклонил", "contract", contract_id, comment)
        db.flush()
        return {"status": STATUS_REJECTED, "finished": True}

    if decision != STATUS_APPROVED:
        raise ValueError("Решение должно быть 'Согласовано' или 'Отклонено'.")

    add_log(db, email, role, "Согласовал", "contract", contract_id, comment)

    next_stage = db.query(models.Approval).filter(
        models.Approval.contract_id == contract_id,
        models.Approval.stage == approval.stage + 1,
    ).first()

    if not next_stage:
        contract.status = STATUS_APPROVED
        db.flush()
        return {"status": STATUS_APPROVED, "finished": True}

    next_stage.state = "active"
    db.flush()
    return {"status": STATUS_PENDING, "finished": False}


# ══════════════════════════════════════════════════════════════
# УДАЛЕНИЕ ДОГОВОРА
# ══════════════════════════════════════════════════════════════

def assert_deletable(db: Session, contract, user_email: str, user_role: str):
    """
    Удалить договор можно только инициатору, и только пока статус
    "На согласовании" и ПО НЕМУ ЕЩЁ НЕТ НИ ОДНОГО РЕШЕНИЯ.
    """
    if contract.initiator_email != user_email and user_role != "Админ":
        raise ValueError("Удалить может только инициатор.")
    if contract.status != STATUS_PENDING:
        raise ValueError("Удалить можно только договор со статусом «На согласовании».")
    has_decision = db.query(models.Approval).filter(
        models.Approval.contract_id == contract.id,
        models.Approval.decision != "Ожидает",
    ).first()
    if has_decision:
        raise ValueError("Удалить нельзя: по договору уже есть хотя бы одно решение согласования.")


def delete_contract(db: Session, contract, user_email: str, user_role: str):
    db.query(models.Approval).filter(models.Approval.contract_id == contract.id).delete(synchronize_session=False)
    db.query(models.PaymentScheduleItem).filter(
        models.PaymentScheduleItem.contract_id == contract.id).delete(synchronize_session=False)
    add_log(db, user_email, user_role, "Удалил", "contract", contract.id, contract.subject)
    db.delete(contract)


# ══════════════════════════════════════════════════════════════
# ХРАНИЛИЩЕ ДОКУМЕНТОВ
# ══════════════════════════════════════════════════════════════

DOC_TYPES = ["Договор", "Доп. соглашение", "Приложение", "Скан подписанного", "Прочее"]


def link_document(db: Session, file_url: str, entity_id: str, entity_subject: str, doc_type: str = "Договор"):
    """
    Привязывает ранее загруженный файл к договору (см. files_router.upload_file).
    Ищем по stored_filename (последний сегмент URL), а не по точному совпадению
    всей ссылки — так привязка не ломается, даже если абсолютный/относительный
    адрес или домен backend отличаются от того, что был сохранён при загрузке.
    """
    if not file_url:
        return
    stored_filename = file_url.rstrip("/").split("/")[-1]
    doc = db.query(models.Document).filter(models.Document.stored_filename == stored_filename).first()
    if doc:
        doc.entity_type = "contract"
        doc.entity_id = entity_id
        doc.entity_subject = entity_subject
        doc.doc_type = doc_type
