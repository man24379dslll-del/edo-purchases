import io
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.auth import get_current_user
from app.services import workflow as wf

router = APIRouter(prefix="/api", tags=["reports"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER_FILL = PatternFill("solid", fgColor="1A2347")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def _sheet_response(wb: Workbook, filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _write_header(ws, headers):
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    ws.freeze_panes = "A2"


def _autosize(ws):
    for col in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max(length + 2, 10), 45)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    contracts_q = db.query(models.Contract)
    purchases_q = db.query(models.Purchase)
    if user.role not in ("Директор", "Админ", "Фин. директор", "Бухгалтер", "Юрист", "Маркетинг", "Закупщик"):
        contracts_q = contracts_q.filter(models.Contract.initiator_email == user.email)
        purchases_q = purchases_q.filter(models.Purchase.initiator_email == user.email)

    contracts = contracts_q.all()
    purchases = purchases_q.all()
    my_pending = wf.pending_for_role(db, "contract", user.role) \
        + wf.pending_for_role(db, "amendment", user.role) \
        + wf.pending_for_role(db, "purchase", user.role)

    return {
        "contractsTotal": len(contracts),
        "contractsPending": sum(1 for c in contracts if c.status == wf.STATUS_PENDING),
        "contractsApproved": sum(1 for c in contracts if c.status == wf.STATUS_APPROVED),
        "purchasesTotal": len(purchases),
        "purchasesPending": sum(1 for p in purchases if p.status == wf.STATUS_PENDING),
        "purchasesApproved": sum(1 for p in purchases if p.status == wf.STATUS_APPROVED),
        "purchasesAmount": float(sum((p.amount or Decimal("0")) for p in purchases if p.status != wf.STATUS_REJECTED)),
        "myPendingApprovals": len(my_pending),
    }


@router.get("/log/{entity_id}")
def get_log(entity_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(models.LogEntry).filter(models.LogEntry.entity_id == entity_id) \
        .order_by(models.LogEntry.timestamp.asc()).all()
    return [{"date": r.timestamp, "user": r.user_email, "role": r.role,
             "action": r.action, "comment": r.comment} for r in rows]


@router.get("/osv")
def get_osv(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Вся арифметика ниже — в Decimal, а не float. Деньги, накапливаемые сложением
    сотен строк (закупки, платежи), на float дают заметную погрешность в копейках;
    в Decimal её нет. Конвертация в float происходит только один раз, в самом
    конце — при сериализации в JSON для фронтенда.
    """
    if user.role not in ("Фин. директор", "Админ"):
        raise HTTPException(403, "ОСВ доступна только Фин. директору и Админу.")

    contractors = db.query(models.Contractor).all()
    contracts = db.query(models.Contract).all()
    purchases = db.query(models.Purchase).all()
    payments = db.query(models.Payment).all()
    receipts = db.query(models.Receipt).all()

    contracts_by_id = {c.id: c for c in contracts}
    purchases_by_id = {p.id: p for p in purchases}

    Z = Decimal("0")
    m = {}
    for c in contractors:
        m[c.id] = {
            "contractorId": c.id, "contractorName": c.name, "contractorInn": c.inn or "",
            "contracts": 0, "contractSum": Z, "debit": Z, "credit": Z, "saldo": Z,
            "orderedQty": Z, "receivedQty": Z,
        }

    for c in contracts:
        row = m.get(c.contractor_id)
        if not row:
            continue
        row["contracts"] += 1
        if "Отклонено" not in (c.status or ""):
            row["contractSum"] += (c.limit_amount or Z)

    def contractor_id_for_contract(contract_id):
        c = contracts_by_id.get(contract_id)
        return c.contractor_id if c else None

    for p in purchases:
        contractor_id = contractor_id_for_contract(p.contract_id)
        row = m.get(contractor_id)
        if not row:
            continue
        if "Отклонено" in (p.status or ""):
            continue
        row["debit"] += (p.amount or Z)
        row["orderedQty"] += (p.quantity or Z)

    for pay in payments:
        purchase = purchases_by_id.get(pay.purchase_id)
        if not purchase:
            continue
        contractor_id = contractor_id_for_contract(purchase.contract_id)
        row = m.get(contractor_id)
        if not row:
            continue
        row["credit"] += (pay.amount or Z)

    for r in receipts:
        purchase = purchases_by_id.get(r.purchase_id)
        if not purchase:
            continue
        contractor_id = contractor_id_for_contract(purchase.contract_id)
        row = m.get(contractor_id)
        if not row:
            continue
        row["receivedQty"] += (r.quantity or Z)

    rows = list(m.values())
    for row in rows:
        row["saldo"] = row["debit"] - row["credit"]
        row["saldoQty"] = row["orderedQty"] - row["receivedQty"]
    rows.sort(key=lambda r: r["saldo"], reverse=True)

    totals = {"contracts": 0, "contractSum": Z, "debit": Z, "credit": Z, "saldo": Z,
              "orderedQty": Z, "receivedQty": Z, "saldoQty": Z}
    for row in rows:
        for k in totals:
            totals[k] += row[k]

    # Единственное место конвертации Decimal → float: на выходе в JSON для фронтенда.
    def to_float(d):
        return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in d.items()}

    return {
        "rows": [to_float(r) for r in rows],
        "totals": to_float(totals),
        "generatedAt": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }


@router.get("/export/contracts.xlsx")
def export_contracts(db: Session = Depends(get_db), user=Depends(get_current_user)):
    query = db.query(models.Contract)
    if user.role not in ("Директор", "Админ", "Фин. директор", "Бухгалтер", "Юрист", "Маркетинг"):
        query = query.filter(models.Contract.initiator_email == user.email)
    rows = query.order_by(models.Contract.created_at.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Договоры"
    _write_header(ws, ["№", "Дата", "Инициатор", "Контрагент", "ИНН", "Юрлицо",
                        "Предмет", "Номер договора", "Лимит, ₽", "Статус", "Действует до", "Комментарий"])
    for c in rows:
        ws.append([
            c.id, c.created_at.strftime("%d.%m.%Y %H:%M") if c.created_at else "", c.initiator_fio,
            c.contractor_name, c.contractor_inn or "", c.legal_entity_name or "",
            c.subject, c.contract_number or "", float(c.limit_amount or 0), c.status,
            c.valid_until.strftime("%d.%m.%Y") if c.valid_until else "", c.comment or "",
        ])
    _autosize(ws)
    return _sheet_response(wb, "contracts.xlsx")


@router.get("/export/purchases.xlsx")
def export_purchases(db: Session = Depends(get_db), user=Depends(get_current_user)):
    query = db.query(models.Purchase)
    if user.role not in ("Директор", "Админ", "Маркетинг", "Закупщик", "Фин. директор"):
        query = query.filter(models.Purchase.initiator_email == user.email)
    rows = query.order_by(models.Purchase.created_at.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Закупки"
    _write_header(ws, ["№", "Дата", "Инициатор", "Договор", "Контрагент", "Тип", "Подкатегория",
                        "Предмет", "Кол-во", "Цена за ед.", "Сумма, ₽", "Статус", "Исполнение", "Комментарий"])
    for p in rows:
        ws.append([
            p.id, p.created_at.strftime("%d.%m.%Y %H:%M") if p.created_at else "", p.initiator_fio,
            p.contract_id or "", p.contractor_name or "", p.purchase_type or "", p.subcategory or "",
            p.subject, float(p.quantity or 0), float(p.price_per_unit or 0), float(p.amount or 0),
            p.status, p.execution_status or "", p.comment or "",
        ])
    _autosize(ws)
    return _sheet_response(wb, "purchases.xlsx")


@router.get("/export/osv.xlsx")
def export_osv(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role not in ("Фин. директор", "Админ"):
        raise HTTPException(403, "ОСВ доступна только Фин. директору и Админу.")
    data = get_osv(db, user)

    wb = Workbook()
    ws = wb.active
    ws.title = "ОСВ"
    _write_header(ws, ["Контрагент", "ИНН", "Договоров", "Сумма договоров, ₽", "Дебет, ₽",
                        "Кредит, ₽", "Сальдо, ₽", "Заказано", "Получено", "Остаток"])
    for r in data["rows"]:
        saldo_qty = r.get("saldoQty", r["orderedQty"] - r["receivedQty"])
        ws.append([
            r["contractorName"], r["contractorInn"], r["contracts"], r["contractSum"],
            r["debit"], r["credit"], r["saldo"], r["orderedQty"], r["receivedQty"], saldo_qty,
        ])
    t = data["totals"]
    ws.append(["ИТОГО", "", t["contracts"], t["contractSum"], t["debit"], t["credit"],
               t["saldo"], t["orderedQty"], t["receivedQty"], t["saldoQty"]])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
    _autosize(ws)
    return _sheet_response(wb, "osv.xlsx")
