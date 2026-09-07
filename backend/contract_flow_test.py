import sys, os, tempfile, shutil
sys.path.insert(0, ".")

UPLOAD_DIR = tempfile.mkdtemp()
os.environ["UPLOAD_DIR"] = UPLOAD_DIR
os.environ["JWT_SECRET"] = "test"
os.environ["CORS_ORIGINS"] = "*"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app import models
from app.auth import hash_password
from app.main import app

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

db = TestSession()
for email, role in {
    "init@t.co": "Инициатор", "init2@t.co": "Инициатор", "dir@t.co": "Директор",
    "lawyer@t.co": "Юрист", "acc@t.co": "Бухгалтер",
}.items():
    db.add(models.User(email=email, fio=role, role=role, password_hash=hash_password("pass123")))
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
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def check(cond, msg):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {msg}")
    if not cond:
        raise SystemExit(1)


h_init = login("init@t.co")
h_dir = login("dir@t.co")

# ══════════════════════════════════════════════════════════════
# 1. АВТОМАТИЧЕСКАЯ МАРШРУТИЗАЦИЯ ПО КАТЕГОРИИ/ТИПУ/СУММЕ
# ══════════════════════════════════════════════════════════════

# категория из списка "уровня 1" — всегда уровень 1, независимо от суммы
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Товар", "subject": "Поставка товара",
    "category": "Товар/производство", "contract_type": "Системный",
})
check(r.status_code == 200 and r.json()["approval_tier"] == 1, f"категория тир-1 → уровень 1: {r.json()}")
cid_tier1_cat = r.json()["id"]

r = client.get(f"/api/contracts/{cid_tier1_cat}", headers=h_init)
roles = [a["role"] for a in r.json()["approvals"]]
check(roles == ["Юрист", "Бухгалтер", "Директор"], f"цепочка уровня 1: {roles}")
active = [a for a in r.json()["approvals"] if a["state"] == "active"]
check(len(active) == 1 and active[0]["role"] == "Юрист", "первый активный этап — Юрист")

# категория из списка "уровня 2" — уровень 2, независимо от суммы
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Ремонт", "subject": "Ремонт офиса",
    "category": "Ремонтные работы", "contract_type": "Системный",
})
check(r.json()["approval_tier"] == 2, f"категория тир-2 → уровень 2: {r.json()}")
cid_tier2_cat = r.json()["id"]
r = client.get(f"/api/contracts/{cid_tier2_cat}", headers=h_init)
roles = [a["role"] for a in r.json()["approvals"]]
check(roles == ["Директор"], f"цепочка уровня 2 — только Директор: {roles}")

# разовая закупка без суммы — ошибка (нужна сумма для определения порога)
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Закупка", "subject": "Разовая закупка без суммы",
    "category": "Прочее", "contract_type": "Разовая закупка",
})
check(r.status_code == 400, f"разовая закупка без суммы отклонена: {r.status_code}")

# разовая закупка свыше 500 т.р. — уровень 1
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Крупная", "subject": "Крупная разовая закупка",
    "category": "Прочее", "contract_type": "Разовая закупка", "amount": "600000",
})
check(r.json()["approval_tier"] == 1, f"разовая закупка >500т.р. → уровень 1: {r.json()}")

# разовая закупка 100-500 т.р. — уровень 2
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Средняя", "subject": "Средняя разовая закупка",
    "category": "Прочее", "contract_type": "Разовая закупка", "amount": "250000",
})
check(r.json()["approval_tier"] == 2, f"разовая закупка 100-500т.р. → уровень 2: {r.json()}")

# разовая закупка ниже 100 т.р. — тоже уровень 2 (безопасный минимум)
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Мелкая", "subject": "Мелкая разовая закупка",
    "category": "Прочее", "contract_type": "Разовая закупка", "amount": "50000",
})
check(r.json()["approval_tier"] == 2, f"разовая закупка <100т.р. → уровень 2 (минимум): {r.json()}")

