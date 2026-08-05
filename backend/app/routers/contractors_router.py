from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user
from app.services.workflow import add_log, gen_id

router = APIRouter(prefix="/api/contractors", tags=["contractors"])


@router.get("")
def list_contractors(q: Optional[str] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    query = db.query(models.Contractor)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(models.Contractor.name.ilike(like), models.Contractor.inn.ilike(like)))
    return query.order_by(models.Contractor.name.asc()).limit(50).all()


@router.post("")
def create_contractor(data: schemas.ContractorIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not data.name:
        raise HTTPException(400, "Укажите название контрагента.")
    if data.inn:
        existing = db.query(models.Contractor).filter(models.Contractor.inn == data.inn).first()
        if existing:
            return {"id": existing.id}
    c_id = gen_id(db, "КА")
    db.add(models.Contractor(
        id=c_id, name=data.name, inn=data.inn, contact_person=data.contact_person,
        contact_phone=data.contact_phone, contact_email=data.contact_email, status="Активен",
    ))
    add_log(db, user.email, user.role, "Добавил контрагента", "contractor", c_id, data.name)
    db.commit()
    return {"id": c_id}


@router.get("/form-options")
def form_options(db: Session = Depends(get_db), _=Depends(get_current_user)):
    entities = db.query(models.LegalEntity).all()
    return {
        "legalEntities": [{"id": e.id, "name": e.name} for e in entities],
        "purchaseTypes": ["Товар", "Основные средства", "Полиграфия"],
        "productSubcategories": ["Основные ЗДР/ПП", "Дополнительные ПП", "Тест"],
    }
