"""
Проверка гонки состояний: создаём договор, где на первом этапе два параллельных
согласующих (Юрист + Маркетинг), и решаем за них ОДНОВРЕМЕННО из разных потоков.
Без блокировки строк это иногда приводит к тому, что этап "Фин. директор"
открывается дважды или не открывается вовсе. С блокировкой — результат
детерминирован при любом количестве повторов.
"""
import sys
sys.path.insert(0, ".")

import os
import tempfile
import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app import models
from app.auth import hash_password
from app.main import app

# Файловая БД (не :memory:) с обычным пулом соединений — каждый поток получает
# своё соединение, и SQLite сериализует конкурентные транзакции на уровне файла.
# Это ближе к реальному поведению под нагрузкой, чем один общий in-memory коннекшн.
db_path = os.path.join(tempfile.mkdtemp(), "concurrency_test.db")
engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 30})
TestSession = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

db = TestSession()
for email, role in {"buyer@t.co": "Закупщик", "lawyer@t.co": "Юрист", "mkt@t.co": "Маркетинг",
                     "findir@t.co": "Фин. директор", "acc@t.co": "Бухгалтер"}.items():
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


h_buyer = login("buyer@t.co")

RUNS = 20
double_advance = 0
never_advance = 0

for i in range(RUNS):
    r = client.post("/api/contracts", headers=h_buyer, json={
        "contractor_name": f"Контрагент {i}", "subject": "Тест гонки", "needs_marketing": True,
    })
    contract_id = r.json()["id"]

    results = {}

    def approve(email, role):
        r = client.post("/api/approvals/decide", headers=login(email),
                         json={"entity_type": "contract", "entity_id": contract_id, "decision": "Согласовано"})
        results[role] = r

    t1 = threading.Thread(target=approve, args=("lawyer@t.co", "Юрист"))
    t2 = threading.Thread(target=approve, args=("mkt@t.co", "Маркетинг"))
    t1.start(); t2.start()
    t1.join(); t2.join()

    for role, r in results.items():
        if r.status_code != 200:
            print(f"  ! запрос {role} завершился ошибкой {r.status_code}: {r.text[:200]}")

    r = client.get(f"/api/contracts/{contract_id}", headers=h_buyer)
    approvals = r.json()["approvals"]
    active_count = sum(1 for a in approvals if a["role"] == "Фин. директор" and a["state"] == "active")
    if active_count > 1:
        double_advance += 1
    if active_count == 0:
        never_advance += 1

print(f"Прогонов: {RUNS}")
print(f"Этап 'Фин. директор' открылся дважды: {double_advance}")
print(f"Этап 'Фин. директор' не открылся вовсе: {never_advance}")

if double_advance == 0 and never_advance == 0:
    print("\n[OK] Блокировка строк работает — гонок не обнаружено")
else:
    print("\n[FAIL] Обнаружена гонка состояний!")
    raise SystemExit(1)
