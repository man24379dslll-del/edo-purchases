from typing import Optional
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user, require_roles
from app.services import workflow as wf

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


@router.get("", response_model=list[schemas.PurchaseOut])
def list_purchases(
    db: Session = Depends(get_db), user=Depends(get_current_user),
    q: Optional[str] = None, status: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
):
    query = db.query(models.Purchase)
    if user.role not in ("Директор", "Админ", "Маркетинг", "Закупщик", "Фин. директор"):
        query = query.filter(models.Purchase.initiator_email == user.email)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            models.Purchase.id.ilike(like),
            models.Purchase.subject.ilike(like),
            models.Purchase.contractor_name.ilike(like),
        ))
    if status:
        query = query.filter(models.Purchase.status == status)
    if date_from:
        query = query.filter(models.Purchase.created_at >= date_from)
    if date_to:
        query = query.filter(models.Purchase.created_at <= date_to)
    return query.order_by(models.Purchase.created_at.desc()).all()


@router.get("/{purchase_id}")
def get_purchase(purchase_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    p = db.query(models.Purchase).filter(models.Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(404, "Закупка не найдена.")
    receipts = db.query(models.Receipt).filter(models.Receipt.purchase_id == purchase_id).all()
    payments = db.query(models.Payment).filter(models.Payment.purchase_id == purchase_id).all()
    trail = wf.get_approval_trail(db, "purchase", purchase_id)
    received_qty = sum(float(r.quantity) for r in receipts)
    paid_amount = sum(float(pay.amount) for pay in payments)
    return {
        "purchase": schemas.PurchaseOut.model_validate(p),
        "receipts": receipts,
        "payments": payments,
        "remainingQty": float(p.quantity) - received_qty,
        "remainingAmount": float(p.amount) - paid_amount,
        "approvals": [
            {"role": a.approver_role, "stage": a.stage, "decision": a.decision,
             "state": a.state, "date": a.decision_date, "comment": a.comment}
            for a in trail
        ],
    }


@router.post("")
def create_purchase(data: schemas.PurchaseCreateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    contractor_name = None
    if data.contract_id:
        contract = db.query(models.Contract).filter(models.Contract.id == data.contract_id).first()
        if not contract:
            raise HTTPException(404, "Договор не найден.")
        contractor_name = contract.contractor_name

    amount = (data.quantity * data.price_per_unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    purchase_id = wf.gen_id(db, "ЗАК")
    db.add(models.Purchase(
        id=purchase_id, initiator_email=user.email, initiator_fio=user.fio,
        contract_id=data.contract_id, contractor_name=contractor_name,
        purchase_type=data.purchase_type, subcategory=data.subcategory, subject=data.subject,
        quantity=data.quantity, price_per_unit=data.price_per_unit, amount=amount,
        status=wf.STATUS_PENDING, comment=data.comment, file_url=data.file_url,
        execution_status="Не исполнено",
    ))
    wf.start_approval(db, "purchase", purchase_id, subject=data.subject)
    # Примечание: в отличие от договора, у закупки этап "Маркетинг" в PURCHASE_CHAIN
    # задан не списком, а обязательной строкой — он не может быть пропущен через
    # needs_marketing (этого флага в исходной системе для закупок и не было).
    wf.add_log(db, user.email, user.role, "Создал закупку", "purchase", purchase_id, data.subject)
    db.commit()
    return {"id": purchase_id}


@router.post("/{purchase_id}/resubmit")
def resubmit_purchase(purchase_id: str, data: schemas.ResubmitIn, db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    """Доработка отклонённой закупки: правим поля, пересчитываем сумму, новый раунд согласования."""
    purchase = db.query(models.Purchase).filter(models.Purchase.id == purchase_id).with_for_update().first()
    if not purchase:
        raise HTTPException(404, "Закупка не найдена.")
    if purchase.status != wf.STATUS_REJECTED:
        raise HTTPException(400, "Доработать можно только отклонённую закупку.")
    if user.email != purchase.initiator_email and user.role != "Админ":
        raise HTTPException(403, "Доработать закупку может только её инициатор.")

    if data.subject:
        purchase.subject = data.subject
    if data.file_url is not None:
        purchase.file_url = data.file_url
    if data.quantity is not None:
        purchase.quantity = data.quantity
    if data.price_per_unit is not None:
        purchase.price_per_unit = data.price_per_unit
    if data.quantity is not None or data.price_per_unit is not None:
        purchase.amount = (purchase.quantity * purchase.price_per_unit).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
    purchase.comment = data.comment

    new_revision = wf.begin_new_round(db, purchase, "purchase")
    wf.add_log(db, user.email, user.role, f"Доработал и переотправил (раунд {new_revision})",
               "purchase", purchase_id, data.comment)
    db.commit()
    return {"id": purchase_id, "revision": new_revision}


@router.post("/receipts", dependencies=[Depends(require_roles("Склад", "Закупщик"))])
def add_receipt(data: schemas.ReceiptIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    purchase = db.query(models.Purchase).filter(models.Purchase.id == data.purchase_id).first()
    if not purchase:
        raise HTTPException(404, "Закупка не найдена.")
    r_id = wf.gen_id(db, "ПОСТ")
    db.add(models.Receipt(
        id=r_id, purchase_id=data.purchase_id, user_email=user.email, user_fio=user.fio,
        quantity=data.quantity, comment=data.comment,
    ))
    wf.add_log(db, user.email, user.role, "Зафиксировал поступление", "purchase", data.purchase_id,
               f"{data.quantity} ед.")
    db.commit()
    return {"id": r_id}


@router.post("/payments", dependencies=[Depends(require_roles("Бухгалтер", "Фин. директор"))])
def add_payment(data: schemas.PaymentIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    purchase = db.query(models.Purchase).filter(models.Purchase.id == data.purchase_id).first()
    if not purchase:
        raise HTTPException(404, "Закупка не найдена.")
    p_id = wf.gen_id(db, "ПЛТ")
    db.add(models.Payment(
        id=p_id, purchase_id=data.purchase_id, user_email=user.email, user_fio=user.fio,
        amount=data.amount, payment_type=data.payment_type, payment_form=data.payment_form,
        comment=data.comment,
    ))
    wf.add_log(db, user.email, user.role, "Добавил платёж", "purchase", data.purchase_id, f"{data.amount} ₽")
    db.commit()
    return {"id": p_id}