# договор без известной суммы (длительный) — если категория тир-1, всё равно уровень 1
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Длительный", "subject": "Долгосрочная аренда без известной цены",
    "category": "Аренда имущества", "contract_type": "Системный",
})
check(r.status_code == 200 and r.json()["approval_tier"] == 1,
      f"длительный договор без суммы, но тир-1 категория → уровень 1: {r.json()}")

# ══════════════════════════════════════════════════════════════
# 2. ПОЛНЫЙ ЦИКЛ СОГЛАСОВАНИЯ УРОВНЯ 1: Юрист → Бухгалтер → Директор
# ══════════════════════════════════════════════════════════════

r = client.post("/api/approvals/decide", headers=login("lawyer@t.co"),
                 json={"contract_id": cid_tier1_cat, "decision": "Согласовано"})
check(r.status_code == 200 and not r.json()["finished"], f"юрист согласовал: {r.text}")

r = client.get(f"/api/contracts/{cid_tier1_cat}", headers=h_init)
active = [a for a in r.json()["approvals"] if a["state"] == "active"]
check(active[0]["role"] == "Бухгалтер", f"после юриста активен бухгалтер: {active}")

# директор пока не может согласовать — не его очередь
r = client.post("/api/approvals/decide", headers=h_dir,
                 json={"contract_id": cid_tier1_cat, "decision": "Согласовано"})
check(r.status_code == 400, f"директор не может согласовать раньше бухгалтера: {r.status_code}")

r = client.post("/api/approvals/decide", headers=login("acc@t.co"),
                 json={"contract_id": cid_tier1_cat, "decision": "Согласовано"})
check(r.status_code == 200 and not r.json()["finished"], f"бухгалтер согласовал: {r.text}")

r = client.post("/api/approvals/decide", headers=h_dir,
                 json={"contract_id": cid_tier1_cat, "decision": "Согласовано"})
check(r.status_code == 200 and r.json()["status"] == "Согласовано" and r.json()["finished"],
      f"директор согласовал финально: {r.text}")

# ══════════════════════════════════════════════════════════════
# 3. УРОВЕНЬ 2: только Директор, сразу финал
# ══════════════════════════════════════════════════════════════

r = client.post("/api/approvals/decide", headers=h_dir,
                 json={"contract_id": cid_tier2_cat, "decision": "Согласовано"})
check(r.status_code == 200 and r.json()["status"] == "Согласовано" and r.json()["finished"],
      f"уровень 2 согласован одним решением директора: {r.text}")

# ══════════════════════════════════════════════════════════════
# 4. ОТКЛОНЕНИЕ ОСТАНАВЛИВАЕТ МАРШРУТ
# ══════════════════════════════════════════════════════════════

r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Откл", "subject": "На отклонение",
    "category": "Товар/производство",
})
cid_rej = r.json()["id"]
r = client.post("/api/approvals/decide", headers=login("lawyer@t.co"),
                 json={"contract_id": cid_rej, "decision": "Отклонено"})
check(r.status_code == 200 and r.json()["status"] == "Отклонено", f"юрист отклонил: {r.text}")
r = client.get(f"/api/contracts/{cid_rej}", headers=h_init)
check(r.json()["contract"]["status"] == "Отклонено", "статус — Отклонено")

# ══════════════════════════════════════════════════════════════
# 5. УДАЛЕНИЕ ДОГОВОРА
# ══════════════════════════════════════════════════════════════

r = client.post("/api/contracts", headers=h_init, json={"contractor_name": "ООО Удал", "subject": "На удаление"})
cid_del = r.json()["id"]
r = client.delete(f"/api/contracts/{cid_del}", headers=login("init2@t.co"))
check(r.status_code == 400, f"не-инициатор не может удалить: {r.status_code}")
r = client.delete(f"/api/contracts/{cid_del}", headers=h_init)
check(r.status_code == 200, f"инициатор удалил договор: {r.text}")
r = client.get(f"/api/contracts/{cid_del}", headers=h_init)
check(r.status_code == 404, "удалённый договор больше не находится")

r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Удал2", "subject": "Тест2", "category": "Товар/производство"})
cid_del2 = r.json()["id"]
client.post("/api/approvals/decide", headers=login("lawyer@t.co"),
            json={"contract_id": cid_del2, "decision": "Согласовано"})
