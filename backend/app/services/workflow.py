"""
Маршрут согласования договора — динамический (зависит от решения Директора):

  Инициатор создаёт → Директор рассматривает.
    ├─ Директор жмёт "Стандартный" → договор сразу Согласован (финал).
    └─ Директор жмёт "Отправить Юристу и Бухгалтеру" →
         Юрист согласовывает → Бухгалтер согласовывает →
         Директор ставит финальную подпись → Согласован.

  Отклонить может любой согласующий на своём активном этапе — договор
  сразу переходит в "Отклонено", маршрут дальше не идёт.
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app import models

STATUS_PENDING = "На согласовании"
STATUS_APPROVED = "Согласовано"
STATUS_REJECTED = "Отклонено"

STAGE_DIRECTOR_REVIEW = 0
STAGE_LAWYER = 1
STAGE_ACCOUNTANT = 2
STAGE_DIRECTOR_FINAL = 3


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


def start_approval(db: Session, contract_id: str):
    """Создаёт первый этап (Директор рассматривает) сразу активным."""
    db.add(models.Approval(
        approval_id=gen_id(db, "SOG"), contract_id=contract_id,
        stage=STAGE_DIRECTOR_REVIEW, approver_role="Директор",
        decision="Ожидает", state="active",
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


def decide(db: Session, contract_id: str, role: str, email: str, decision: str,
           comment: str = "", standard: bool = None):
    """
    Обрабатывает решение по договору. Бросает ValueError с понятным
    сообщением при некорректном запросе (нет активного этапа для роли,
    не указан standard на этапе Директора и т.п.).
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

    # ── Этап 0: решение Директора при первом рассмотрении ──
    if approval.stage == STAGE_DIRECTOR_REVIEW:
        if standard is None:
            raise ValueError("Укажите: 'Стандартный' договор, или отправить Юристу и Бухгалтеру.")
        contract.is_standard = standard
        if standard:
            contract.status = STATUS_APPROVED
            add_log(db, email, role, "Согласовал как стандартный", "contract", contract_id, comment)
            db.flush()
            return {"status": STATUS_APPROVED, "finished": True}
        else:
            db.add(models.Approval(
                approval_id=gen_id(db, "SOG"), contract_id=contract_id,
                stage=STAGE_LAWYER, approver_role="Юрист", decision="Ожидает", state="active",
            ))
            add_log(db, email, role, "Отправил на Юриста и Бухгалтера", "contract", contract_id, comment)
            db.flush()
            return {"status": STATUS_PENDING, "finished": False}

    # ── Этап 1: Юрист согласовал — открываем Бухгалтера ──
    if approval.stage == STAGE_LAWYER:
        db.add(models.Approval(
            approval_id=gen_id(db, "SOG"), contract_id=contract_id,
            stage=STAGE_ACCOUNTANT, approver_role="Бухгалтер", decision="Ожидает", state="active",
        ))
        add_log(db, email, role, "Согласовал", "contract", contract_id, comment)
        db.flush()
        return {"status": STATUS_PENDING, "finished": False}

    # ── Этап 2: Бухгалтер согласовал — возвращаем Директору на финальную подпись ──
    if approval.stage == STAGE_ACCOUNTANT:
        db.add(models.Approval(
            approval_id=gen_id(db, "SOG"), contract_id=contract_id,
            stage=STAGE_DIRECTOR_FINAL, approver_role="Директор", decision="Ожидает", state="active",
        ))
        add_log(db, email, role, "Согласовал", "contract", contract_id, comment)
        db.flush()
        return {"status": STATUS_PENDING, "finished": False}

    # ── Этап 3: финальная подпись Директора ──
    if approval.stage == STAGE_DIRECTOR_FINAL:
        contract.status = STATUS_APPROVED
        add_log(db, email, role, "Финальная подпись", "contract", contract_id, comment)
        db.flush()
        return {"status": STATUS_APPROVED, "finished": True}

    raise ValueError("Некорректный этап согласования.")


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
