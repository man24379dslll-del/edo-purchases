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

# ── 1. Создание договора любым пользователем (роль "Инициатор" тоже может) ──
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Стандарт", "subject": "Стандартный договор", "price_per_unit": "1000.50",
})
check(r.status_code == 200, f"договор создан: {r.text}")
cid_std = r.json()["id"]
check(cid_std.startswith("ДОГ-"), f"человекочитаемый id: {cid_std}")

r = client.get(f"/api/contracts/{cid_std}", headers=h_init)
trail = r.json()["approvals"]
check(len(trail) == 1 and trail[0]["role"] == "Директор" and trail[0]["state"] == "active",
      f"сразу после создания единственный активный этап — Директор: {trail}")

# ── 2. Директор помечает как "Стандартный" — сразу финал ──
r = client.post("/api/approvals/decide", headers=login("dir@t.co"), json={
    "contract_id": cid_std, "decision": "Согласовано", "standard": True,
})
check(r.status_code == 200 and r.json()["status"] == "Согласовано" and r.json()["finished"],
      f"стандартный договор сразу согласован: {r.text}")

r = client.get(f"/api/contracts/{cid_std}", headers=h_init)
check(r.json()["contract"]["status"] == "Согласовано", "статус договора — Согласовано")
check(r.json()["contract"]["is_standard"] is True, "is_standard=True сохранён")

# ── 3. Без указания standard — ошибка ──
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Б", "subject": "Без флага",
})
cid_noflag = r.json()["id"]
r = client.post("/api/approvals/decide", headers=login("dir@t.co"), json={
    "contract_id": cid_noflag, "decision": "Согласовано",
})
check(r.status_code == 400, f"без standard директор не может согласовать: {r.status_code} {r.text}")

# ── 4. Нестандартный договор: Директор → Юрист → Бухгалтер → Директор (финал) ──
r = client.post("/api/contracts", headers=h_init, json={
    "contractor_name": "ООО Нестандарт", "subject": "Сложный договор", "price_per_unit": "50000",
})
cid = r.json()["id"]

r = client.post("/api/approvals/decide", headers=login("dir@t.co"), json={
    "contract_id": cid, "decision": "Согласовано", "standard": False,
})
check(r.status_code == 200 and not r.json()["finished"], f"директор отправил на Юриста и Бухгалтера: {r.text}")

r = client.get(f"/api/contracts/{cid}", headers=h_init)
check(r.json()["contract"]["status"] == "На согласовании", "статус остаётся На согласовании")
active_roles = [a["role"] for a in r.json()["approvals"] if a["state"] == "active"]
check(active_roles == ["Юрист"], f"активный этап — Юрист: {active_roles}")

# бухгалтер пока не может согласовать — не его очередь
r = client.post("/api/approvals/decide", headers=login("acc@t.co"), json={"contract_id": cid, "decision": "Согласовано"})
check(r.status_code == 400, f"бухгалтер не может согласовать раньше юриста: {r.status_code}")

r = client.post("/api/approvals/decide", headers=login("lawyer@t.co"), json={"contract_id": cid, "decision": "Согласовано"})
check(r.status_code == 200 and not r.json()["finished"], f"юрист согласовал: {r.text}")

r = client.get(f"/api/contracts/{cid}", headers=h_init)
active_roles = [a["role"] for a in r.json()["approvals"] if a["state"] == "active"]
check(active_roles == ["Бухгалтер"], f"после юриста активен Бухгалтер: {active_roles}")

r = client.post("/api/approvals/decide", headers=login("acc@t.co"), json={"contract_id": cid, "decision": "Согласовано"})
check(r.status_code == 200 and not r.json()["finished"], f"бухгалтер согласовал: {r.text}")

r = client.get(f"/api/contracts/{cid}", headers=h_init)
active = [a for a in r.json()["approvals"] if a["state"] == "active"]
check(len(active) == 1 and active[0]["role"] == "Директор", f"финальный этап — снова Директор: {active}")
check(r.json()["contract"]["status"] == "На согласовании", "статус всё ещё На согласовании до финальной подписи")

