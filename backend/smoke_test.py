import sys
sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app import models
from app.auth import hash_password
from app.main import app

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

# сидируем пользователей на все роли + юрлицо
db = TestSession()
roles = {
    "buyer@t.co": "Закупщик", "lawyer@t.co": "Юрист", "mkt@t.co": "Маркетинг",
    "findir@t.co": "Фин. директор", "acc@t.co": "Бухгалтер", "dir@t.co": "Директор",
    "init@t.co": "Инициатор", "warehouse@t.co": "Склад",
}
for email, role in roles.items():
    db.add(models.User(email=email, fio=role, role=role, password_hash=hash_password("pass123")))
db.add(models.LegalEntity(id="LE-1", name="ООО Ромашка", inn="7700000000"))
db.add(models.IdCounter(name="global", value=0))
db.commit()
db.close()


def override_get_db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def login(email):
    r = client.post("/api/auth/login", json={"email": email, "password": "pass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def check(cond, msg):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {msg}")
    if not cond:
        raise SystemExit(1)


# 1. Закупщик создаёт договор
h_buyer = login("buyer@t.co")
r = client.post("/api/contracts", headers=h_buyer, json={
    "contractor_name": "ООО Ромашка", "contractor_inn": "7700000000",
    "legal_entity_id": "LE-1", "subject": "Поставка бумаги",
    "limit_amount": "150000.55", "needs_marketing": True,
    "items": [{"name": "Бумага А4", "price": "333.33", "unit": "пачка"}],
})
check(r.status_code == 200, "создание договора")
contract_id = r.json()["id"]
check(contract_id.startswith("ДОГ-"), f"человекочитаемый id: {contract_id}")

# 2. Юрист и Маркетинг согласуют параллельный этап
for email in ("lawyer@t.co", "mkt@t.co"):
    r = client.post("/api/approvals/decide", headers=login(email), json={
        "entity_type": "contract", "entity_id": contract_id, "decision": "Согласовано",
    })
    check(r.status_code == 200, f"{email} согласовал этап 1")

r = client.get(f"/api/contracts/{contract_id}", headers=h_buyer)
stage_states = {a["role"]: a["state"] for a in r.json()["approvals"]}
check(stage_states["Фин. директор"] == "active", "этап 2 (Фин. директор) открылся после параллельного этапа")

# 3. Фин. директор и Бухгалтер согласуют
client.post("/api/approvals/decide", headers=login("findir@t.co"),
            json={"entity_type": "contract", "entity_id": contract_id, "decision": "Согласовано"})
r = client.post("/api/approvals/decide", headers=login("acc@t.co"),
                 json={"entity_type": "contract", "entity_id": contract_id, "decision": "Согласовано"})
check(r.json()["status"] == "Согласовано" and r.json()["finished"], "договор полностью согласован")

r = client.get(f"/api/contracts/{contract_id}", headers=h_buyer)
check(r.json()["contract"]["status"] == "Согласовано", "статус договора обновлён")

# 4. Повторное согласование той же роли должно быть отклонено с понятной ошибкой
r = client.post("/api/approvals/decide", headers=login("acc@t.co"),
                 json={"entity_type": "contract", "entity_id": contract_id, "decision": "Согласовано"})
check(r.status_code == 400, "повторное согласование корректно отклонено (не должно быть активного этапа)")

# 5. Инициатор создаёт закупку по этому договору
h_init = login("init@t.co")
r = client.post("/api/purchases", headers=h_init, json={
    "contract_id": contract_id, "purchase_type": "Товар", "subject": "Бумага для офиса",
    "quantity": "10.5", "price_per_unit": "333.33",
})
check(r.status_code == 200, "создание закупки")
purchase_id = r.json()["id"]

r = client.get(f"/api/purchases/{purchase_id}", headers=h_init)
amount = r.json()["purchase"]["amount"]
# Эталон считаем через Decimal, а не float — иначе сравнение само наступит
# на ту же грабли с плавающей точкой, которую мы и проверяем.
from decimal import Decimal, ROUND_HALF_UP as _RHU
expected = float((Decimal("10.5") * Decimal("333.33")).quantize(Decimal("0.01"), rounding=_RHU))
check(abs(amount - expected) < 0.001, f"сумма закупки посчитана точно через Decimal: {amount} == {expected}")

purchase_stage_states = {a["role"]: a["state"] for a in r.json()["approvals"]}
check(purchase_stage_states["Маркетинг"] == "active", "у закупки маршрут стартует с Маркетинга (не пропущен)")

# полный маршрут закупки: Маркетинг → Директор → Закупщик
client.post("/api/approvals/decide", headers=login("mkt@t.co"),
            json={"entity_type": "purchase", "entity_id": purchase_id, "decision": "Согласовано"})
client.post("/api/approvals/decide", headers=login("dir@t.co"),
            json={"entity_type": "purchase", "entity_id": purchase_id, "decision": "Согласовано"})
r = client.post("/api/approvals/decide", headers=h_buyer,
                 json={"entity_type": "purchase", "entity_id": purchase_id, "decision": "Согласовано"})
check(r.json()["status"] == "Согласовано", "закупка полностью согласована")

# 6. Поступление и платёж
r = client.post("/api/purchases/receipts", headers=login("warehouse@t.co"),
                 json={"purchase_id": purchase_id, "quantity": "5.5"})
check(r.status_code == 200, "поступление зафиксировано")
r = client.post("/api/purchases/payments", headers=login("acc@t.co"),
                 json={"purchase_id": purchase_id, "amount": "1000.10", "payment_type": "Безналичный"})
check(r.status_code == 200, "платёж добавлен")

# 7. Массовое согласование (создаём второй договор и проверяем decide-bulk)
r = client.post("/api/contracts", headers=h_buyer, json={
    "contractor_name": "ООО Ромашка", "subject": "Договор №2",
})
contract_id_2 = r.json()["id"]
r = client.post("/api/approvals/decide-bulk", headers=login("lawyer@t.co"), json={
    "items": [{"entity_type": "contract", "entity_id": contract_id_2}],
    "decision": "Согласовано",
})
check(r.status_code == 200 and r.json()["results"][0]["ok"], "массовое согласование работает")

# 8. ОСВ и экспорт
r = client.get("/api/osv", headers=login("findir@t.co"))
check(r.status_code == 200, "ОСВ доступна Фин. директору")
row = next(x for x in r.json()["rows"] if x["contractorName"] == "ООО Ромашка")
check(row["debit"] > 0, f"ОСВ считает дебет: {row['debit']}")

r = client.get("/api/export/osv.xlsx", headers=login("findir@t.co"))
check(r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxml"), "экспорт ОСВ в xlsx")

# 9. Поиск/фильтры
r = client.get("/api/contracts", headers=h_buyer, params={"q": "Ромашка", "status": "Согласовано"})
check(r.status_code == 200 and len(r.json()) >= 1, "поиск+фильтр по договорам работает")

# 10. Доступ закрыт не-Фин.директору
r = client.get("/api/osv", headers=h_buyer)
check(r.status_code == 403, "ОСВ недоступна Закупщику (403)")

print("\nВСЕ ПРОВЕРКИ ПРОШЛИ УСПЕШНО")
