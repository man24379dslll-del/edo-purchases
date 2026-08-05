# ЭДО Закупок — Supabase + Python (FastAPI) + React + Railway

Полный перенос системы электронного документооборота закупок с Google Apps Script /
Google Sheets на современный стек:

| Было | Стало |
|---|---|
| Google Sheets | **Supabase (Postgres)** |
| Code.gs (Apps Script) | **Python / FastAPI** (backend) |
| Index.html + google.script.run | **React + Vite** (frontend), fetch к REST API |
| — | **GitHub** (репозиторий) + **Railway** (хостинг backend и frontend) |

Бизнес-логика (маршруты согласования договоров/закупок, роли, ОСВ, поступления/платежи)
перенесена как есть — см. `backend/app/services/workflow.py`.

## Структура репозитория

```
edo/
├── backend/            # FastAPI API
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py         # SQLAlchemy-модели
│   │   ├── schemas.py        # Pydantic-схемы
│   │   ├── auth.py           # JWT-аутентификация
│   │   ├── services/workflow.py  # маршруты согласования (портировано из Code.gs)
│   │   └── routers/          # эндпоинты API
│   ├── migrations/001_init.sql   # схема БД для Supabase
│   ├── requirements.txt
│   ├── railway.json
│   └── .env.example
└── frontend/           # React + Vite SPA
    ├── src/
    ├── railway.json
    └── .env.example
```

## 1. Supabase (база данных)

1. Зарегистрируйтесь на [supabase.com](https://supabase.com) → **New Project**.
2. Дождитесь создания проекта, затем откройте **SQL Editor → New query**.
3. Скопируйте содержимое `backend/migrations/001_init.sql` и выполните (Run).
   Это создаст все таблицы и добавит:
   - тестового администратора: `admin@example.com` / `admin123` (**смените пароль сразу после первого входа**);
   - два примера юрлиц.
4. Перейдите в **Project Settings → Database → Connection string → URI**,
   выберите режим **Connection pooling (Transaction)** (порт 6543) — он лучше подходит для serverless/контейнерных окружений вроде Railway.
   Скопируйте строку — это будет `DATABASE_URL`.

## 2. Backend (Railway)

1. Локально:
   ```bash
   cd backend
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # впишите DATABASE_URL и JWT_SECRET
   uvicorn app.main:app --reload
   ```
   API поднимется на `http://localhost:8000`, документация — `http://localhost:8000/docs`.

2. Деплой на Railway:
   - [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo** → выберите репозиторий, каталог `backend`.
   - Railway распознает `railway.json`/`Procfile` и соберёт проект через Nixpacks.
   - В **Variables** добавьте:
     - `DATABASE_URL` — строка из Supabase (шаг 1.4)
     - `JWT_SECRET` — случайная строка (`python -c "import secrets; print(secrets.token_hex(32))"`)
     - `CORS_ORIGINS` — домен фронтенда после его деплоя (шаг 3), через запятую если их несколько
   - Deploy. Проверьте `https://<ваш-backend>.up.railway.app/api/health` → `{"status":"ok"}`.

## 3. Frontend (Railway)

1. Локально:
   ```bash
   cd frontend
   npm install
   cp .env.example .env.local   # укажите VITE_API_URL = адрес backend из шага 2
   npm run dev
   ```
2. Деплой на Railway:
   - **New Project → Deploy from GitHub repo**, каталог `frontend`.
   - Переменная окружения `VITE_API_URL` = URL backend-сервиса на Railway.
   - Railway выполнит `npm run build`, затем `npm run start` (раздаёт `dist/` через `serve`).
   - После деплоя обновите `CORS_ORIGINS` в backend-сервисе на реальный URL фронтенда.

## 4. GitHub

Репозиторий уже инициализирован (`git init`) в этой директории. Чтобы запушить:

```bash
git add -A
git commit -m "ЭДО Закупок: миграция на Supabase + FastAPI + React"
git branch -M main
git remote add origin https://github.com/<ваш-логин>/<репозиторий>.git
git push -u origin main
```

Для автоматизации создания репозитория и пуша от вашего имени понадобится
**GitHub Personal Access Token** (scope `repo`) — сообщите его отдельно (не в общий чат,
а через переменные окружения/секреты), и это можно сделать одной командой через `gh` CLI
или `git push` с токеном в URL.

## Роли и маршруты согласования (без изменений от исходной системы)

- **Договор**: Закупщик создаёт → Юрист + Маркетинг (параллельно, Маркетинг опционален) →
  Фин. директор → Бухгалтер (финал).
- **Закупка**: Инициатор создаёт → Маркетинг → Директор → Закупщик (финал, исполняет).
- **Доп. соглашение**: та же цепочка, что и договор.
- Роли: Админ, Инициатор, Закупщик, Маркетинг, Юрист, Фин. директор, Директор, Бухгалтер, Склад.
- ОСВ доступна только ролям «Фин. директор» и «Админ».
- Администрирование пользователей/юрлиц — только роли «Директор» (и «Админ»).

## SLA и эскалация

Каждый активный этап согласования получает дедлайн (по умолчанию 48ч, для Фин. директора/
Бухгалтера/Директора — 24ч, см. `DEFAULT_SLA_HOURS` в `backend/app/services/workflow.py`).

`POST /api/approvals/check-overdue` (доступен роли «Директор») находит просроченные этапы,
помечает их эскалированными и уведомляет директоров по email. На странице
«Мои согласования» у Директора есть кнопка ручного запуска этой проверки.

Для автоматического запуска по расписанию (а не только вручную) настройте одно из:
- **Railway Cron** (Cron Jobs в настройках сервиса) → `curl -X POST https://<backend>/api/approvals/check-overdue` с сервисным токеном раз в час;
- **APScheduler** внутри самого FastAPI-приложения (добавить в `app/main.py` при старте).

## Делегирование

Любой пользователь может передать свою роль другому сотруднику на период (страница
«Делегирование» в интерфейсе) — например, на время отпуска. Замещающий видит и может
согласовывать документы «за» замещаемого, не получая его роль насовсем.

## Доработка отклонённых документов

Если документ отклонён, его инициатор может исправить поля и отправить его на новый круг
согласования кнопкой «Доработать и отправить заново» в карточке договора/закупки. Прежние
раунды согласования сохраняются в истории — ничего не удаляется.

## Email-уведомления

Настраиваются переменными окружения `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
`SMTP_FROM`, `APP_BASE_URL` (см. `backend/.env.example`). Без `SMTP_HOST` уведомления просто
не отправляются — остальная система работает как обычно.

## Тесты

В `backend/` лежат три сценарных теста (на sqlite, реальная БД не нужна):
```bash
cd backend
python3 smoke_test.py        # сквозной сценарий: договор → закупка → платежи → ОСВ → экспорт
python3 concurrency_test.py  # проверка блокировок при параллельном согласовании
python3 block_b_test.py      # SLA/эскалация, делегирование, доработка отклонённых документов
```

## Что дальше можно улучшить

- Загрузка файлов договоров/закупок — сейчас поле `file_url` принимает произвольную ссылку;
  для полноценной загрузки файлов стоит подключить **Supabase Storage** (S3-совместимое хранилище).
- Row Level Security в Supabase, если понадобится прямой доступ к БД помимо backend.
- Alembic вместо ручных SQL-миграций, пагинация списков, rate limiting на login, refresh-токены.