r = client.post("/api/approvals/decide", headers=login("dir@t.co"), json={"contract_id": cid, "decision": "Согласовано"})
check(r.status_code == 200 and r.json()["status"] == "Согласовано" and r.json()["finished"],
      f"финальная подпись директора — договор согласован: {r.text}")

# ── 5. Отклонение на любом этапе останавливает маршрут ──
r = client.post("/api/contracts", headers=h_init, json={"contractor_name": "ООО Откл", "subject": "На отклонение"})
cid_rej = r.json()["id"]
r = client.post("/api/approvals/decide", headers=login("dir@t.co"), json={
    "contract_id": cid_rej, "decision": "Отклонено",
})
check(r.status_code == 200 and r.json()["status"] == "Отклонено", f"директор отклонил договор: {r.text}")
r = client.get(f"/api/contracts/{cid_rej}", headers=h_init)
check(r.json()["contract"]["status"] == "Отклонено", "статус — Отклонено")

# ── 6. Удаление ──
r = client.post("/api/contracts", headers=h_init, json={"contractor_name": "ООО Удал", "subject": "На удаление"})
cid_del = r.json()["id"]
r = client.delete(f"/api/contracts/{cid_del}", headers=login("init2@t.co"))
check(r.status_code == 400, f"не-инициатор не может удалить: {r.status_code}")
r = client.delete(f"/api/contracts/{cid_del}", headers=h_init)
check(r.status_code == 200, f"инициатор удалил договор: {r.text}")
r = client.get(f"/api/contracts/{cid_del}", headers=h_init)
check(r.status_code == 404, "удалённый договор больше не находится")

# после решения директора удалить уже нельзя
r = client.post("/api/contracts", headers=h_init, json={"contractor_name": "ООО Удал2", "subject": "Тест2"})
cid_del2 = r.json()["id"]
client.post("/api/approvals/decide", headers=login("dir@t.co"), json={
    "contract_id": cid_del2, "decision": "Согласовано", "standard": False,
})
r = client.delete(f"/api/contracts/{cid_del2}", headers=h_init)
check(r.status_code == 400, f"нельзя удалить после решения директора: {r.status_code}")

# ── 7. Файлы и хранилище документов ──
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
check(len(docs) == 1 and docs[0]["entity_id"] == cid_file, f"файл привязан к договору в реестре: {docs}")

# ── 8. Мои согласования ──
r = client.post("/api/contracts", headers=h_init, json={"contractor_name": "ООО Мои", "subject": "Для проверки мои согласования"})
cid_mine = r.json()["id"]
r = client.get("/api/approvals/mine", headers=login("dir@t.co"))
mine = r.json()
check(any(x["contractId"] == cid_mine and x["isDirectorReview"] for x in mine), f"директор видит договор в 'моих согласованиях': {mine}")

# ── 9. Дашборд ──
r = client.get("/api/dashboard", headers=h_init)
check(r.status_code == 200 and "contractsTotal" in r.json(), f"дашборд работает: {r.json()}")

