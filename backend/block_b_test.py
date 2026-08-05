import sys
sys.path.insert(0, ".")

from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app import models
from app.auth import hash_password
from app.services import notifications
from app.main import app

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

db = TestSession()
roles = {
    "buyer@t.co": "Закупщик", "lawyer@t.co": "Юрист", "lawyer2@t.co": "Склад",
    "mkt@t.co": "Маркетинг", "findir@t.co": "Фин. директор", "acc@t.co": "Бухгалтер",
    "dir@t.co": "Директор",
}
for email, role in roles.items():
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


h_buyer = login("buyer@t.co")

# ── 1. SLA: у только что созданного договора первый этап имеет дедлайн ──
r = client.post("/api/contracts", headers=h_buyer, json={
    "contractor_name": "ООО Тест", "subject": "SLA-тест",
})
contract_id = r.json()["id"]
r = client.get(f"/api/contracts/{contract_id}", headers=h_buyer)
lawyer_stage = next(a for a in r.json()["approvals"] if a["role"] == "Юрист")
check(lawyer_stage["state"] == "active", "первый этап активен сразу после создания")

# ── 2. Уведомления: хук вызвался при создании (проверяем через _last_sent) ──
notifications._last_sent.clear()
r = client.post("/api/contracts", headers=h_buyer, json={
    "contractor_name": "ООО Уведомление", "subject": "Проверка письма",
})
contract_id_notif = r.json()["id"]
sent_to = {m["to"] for m in notifications._last_sent}
check("lawyer@t.co" in sent_to, f"уведомление ушло Юристу: {sent_to}")
check(any("Проверка письма" in m["body"] for m in notifications._last_sent), "тема письма содержит предмет договора")

# ── 3. Эскалация: искусственно просрочим дедлайн и вызовем check-overdue ──
db2 = TestSession()
appr = db2.query(models.Approval).filter(
    models.Approval.entity_id == contract_id, models.Approval.approver_role == "Юрист",
    models.Approval.state == "active",
).first()
appr.deadline = datetime.now(timezone.utc) - timedelta(hours=1)
db2.commit()
db2.close()

notifications._last_sent.clear()
r = client.post("/api/approvals/check-overdue", headers=login("dir@t.co"))
check(r.status_code == 200 and r.json()["escalatedCount"] >= 1, f"эскалация нашла просроченный этап: {r.json()}")
check(any(m["to"] == "dir@t.co" for m in notifications._last_sent), "директор уведомлён об эскалации")

# повторный вызов не должен эскалировать тот же этап снова
r2 = client.post("/api/approvals/check-overdue", headers=login("dir@t.co"))
same_contract_again = any(i["entityId"] == contract_id for i in r2.json()["items"])
check(not same_contract_again, "повторная эскалация того же этапа не происходит (escalated=True)")

# закупщику эскалация недоступна (не Директор)
r = client.post("/api/approvals/check-overdue", headers=h_buyer)
check(r.status_code == 403, "эскалация недоступна не-Директору")

# ── 4. Делегирование: Юрист2 замещает Юриста и согласовывает вместо него ──
r = client.post("/api/approvals/delegations", headers=login("lawyer@t.co"), json={
    "delegator_email": "lawyer@t.co", "delegate_email": "lawyer2@t.co",
    "starts_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    "ends_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    "comment": "Отпуск",
})
check(r.status_code == 200, f"делегирование создано: {r.text}")

r = client.get("/api/approvals/mine", headers=login("lawyer2@t.co"))
mine = r.json()
check(any(x["entityId"] == contract_id and x["isDelegated"] for x in mine),
      "замещающий видит чужую задачу как делегированную")

r = client.post("/api/approvals/decide", headers=login("lawyer2@t.co"),
                 json={"entity_type": "contract", "entity_id": contract_id, "decision": "Согласовано"})
check(r.status_code == 200, f"замещающий согласовал вместо Юриста: {r.text}")

r = client.get(f"/api/contracts/{contract_id}", headers=h_buyer)
lawyer_stage = next(a for a in r.json()["approvals"] if a["role"] == "Юрист")
check(lawyer_stage["decision"] == "Согласовано", "этап Юриста закрыт решением замещающего")

# у настоящего Юриста задачи по этому договору больше нет
r = client.get("/api/approvals/mine", headers=login("lawyer@t.co"))
check(not any(x["entityId"] == contract_id for x in r.json()), "исходный Юрист больше не видит закрытую задачу")

# ── 5. Доработка отклонённого договора ──
r = client.post("/api/contracts", headers=h_buyer, json={
    "contractor_name": "ООО Реворк", "subject": "Черновой предмет",
})
rework_id = r.json()["id"]
r = client.post("/api/approvals/decide", headers=login("lawyer@t.co"),
                 json={"entity_type": "contract", "entity_id": rework_id, "decision": "Отклонено",
                       "comment": "Не хватает реквизитов"})
check(r.json()["status"] == "Отклонено", "договор отклонён")

# нельзя доработать не-инициатору
r = client.post(f"/api/contracts/{rework_id}/resubmit", headers=login("acc@t.co"),
                 json={"comment": "пробую чужое"})
check(r.status_code == 403, "доработать может только инициатор")

r = client.post(f"/api/contracts/{rework_id}/resubmit", headers=h_buyer,
                 json={"subject": "Исправленный предмет", "comment": "Добавил реквизиты"})
check(r.status_code == 200 and r.json()["revision"] == 2, f"доработка создала раунд 2: {r.json()}")

r = client.get(f"/api/contracts/{rework_id}", headers=h_buyer)
check(r.json()["contract"]["status"] == "На согласовании", "статус сброшен в 'На согласовании'")
check(r.json()["contract"]["subject"] == "Исправленный предмет", "предмет договора обновлён")
trail = r.json()["approvals"]
check(all(a["decision"] == "Ожидает" for a in trail if a["role"] == "Юрист"),
      "новый раунд начинается с чистого листа (Юрист снова 'Ожидает')")

# нельзя доработать документ, который не отклонён
r = client.post(f"/api/contracts/{rework_id}/resubmit", headers=h_buyer, json={"comment": "ещё раз"})
check(r.status_code == 400, "нельзя доработать документ, который уже не в статусе 'Отклонено'")

print("\nВСЕ ПРОВЕРКИ БЛОКА B ПРОШЛИ УСПЕШНО")