r = client.delete(f"/api/contracts/{cid_del2}", headers=h_init)
check(r.status_code == 400, f"нельзя удалить после хотя бы одного решения: {r.status_code}")

# ══════════════════════════════════════════════════════════════
# 6. ФАЙЛЫ И ХРАНИЛИЩЕ ДОКУМЕНТОВ
# ══════════════════════════════════════════════════════════════

r = client.post("/api/files/upload", headers=h_init,
                 files={"file": ("dogovor.pdf", b"%PDF-1.4 test", "application/pdf")})
check(r.status_code == 200, f"файл загружен: {r.text}")
file_url = r.json()["url"]

r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Файл", "subject": "Договор с файлом", "file_url": file_url,
})
cid_file = r.json()["id"]

r = client.get("/api/documents", headers=h_init, params={"q": "dogovor"})
docs = r.json()
linked = next(d for d in docs if d["original_name"] == "dogovor.pdf")
check(linked["entity_type"] == "contract" and linked["entity_id"] == cid_file,
      f"файл привязался к договору: {linked}")

# доп. соглашение / приложение с типом
r = client.post("/api/files/upload", headers=h_init,
                 files={"file": ("dop_soglashenie.pdf", b"%PDF-1.4 ds", "application/pdf")})
ds_url = r.json()["url"]
r = client.post(f"/api/contracts/{cid_file}/documents", headers=h_init, json={
    "url": ds_url, "doc_type": "Доп. соглашение", "description": "ДС №1",
})
check(r.status_code == 200, f"доп. соглашение прикреплено: {r.text}")

r = client.get(f"/api/contracts/{cid_file}", headers=h_init)
check(len(r.json()["documents"]) == 2, f"на карточке два документа: {r.json()['documents']}")

doc_id = next(d["id"] for d in r.json()["documents"] if d["doc_type"] == "Доп. соглашение")
r = client.delete(f"/api/documents/{doc_id}", headers=login("lawyer@t.co"))
check(r.status_code == 403, f"чужой не может удалить документ: {r.status_code}")
r = client.delete(f"/api/documents/{doc_id}", headers=h_init)
check(r.status_code == 200, f"инициатор удалил документ: {r.text}")

# непривязанный файл
r = client.post("/api/files/upload", headers=h_init,
                 files={"file": ("orphan.pdf", b"%PDF-1.4 orphan", "application/pdf")})
orphan_url = r.json()["url"]
r = client.get("/api/documents", headers=h_init, params={"q": "orphan"})
orphan_doc = r.json()[0]
check(orphan_doc["entity_id"] is None, "непривязанный файл виден без привязки")
r = client.delete(f"/api/documents/{orphan_doc['id']}", headers=h_init)
check(r.status_code == 200, "непривязанный файл удалён")
r = client.get(orphan_url)
check(r.status_code == 404, "файл реально удалён с диска")

# ══════════════════════════════════════════════════════════════
# 7. ПРОЧЕЕ: дашборд, экспорт, роли, "мои согласования"
# ══════════════════════════════════════════════════════════════

r = client.get("/api/approvals/mine", headers=h_dir)
check(r.status_code == 200, f"мои согласования доступны: {r.status_code}")

r = client.get("/api/dashboard", headers=h_init)
check(r.status_code == 200 and "contractsTotal" in r.json(), f"дашборд работает: {r.json()}")

