from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user
from app.services import workflow as wf

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("/mine")
def my_approvals(db: Session = Depends(get_db), user=Depends(get_current_user)):
    approvals = wf.pending_for_role(db, user.role)
    result = []
    for a in approvals:
        c = db.query(models.Contract).filter(models.Contract.id == a.contract_id).first()
        if not c:
            continue
        result.append({
            "contractId": c.id,
            "subject": c.subject,
            "contractorName": c.contractor_name,
            "pricePerUnit": float(c.price_per_unit or 0),
            "amount": float(c.amount) if c.amount is not None else None,
            "category": c.category,
            "contractType": c.contract_type,
            "approvalTier": c.approval_tier,
            "createdAt": c.created_at,
            "initiatorFio": c.initiator_fio,
            "stage": a.stage,
        })
    result.sort(key=lambda r: r["createdAt"])
    return result


@router.post("/decide")
def decide(data: schemas.DecisionIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role == "Контрагент":
        raise HTTPException(403, "Контрагенту недоступно согласование.")
    if data.decision not in (wf.STATUS_APPROVED, wf.STATUS_REJECTED):
        raise HTTPException(400, "Решение должно быть 'Согласовано' или 'Отклонено'.")
    try:
        result = wf.decide(db, data.contract_id, user.role, user.email, data.decision, data.comment or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result
