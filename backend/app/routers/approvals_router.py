from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user, require_roles
from app.services import workflow as wf

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

ENTITY_MODEL = {"contract": models.Contract, "amendment": models.Amendment, "purchase": models.Purchase}


@router.get("/mine")
def my_approvals(db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = []
    now = datetime.now(timezone.utc)
    for entity_type, model in ENTITY_MODEL.items():
        approvals = wf.pending_for_user(db, entity_type, user.email, user.role)
        for a in approvals:
            entity = db.query(model).filter(model.id == a.entity_id).first()
            if not entity:
                continue
            overdue = bool(a.deadline and a.deadline.replace(tzinfo=timezone.utc) < now)
            result.append({
                "entityType": entity_type,
                "entityId": entity.id,
                "subject": entity.subject,
                "createdAt": entity.created_at,
                "initiatorFio": entity.initiator_fio,
                "stage": a.stage,
                "actingAsRole": a.approver_role,       # может отличаться от user.role при делегировании
                "isDelegated": a.approver_role != user.role,
                "deadline": a.deadline,
                "overdue": overdue,
            })
    # просроченные — наверх
    result.sort(key=lambda r: (not r["overdue"], r["createdAt"]))
    return result


@router.post("/decide")
def decide(data: schemas.DecisionIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if data.entity_type not in ENTITY_MODEL:
        raise HTTPException(400, "Неизвестный тип сущности.")
    if data.decision not in (wf.STATUS_APPROVED, wf.STATUS_REJECTED):
        raise HTTPException(400, "Решение должно быть 'Согласовано' или 'Отклонено'.")
    try:
        approver_role = wf.resolve_approver_role(db, data.entity_type, data.entity_id, user.email, user.role)
        result = wf.decide(db, data.entity_type, data.entity_id, approver_role, user.email,
                            data.decision, data.comment or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/decide-bulk")
def decide_bulk(data: schemas.BulkDecisionIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if data.decision not in (wf.STATUS_APPROVED, wf.STATUS_REJECTED):
        raise HTTPException(400, "Решение должно быть 'Согласовано' или 'Отклонено'.")
    results = []
    for item in data.items:
        if item.entity_type not in ENTITY_MODEL:
            results.append({"entityId": item.entity_id, "ok": False, "error": "Неизвестный тип сущности."})
            continue
        try:
            approver_role = wf.resolve_approver_role(db, item.entity_type, item.entity_id, user.email, user.role)
            wf.decide(db, item.entity_type, item.entity_id, approver_role, user.email,
                      data.decision, data.comment or "")
            results.append({"entityId": item.entity_id, "ok": True})
        except ValueError as e:
            results.append({"entityId": item.entity_id, "ok": False, "error": str(e)})
    db.commit()
    return {"results": results}


@router.post("/check-overdue")
def check_overdue(db: Session = Depends(get_db), _=Depends(require_roles("Директор"))):
    """
    Ищет просроченные по SLA этапы и эскалирует их (лог + список для рассылки).
    Вызывается по расписанию — см. README "SLA и эскалация" (Railway Cron / APScheduler).
    Доступ ограничен ролью Директор, чтобы эндпоинт нельзя было дёргать кем попало
    (в проде для cron-вызова обычно используют отдельный сервисный токен).
    """
    escalated = wf.check_overdue(db)
    db.commit()
    return {
        "escalatedCount": len(escalated),
        "items": [{"entityType": a.entity_type, "entityId": a.entity_id, "role": a.approver_role} for a in escalated],
    }


# ══════════════════════════════════════════════════════════════
# ДЕЛЕГИРОВАНИЕ
# ══════════════════════════════════════════════════════════════

@router.get("/delegations")
def list_delegations(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Свои делегирования видит любой пользователь; Директор/Админ видят все."""
    q = db.query(models.Delegation)
    if user.role not in ("Директор", "Админ"):
        q = q.filter(
            (models.Delegation.delegator_email == user.email) | (models.Delegation.delegate_email == user.email)
        )
    return q.order_by(models.Delegation.starts_at.desc()).all()


@router.post("/delegations")
def create_delegation(data: schemas.DelegationIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    delegator = db.query(models.User).filter(models.User.email == data.delegator_email).first()
    if not delegator:
        raise HTTPException(404, "Замещаемый пользователь не найден.")
    delegate = db.query(models.User).filter(models.User.email == data.delegate_email).first()
    if not delegate:
        raise HTTPException(404, "Замещающий пользователь не найден.")
    # Создать делегирование может сам замещаемый (за себя) либо Директор/Админ (за любого).
    if user.email != data.delegator_email and user.role not in ("Директор", "Админ"):
        raise HTTPException(403, "Можно делегировать только свою роль (или быть Директором).")
    if data.ends_at <= data.starts_at:
        raise HTTPException(400, "Дата окончания должна быть позже даты начала.")

    d_id = wf.gen_id(db, "ДЕЛ")
    db.add(models.Delegation(
        id=d_id, delegator_email=delegator.email, delegator_role=delegator.role,
        delegate_email=delegate.email, starts_at=data.starts_at, ends_at=data.ends_at,
        comment=data.comment, created_by=user.email,
    ))
    wf.add_log(db, user.email, user.role, "Создал делегирование", "delegation", d_id,
               f"{delegator.email} ({delegator.role}) → {delegate.email}")
    db.commit()
    return {"id": d_id}


@router.delete("/delegations/{delegation_id}")
def delete_delegation(delegation_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    d = db.query(models.Delegation).filter(models.Delegation.id == delegation_id).first()
    if not d:
        raise HTTPException(404, "Делегирование не найдено.")
    if user.email != d.delegator_email and user.role not in ("Директор", "Админ"):
        raise HTTPException(403, "Недостаточно прав для отмены этого делегирования.")
    db.delete(d)
    wf.add_log(db, user.email, user.role, "Отменил делегирование", "delegation", delegation_id, "")
    db.commit()
    return {"ok": True}
