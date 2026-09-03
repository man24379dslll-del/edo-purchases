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
    if user.role == "Контрагент":
        # Портал контрагента: видит только договоры, где он сам является контрагентом.
        query = query.filter(models.Contract.contractor_id == user.contractor_id)
    elif user.role not in ("Директор", "Админ", "Юрист", "Бухгалтер"):
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


@router.get("/doc-types")
def get_doc_types():
    return wf.DOC_TYPES


@router.get("/{contract_id}")
def get_contract(contract_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if not c:
        raise HTTPException(404, "Договор не найден.")
    if user.role == "Контрагент" and c.contractor_id != user.contractor_id:
        raise HTTPException(404, "Договор не найден.")  # не 403 — не палим сам факт существования чужого id
    trail = wf.get_approval_trail(db, contract_id)
    docs = db.query(models.Document).filter(
        models.Document.entity_type == "contract", models.Document.entity_id == contract_id,
    ).order_by(models.Document.uploaded_at.asc()).all()
    return {
        "contract": schemas.ContractOut.model_validate(c),
        "approvals": [
            {"role": a.approver_role, "stage": a.stage, "decision": a.decision,
             "state": a.state, "date": a.decision_date, "comment": a.comment}
            for a in trail
        ],
        "documents": [schemas.DocumentOut.model_validate(d) for d in docs],
    }


@router.post("")
def create_contract(data: schemas.ContractCreateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role == "Контрагент":
        raise HTTPException(403, "Контрагенту недоступно создание договоров.")
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
        price_per_unit=data.price_per_unit,
        status=wf.STATUS_PENDING,
        valid_until=data.valid_until,
        comment=data.comment,
        file_url=data.file_url,
    )
    db.add(contract)
    db.flush()

    wf.link_document(db, data.file_url, contract_id, data.subject)
    wf.start_approval(db, contract_id)
    wf.add_log(db, user.email, user.role, "Создал договор", "contract", contract_id, data.subject)
    db.commit()
    return {"id": contract_id}


@router.delete("/{contract_id}")
def delete_contract(contract_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role == "Контрагент":
        raise HTTPException(403, "Контрагенту недоступно удаление договоров.")
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).with_for_update().first()
    if not contract:
        raise HTTPException(404, "Договор не найден.")
    try:
        wf.assert_deletable(db, contract, user.email, user.role)
    except ValueError as e:
        raise HTTPException(400, str(e))
    wf.delete_contract(db, contract, user.email, user.role)
    db.commit()
    return {"ok": True}


@router.post("/{contract_id}/documents")
def attach_document(contract_id: str, data: schemas.AttachDocumentIn, db: Session = Depends(get_db),
                     user=Depends(get_current_user)):
    """
    Прикрепляет уже загруженный файл (см. POST /api/files/upload) к договору —
    доп. соглашение, приложение, скан подписанного экземпляра и т.д.
    """
    if user.role == "Контрагент":
        raise HTTPException(403, "Контрагенту недоступно добавление документов.")
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(404, "Договор не найден.")
    if data.doc_type not in wf.DOC_TYPES:
        raise HTTPException(400, f"Неизвестный тип документа. Допустимые: {', '.join(wf.DOC_TYPES)}")
    wf.link_document(db, data.url, contract_id, data.description or contract.subject, doc_type=data.doc_type)
    wf.add_log(db, user.email, user.role, f"Добавил документ «{data.doc_type}»", "contract", contract_id,
               data.description or "")
    db.commit()
    return {"ok": True}
