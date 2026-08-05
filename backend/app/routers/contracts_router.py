from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user, require_roles
from app.services import workflow as wf

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


@router.get("", response_model=list[schemas.ContractOut])
def list_contracts(
    db: Session = Depends(get_db), user=Depends(get_current_user),
    q: Optional[str] = None, status: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
):
    query = db.query(models.Contract)
    if user.role not in ("Директор", "Админ", "Фин. директор", "Бухгалтер", "Юрист", "Маркетинг"):
        query = query.filter(models.Contract.initiator_email == user.email)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            models.Contract.id.ilike(like),
            models.Contract.subject.ilike(like),
            models.Contract.contractor_name.ilike(like),
            models.Contract.contract_number.ilike(like),
        ))
    if status:
        query = query.filter(models.Contract.status == status)
    if date_from:
        query = query.filter(models.Contract.created_at >= date_from)
    if date_to:
        query = query.filter(models.Contract.created_at <= date_to)
    return query.order_by(models.Contract.created_at.desc()).all()


@router.get("/{contract_id}")
def get_contract(contract_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    c = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if not c:
        raise HTTPException(404, "Договор не найден.")
    items = db.query(models.ContractItem).filter(models.ContractItem.contract_id == contract_id).all()
    files = db.query(models.ContractFile).filter(models.ContractFile.contract_id == contract_id).all()
    trail = wf.get_approval_trail(db, "contract", contract_id)
    return {
        "contract": schemas.ContractOut.model_validate(c),
        "items": items,
        "files": files,
        "approvals": [
            {"role": a.approver_role, "stage": a.stage, "decision": a.decision,
             "state": a.state, "date": a.decision_date, "comment": a.comment}
            for a in trail
        ],
    }


@router.post("", dependencies=[Depends(require_roles("Закупщик"))])
def create_contract(data: schemas.ContractCreateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    contractor = db.query(models.Contractor).filter(models.Contractor.name == data.contractor_name).first()
    if not contractor:
        contractor = models.Contractor(
            id=wf.gen_id(db, "КА"), name=data.contractor_name, inn=data.contractor_inn, status="Активен")
        db.add(contractor)
        db.flush()

    legal_entity = None
    if data.legal_entity_id:
        legal_entity = db.query(models.LegalEntity).filter(models.LegalEntity.id == data.legal_entity_id).first()

    contract_id = wf.gen_id(db, "ДОГ")
    contract = models.Contract(
        id=contract_id,
        initiator_email=user.email,
        initiator_fio=user.fio,
        contractor_id=contractor.id,
        contractor_name=contractor.name,
        contractor_inn=contractor.inn,
        legal_entity_id=legal_entity.id if legal_entity else None,
        legal_entity_name=legal_entity.name if legal_entity else None,
        subject=data.subject,
        contract_number=data.contract_number,
        limit_amount=data.limit_amount,
        status=wf.STATUS_PENDING,
        needs_marketing=data.needs_marketing,
        valid_until=data.valid_until,
        comment=data.comment,
        file_url=data.file_url,
    )
    db.add(contract)
    db.flush()

    for item in data.items:
        db.add(models.ContractItem(
            id=wf.gen_id(db, "ПОЗ"), contract_id=contract_id, name=item.name,
            price=item.price, unit=item.unit, created_by=user.email,
        ))

    wf.start_approval(db, "contract", contract_id, needs_marketing=data.needs_marketing, subject=data.subject)
    wf.add_log(db, user.email, user.role, "Создал договор", "contract", contract_id, data.subject)
    db.commit()
    return {"id": contract_id}


@router.post("/{contract_id}/resubmit")
def resubmit_contract(contract_id: str, data: schemas.ResubmitIn, db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    """
    Доработка отклонённого договора: инициатор правит поля и запускает новый
    раунд согласования с чистого листа (та же цепочка ролей). Старый раунд
    остаётся в истории — виден во вкладке "История"/через /api/log.
    """
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).with_for_update().first()
    if not contract:
        raise HTTPException(404, "Договор не найден.")
    if contract.status != wf.STATUS_REJECTED:
        raise HTTPException(400, "Доработать можно только отклонённый договор.")
    if user.email != contract.initiator_email and user.role != "Админ":
        raise HTTPException(403, "Доработать договор может только его инициатор.")

    if data.subject:
        contract.subject = data.subject
    if data.limit_amount is not None:
        contract.limit_amount = data.limit_amount
    if data.valid_until is not None:
        contract.valid_until = data.valid_until
    if data.file_url is not None:
        contract.file_url = data.file_url
    contract.comment = data.comment

    new_revision = wf.begin_new_round(db, contract, "contract", needs_marketing=contract.needs_marketing)
    wf.add_log(db, user.email, user.role, f"Доработал и переотправил (раунд {new_revision})",
               "contract", contract_id, data.comment)
    db.commit()
    return {"id": contract_id, "revision": new_revision}


@router.post("/amendments", dependencies=[Depends(require_roles("Закупщик"))])
def create_amendment(data: schemas.AmendmentCreateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    contract = db.query(models.Contract).filter(models.Contract.id == data.contract_id).first()
    if not contract:
        raise HTTPException(404, "Договор не найден.")
    am_id = wf.gen_id(db, "ДС")
    db.add(models.Amendment(
        id=am_id, initiator_email=user.email, initiator_fio=user.fio,
        contract_id=data.contract_id, contractor_name=contract.contractor_name,
        subject=data.subject, status=wf.STATUS_PENDING, needs_marketing=data.needs_marketing,
        comment=data.comment, file_url=data.file_url,
    ))
    wf.start_approval(db, "amendment", am_id, needs_marketing=data.needs_marketing, subject=data.subject)
    wf.add_log(db, user.email, user.role, "Создал доп. соглашение", "amendment", am_id, data.subject)
    db.commit()
    return {"id": am_id}


@router.get("/amendments/list")
def list_amendments(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.Amendment).order_by(models.Amendment.created_at.desc()).all()
