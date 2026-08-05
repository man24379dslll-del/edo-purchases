from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import require_roles, hash_password
from app.services.workflow import add_log, gen_id
from app.models import ALL_ROLES

router = APIRouter(prefix="/api/admin", tags=["admin"])
director_only = require_roles("Директор")


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(director_only)):
    return db.query(models.User).all()


@router.post("/users")
def add_user(data: schemas.AddUserIn, db: Session = Depends(get_db), user=Depends(director_only)):
    if data.role not in ALL_ROLES:
        raise HTTPException(400, f"Неизвестная роль: {data.role}")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(400, "Пользователь с таким email уже существует.")
    pwd = data.password or "changeme123"
    new_user = models.User(email=data.email, fio=data.fio, role=data.role, password_hash=hash_password(pwd))
    db.add(new_user)
    add_log(db, user.email, "Директор", "Добавил пользователя", "user", data.email, data.role)
    db.commit()
    return {"ok": True, "temp_password": pwd if not data.password else None}


@router.put("/users/{target_email}/role")
def update_role(target_email: str, new_role: str, old_role: str, db: Session = Depends(get_db), user=Depends(director_only)):
    if new_role not in ALL_ROLES:
        raise HTTPException(400, f"Неизвестная роль: {new_role}")
    target = db.query(models.User).filter(models.User.email == target_email, models.User.role == old_role).first()
    if not target:
        raise HTTPException(404, "Пользователь не найден.")
    target.role = new_role
    add_log(db, user.email, "Директор", "Изменил роль", "user", target_email, f"{old_role} → {new_role}")
    db.commit()
    return {"ok": True}


@router.delete("/users/{target_email}")
def remove_user(target_email: str, target_role: str, db: Session = Depends(get_db), user=Depends(director_only)):
    target = db.query(models.User).filter(models.User.email == target_email, models.User.role == target_role).first()
    if not target:
        raise HTTPException(404, "Пользователь не найден.")
    db.delete(target)
    add_log(db, user.email, "Директор", "Удалил пользователя", "user", target_email, target_role)
    db.commit()
    return {"ok": True}


@router.get("/legal-entities", response_model=list[schemas.LegalEntityOut])
def list_legal_entities(db: Session = Depends(get_db), _=Depends(director_only)):
    return db.query(models.LegalEntity).all()


@router.post("/legal-entities")
def add_legal_entity(data: schemas.LegalEntityIn, db: Session = Depends(get_db), user=Depends(director_only)):
    le_id = gen_id(db, "ЮЛ")
    db.add(models.LegalEntity(id=le_id, name=data.name, inn=data.inn, address=data.address))
    add_log(db, user.email, "Директор", "Добавил юрлицо", "legal_entity", le_id, data.name)
    db.commit()
    return {"ok": True, "id": le_id}


@router.delete("/legal-entities/{le_id}")
def remove_legal_entity(le_id: str, db: Session = Depends(get_db), user=Depends(director_only)):
    le = db.query(models.LegalEntity).filter(models.LegalEntity.id == le_id).first()
    if not le:
        raise HTTPException(404, "Юрлицо не найдено.")
    db.delete(le)
    add_log(db, user.email, "Директор", "Удалил юрлицо", "legal_entity", le_id, "")
    db.commit()
    return {"ok": True}


@router.get("/roles")
def get_all_roles():
    return ALL_ROLES