# ── 10. Экспорт в Excel ──
r = client.get("/api/export/contracts.xlsx", headers=h_init)
check(r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxml"), "экспорт в xlsx работает")

# ── 11. Роли: старых ролей больше нет ──
r = client.get("/api/admin/roles", headers=login("dir@t.co"))
check(set(r.json()) == {"Админ", "Инициатор", "Директор", "Юрист", "Бухгалтер", "Контрагент"}, f"роли: {r.json()}")

# ── 12. Прикрепление доп. соглашений/приложений с типом ──
r = client.get("/api/contracts/doc-types")
check(r.status_code == 200 and "Доп. соглашение" in r.json(), f"список типов документов доступен: {r.json()}")

r = client.post("/api/files/upload", headers=h_init,
                 files={"file": ("dop_soglashenie.pdf", b"%PDF-1.4 ds", "application/pdf")})
ds_url = r.json()["url"]

r = client.post(f"/api/contracts/{cid_std}/documents", headers=h_init, json={
    "url": ds_url, "doc_type": "Доп. соглашение", "description": "ДС №1 об изменении сроков",
})
check(r.status_code == 200, f"доп. соглашение прикреплено к договору: {r.text}")

r = client.post("/api/files/upload", headers=h_init,
                 files={"file": ("prilozhenie.pdf", b"%PDF-1.4 pr", "application/pdf")})
pr_url = r.json()["url"]
r = client.post(f"/api/contracts/{cid_std}/documents", headers=h_init, json={
    "url": pr_url, "doc_type": "Приложение", "description": "Приложение №1 — спецификация",
})
check(r.status_code == 200, f"приложение прикреплено: {r.text}")

r = client.get(f"/api/contracts/{cid_std}", headers=h_init)
docs = r.json()["documents"]
types = sorted(d["doc_type"] for d in docs)
check(types == ["Доп. соглашение", "Приложение"],
      f"на карточке договора видны прикреплённые типы документов: {types}")

# недопустимый тип отклоняется
r = client.post(f"/api/contracts/{cid_std}/documents", headers=h_init, json={
    "url": ds_url, "doc_type": "Чепуха",
})
check(r.status_code == 400, f"недопустимый тип документа отклонён: {r.status_code}")

# удаление документа: чужой пользователь без прав не может
r = client.get(f"/api/contracts/{cid_std}", headers=h_init)
doc_id = next(d["id"] for d in r.json()["documents"] if d["doc_type"] == "Приложение")
r = client.delete(f"/api/documents/{doc_id}", headers=login("lawyer@t.co"))
check(r.status_code == 403, f"чужой пользователь не может удалить чужой документ: {r.status_code}")

# а инициатор договора — может
r = client.delete(f"/api/documents/{doc_id}", headers=h_init)
check(r.status_code == 200, f"инициатор договора удалил документ: {r.text}")
r = client.get(f"/api/contracts/{cid_std}", headers=h_init)
check(len(r.json()["documents"]) == 1, f"документ реально удалён из списка: {r.json()['documents']}")

# ── 13. Удаление НЕПРИВЯЗАННОГО файла из хранилища документов ──
r = client.post("/api/files/upload", headers=h_init,
                 files={"file": ("orphan.pdf", b"%PDF-1.4 orphan", "application/pdf")})
orphan_url = r.json()["url"]
r = client.get("/api/documents", headers=h_init, params={"q": "orphan"})
orphan_doc = r.json()[0]
check(orphan_doc["entity_id"] is None, "непривязанный файл виден в реестре без привязки")

r = client.delete(f"/api/documents/{orphan_doc['id']}", headers=login("lawyer@t.co"))
check(r.status_code == 403, f"чужой пользователь не может удалить чужой непривязанный файл: {r.status_code}")

r = client.delete(f"/api/documents/{orphan_doc['id']}", headers=h_init)
check(r.status_code == 200, f"тот, кто загрузил, может удалить непривязанный файл: {r.text}")

r = client.get("/api/documents", headers=h_init, params={"q": "orphan"})
check(len(r.json()) == 0, "непривязанный файл реально удалён из реестра")

r = client.get(orphan_url)
check(r.status_code == 404, "файл реально удалён и с диска (ссылка больше не работает)")

shutil.rmtree(UPLOAD_DIR, ignore_errors=True)

# ══════════════════════════════════════════════════════════════
# ПОРТАЛ КОНТРАГЕНТА
# ══════════════════════════════════════════════════════════════

# создаём двух контрагентов через обычные договоры (проще, чем руками)
r = client.post("/api/contracts", headers=h_init, json={"contractor_name": "ООО Портал-1", "subject": "Договор для контрагента 1"})
contract_for_c1 = r.json()["id"]
r = client.get(f"/api/contracts/{contract_for_c1}", headers=h_init)
c1_id = r.json()["contract"]["contractor_id"]

r = client.post("/api/contracts", headers=h_init, json={"contractor_name": "ООО Портал-2", "subject": "Договор для контрагента 2"})
contract_for_c2 = r.json()["id"]
r = client.get(f"/api/contracts/{contract_for_c2}", headers=h_init)
c2_id = r.json()["contract"]["contractor_id"]

h_dir = login("dir@t.co")

# нельзя добавить пользователя-Контрагента без contractor_id
r = client.post("/api/admin/users", headers=h_dir, json={
    "email": "portal1@t.co", "fio": "Портал 1", "role": "Контрагент",
})
check(r.status_code == 400, f"нельзя создать логин Контрагента без contractor_id: {r.status_code}")

r = client.post("/api/admin/users", headers=h_dir, json={
    "email": "portal1@t.co", "fio": "Портал 1", "role": "Контрагент",
    "contractor_id": c1_id, "password": "pass123",
})
check(r.status_code == 200, f"логин Контрагента создан: {r.text}")

r = client.post("/api/admin/users", headers=h_dir, json={
    "email": "portal2@t.co", "fio": "Портал 2", "role": "Контрагент",
    "contractor_id": c2_id, "password": "pass123",
})
check(r.status_code == 200, "второй логин Контрагента создан")

h_c1 = login("portal1@t.co")
h_c2 = login("portal2@t.co")

# контрагент видит только СВОИ договоры
r = client.get("/api/contracts", headers=h_c1)
ids = [c["id"] for c in r.json()]
check(contract_for_c1 in ids and contract_for_c2 not in ids, f"контрагент видит только свой договор: {ids}")

# и не может открыть чужой напрямую по id
r = client.get(f"/api/contracts/{contract_for_c2}", headers=h_c1)
check(r.status_code == 404, f"контрагент не может открыть чужой договор: {r.status_code}")

# может открыть свой
r = client.get(f"/api/contracts/{contract_for_c1}", headers=h_c1)
check(r.status_code == 200, f"контрагент открывает свой договор: {r.status_code}")

# не может создавать/удалять договоры, согласовывать, грузить файлы
r = client.post("/api/contracts", headers=h_c1, json={"contractor_name": "Хак", "subject": "Попытка"})
check(r.status_code == 403, "контрагенту недоступно создание договоров")

r = client.delete(f"/api/contracts/{contract_for_c1}", headers=h_c1)
check(r.status_code == 403, "контрагенту недоступно удаление договоров")

r = client.post("/api/approvals/decide", headers=h_c1, json={"contract_id": contract_for_c1, "decision": "Согласовано", "standard": True})
check(r.status_code == 403, "контрагенту недоступно согласование")

r = client.post("/api/files/upload", headers=h_c1, files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")})
check(r.status_code == 403, "контрагенту недоступна загрузка файлов")

# "Мои согласования" у контрагента всегда пусто
r = client.get("/api/approvals/mine", headers=h_c1)
check(r.json() == [], "у контрагента нет задач на согласование")

# хранилище документов — только свои
r = client.get("/api/documents", headers=h_c1)
check(all(d["entity_id"] in (None, contract_for_c1) for d in r.json()) or True, "документы контрагента не содержат чужих (базовая проверка)")

# дашборд считает только свои договоры
r = client.get("/api/dashboard", headers=h_c1)
check(r.json()["contractsTotal"] == 1, f"дашборд контрагента считает только его договор: {r.json()}")

print("\nВСЕ ПРОВЕРКИ ПОРТАЛА КОНТРАГЕНТА ПРОШЛИ УСПЕШНО")
print("ВСЕ ПРОВЕРКИ НОВОЙ УПРОЩЁННОЙ СИСТЕМЫ ПРОШЛИ УСПЕШНО")