r = client.get("/api/export/contracts.xlsx", headers=h_init)
check(r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxml"), "экспорт в xlsx работает")

r = client.get("/api/admin/roles", headers=h_dir)
check(set(r.json()) == {"Админ", "Инициатор", "Директор", "Юрист", "Бухгалтер", "Контрагент"}, f"роли: {r.json()}")

r = client.get("/api/contracts/categories", headers=h_init)
check(r.status_code == 200 and "categories" in r.json() and "types" in r.json(), f"категории/типы доступны: {r.json()}")

# ══════════════════════════════════════════════════════════════
# 8. ПЛАТЁЖНЫЙ КАЛЕНДАРЬ
# ══════════════════════════════════════════════════════════════

r = client.post("/api/payments", headers=h_dir, json={
    "contract_id": cid_tier1_cat, "due_date": "2026-10-15", "amount": "150000", "comment": "Первый транш",
})
check(r.status_code == 200, f"директор создал плановый платёж: {r.text}")
payment_id = r.json()["id"]

r = client.post("/api/payments", headers=h_init, json={
    "contract_id": cid_tier1_cat, "due_date": "2026-11-15", "amount": "150000",
})
check(r.status_code == 403, f"инициатору недоступно создание платежей: {r.status_code}")

r = client.get("/api/payments", headers=h_dir, params={"date_from": "2026-10-01", "date_to": "2026-10-31"})
check(r.status_code == 200 and len(r.json()) == 1, f"платёж виден в диапазоне дат: {r.json()}")
check(r.json()[0]["contract_subject"] == "Поставка товара", "у платежа подтянут предмет договора")
check(r.json()[0]["status"] == "Запланирован", "статус по умолчанию — Запланирован")

r = client.get("/api/payments", headers=h_init)
check(r.status_code == 200, f"инициатор может смотреть календарь (только не редактировать): {r.status_code}")

r = client.put(f"/api/payments/{payment_id}/paid", headers=h_dir)
check(r.status_code == 200, f"директор отметил платёж оплаченным: {r.text}")
r = client.get("/api/payments", headers=h_dir, params={"date_from": "2026-10-01", "date_to": "2026-10-31"})
check(r.json()[0]["status"] == "Оплачен", "статус сменился на Оплачен")

r = client.delete(f"/api/payments/{payment_id}", headers=h_dir)
check(r.status_code == 200, f"платёж удалён: {r.text}")

shutil.rmtree(UPLOAD_DIR, ignore_errors=True)

# ══════════════════════════════════════════════════════════════
# 9. ПОРТАЛ КОНТРАГЕНТА
# ══════════════════════════════════════════════════════════════

r = client.post("/api/contracts", headers=h_init, json={"contractor_name": "ООО Портал-1", "subject": "Договор для контрагента 1"})
contract_for_c1 = r.json()["id"]
r = client.get(f"/api/contracts/{contract_for_c1}", headers=h_init)
c1_id = r.json()["contract"]["contractor_id"]

r = client.post("/api/contracts", headers=h_init, json={"contractor_name": "ООО Портал-2", "subject": "Договор для контрагента 2"})
contract_for_c2 = r.json()["id"]
r = client.get(f"/api/contracts/{contract_for_c2}", headers=h_init)
c2_id = r.json()["contract"]["contractor_id"]

r = client.post("/api/admin/users", headers=h_dir, json={
    "email": "portal1@t.co", "fio": "Портал 1", "role": "Контрагент",
})
check(r.status_code == 400, f"нельзя создать логин Контрагента без contractor_id: {r.status_code}")

r = client.post("/api/admin/users", headers=h_dir, json={
    "email": "portal1@t.co", "fio": "Портал 1", "role": "Контрагент",
    "contractor_id": c1_id, "password": "pass123",
})
check(r.status_code == 200, f"логин Контрагента создан: {r.text}")

h_c1 = login("portal1@t.co")

r = client.get("/api/contracts", headers=h_c1)
ids = [c["id"] for c in r.json()]
check(contract_for_c1 in ids and contract_for_c2 not in ids, f"контрагент видит только свой договор: {ids}")

r = client.get(f"/api/contracts/{contract_for_c2}", headers=h_c1)
check(r.status_code == 404, f"контрагент не может открыть чужой договор: {r.status_code}")

r = client.post("/api/contracts", headers=h_c1, json={"contractor_name": "Хак", "subject": "Попытка"})
check(r.status_code == 403, "контрагенту недоступно создание договоров")

r = client.get("/api/payments", headers=h_c1)
check(r.status_code == 403, "контрагенту недоступен платёжный календарь")

print("\nВСЕ ПРОВЕРКИ ПРОШЛИ УСПЕШНО")
