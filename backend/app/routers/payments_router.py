from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user, require_roles
from app.services.workflow import gen_id, add_log

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Финансовые роли — видят и ведут платёжный календарь целиком.
FINANCE_ROLES = ("Директор", "Бухгалтер", "Админ")


def _serialize(item: models.PaymentScheduleItem, contract: models.Contract) -> dict:
    return {
        "id": item.id, "contract_id": item.contract_id,
        "due_date": item.due_date, "amount": float(item.amount),
        "status": item.status, "comment": item.comment,
        "created_by": item.created_by, "created_at": item.created_at, "paid_at": item.paid_at,
        "contract_subject": contract.subject if contract else None,
        "contractor_name": contract.contractor_name if contract else None,
    }


@router.get("")
def list_payments(
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    """Платёжный календарь. Контрагенту недоступен — это внутренняя финансовая информация."""
    if user.role == "Контрагент":
        raise HTTPException(403, "Платёжный календарь недоступен контрагенту.")

    query = db.query(models.PaymentScheduleItem)
    if date_from:
        query = query.filter(models.PaymentScheduleItem.due_date >= date_from)
    if date_to:
        query = query.filter(models.PaymentScheduleItem.due_date <= date_to)
    items = query.order_by(models.PaymentScheduleItem.due_date.asc()).all()

    contract_ids = {i.contract_id for i in items}
    contracts = {c.id: c for c in db.query(models.Contract).filter(models.Contract.id.in_(contract_ids)).all()}
    return [_serialize(i, contracts.get(i.contract_id)) for i in items]


@router.post("", dependencies=[Depends(require_roles(*FINANCE_ROLES))])
def create_payment(data: schemas.PaymentScheduleItemIn, db: Session = Depends(get_db),
                    user=Depends(get_current_user)):
    contract = db.query(models.Contract).filter(models.Contract.id == data.contract_id).first()
    if not contract:
        raise HTTPException(404, "Договор не найден.")
    item_id = gen_id(db, "ПЛТ")
    db.add(models.PaymentScheduleItem(
        id=item_id, contract_id=data.contract_id, due_date=data.due_date,
        amount=data.amount, comment=data.comment, created_by=user.email,
    ))
    add_log(db, user.email, user.role, "Добавил плановый платёж", "contract", data.contract_id,
            f"{data.amount} ₽ на {data.due_date}")
    db.commit()
    return {"id": item_id}


@router.put("/{item_id}/paid", dependencies=[Depends(require_roles(*FINANCE_ROLES))])
def mark_paid(item_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = db.query(models.PaymentScheduleItem).filter(models.PaymentScheduleItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Платёж не найден.")
    item.status = "Оплачен"
    item.paid_at = datetime.now(timezone.utc)
    add_log(db, user.email, user.role, "Отметил платёж оплаченным", "contract", item.contract_id,
            f"{item.amount} ₽ на {item.due_date}")
    db.commit()
    return {"ok": True}


@router.delete("/{item_id}", dependencies=[Depends(require_roles(*FINANCE_ROLES))])
def delete_payment(item_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = db.query(models.PaymentScheduleItem).filter(models.PaymentScheduleItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Платёж не найден.")
    add_log(db, user.email, user.role, "Удалил плановый платёж", "contract", item.contract_id,
            f"{item.amount} ₽ на {item.due_date}")
    db.delete(item)
    db.commit()
    return {"ok": True}
