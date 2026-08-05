-- ══════════════════════════════════════════════════════════════
-- ЭДО ЗАКУПОК — схема Supabase (Postgres)
-- Выполнить в Supabase SQL Editor (Project → SQL Editor → New query)
-- ══════════════════════════════════════════════════════════════

create extension if not exists "pgcrypto";

-- ─── РОЛИ ───
create type user_role as enum (
  'Админ','Инициатор','Закупщик','Маркетинг','Юрист',
  'Фин. директор','Директор','Бухгалтер','Склад'
);

-- ─── ПОЛЬЗОВАТЕЛИ ───
-- пароль хранится в виде bcrypt-хэша, авторизация делается своим FastAPI-бэкендом (JWT),
-- Supabase здесь используется как чистая Postgres БД.
create table users (
  email         text primary key,
  fio           text not null,
  role          user_role not null,
  password_hash text not null,
  is_active     boolean not null default true,
  created_at    timestamptz not null default now()
);

-- ─── ЮРЛИЦА ───
create table legal_entities (
  id         text primary key,
  name       text not null,
  inn        text,
  address    text
);

-- ─── КОНТРАГЕНТЫ ───
create table contractors (
  id             text primary key,
  name           text not null,
  inn            text,
  contact_person text,
  contact_phone  text,
  contact_email  text,
  status         text not null default 'Активен',
  created_at     timestamptz not null default now()
);
create index idx_contractors_inn on contractors(inn);

-- ─── ДОГОВОРЫ ───
create table contracts (
  id                text primary key,
  created_at        timestamptz not null default now(),
  initiator_email   text not null references users(email),
  initiator_fio     text not null,
  contractor_id     text not null references contractors(id),
  contractor_name   text not null,
  contractor_inn    text,
  legal_entity_id   text references legal_entities(id),
  legal_entity_name text,
  subject           text not null,
  contract_number   text,
  limit_amount      numeric(16,2) default 0,
  status            text not null default 'На согласовании',
  needs_marketing   boolean not null default false,
  valid_until       date,
  comment           text,
  file_url          text,
  revision          int not null default 1
);
create index idx_contracts_status on contracts(status);
create index idx_contracts_contractor on contracts(contractor_id);

create table contract_items (
  id          text primary key,
  contract_id text not null references contracts(id) on delete cascade,
  name        text not null,
  price       numeric(16,2) not null default 0,
  unit        text,
  created_at  timestamptz not null default now(),
  created_by  text references users(email)
);

create table contract_files (
  id          text primary key,
  contract_id text not null references contracts(id) on delete cascade,
  file_name   text not null,
  file_url    text not null,
  upload_date timestamptz not null default now(),
  uploaded_by text references users(email)
);

-- ─── ДОП. СОГЛАШЕНИЯ ───
create table amendments (
  id               text primary key,
  created_at       timestamptz not null default now(),
  initiator_email  text not null references users(email),
  initiator_fio    text not null,
  contract_id      text not null references contracts(id),
  contractor_name  text,
  subject          text not null,
  status           text not null default 'На согласовании',
  needs_marketing  boolean not null default false,
  comment          text,
  file_url         text,
  revision         int not null default 1
);

-- ─── ЗАКУПКИ ───
create table purchases (
  id               text primary key,
  created_at       timestamptz not null default now(),
  initiator_email  text not null references users(email),
  initiator_fio    text not null,
  contract_id      text references contracts(id),
  contractor_name  text,
  purchase_type    text,
  subcategory      text,
  subject          text not null,
  quantity         numeric(16,3) not null default 0,
  price_per_unit   numeric(16,2) not null default 0,
  amount           numeric(16,2) not null default 0,
  status           text not null default 'На согласовании',
  comment          text,
  file_url         text,
  execution_status text default 'Не исполнено',
  execution_date   timestamptz,
  revision         int not null default 1
);
create index idx_purchases_status on purchases(status);
create index idx_purchases_contract on purchases(contract_id);

create table receipts (
  id           text primary key,
  purchase_id  text not null references purchases(id) on delete cascade,
  date         timestamptz not null default now(),
  user_email   text references users(email),
  user_fio     text,
  quantity     numeric(16,3) not null,
  comment      text
);

create table payments (
  id            text primary key,
  purchase_id   text not null references purchases(id) on delete cascade,
  date          timestamptz not null default now(),
  user_email    text references users(email),
  user_fio      text,
  amount        numeric(16,2) not null,
  payment_type  text,
  payment_form  text,
  comment       text
);

-- ─── СОГЛАСОВАНИЯ (маршруты) ───
create table approvals (
  approval_id   text primary key,
  entity_type   text not null,       -- contract | purchase | amendment
  entity_id     text not null,
  stage         int not null,        -- индекс этапа в цепочке
  approver_role text not null,       -- роль, которая должна согласовать (либо конкретный approver_email)
  approver_email text,
  decision      text not null default 'Ожидает', -- Ожидает | Согласовано | Отклонено
  decision_date timestamptz,
  comment       text,
  created_at    timestamptz not null default now(),
  activated_at  timestamptz,         -- когда этап стал активным (для отсчёта SLA)
  deadline      timestamptz,         -- activated_at + SLA часов для роли
  escalated     boolean not null default false,
  revision      int not null default 1,  -- номер раунда согласования (растёт при доработке после отклонения)
  signature     text,
  state         text not null default 'active'  -- active | done | skipped
);
create index idx_approvals_entity on approvals(entity_type, entity_id);
create index idx_approvals_approver on approvals(approver_email);
create index idx_approvals_deadline on approvals(deadline) where state = 'active';

-- ─── ЛОГ ───
create table log_entries (
  id          bigserial primary key,
  timestamp   timestamptz not null default now(),
  user_email  text,
  role        text,
  action      text not null,
  entity_type text,
  entity_id   text,
  comment     text
);
create index idx_log_entity on log_entries(entity_type, entity_id);

-- ─── ДЕЛЕГИРОВАНИЕ СОГЛАСОВАНИЯ ───
-- Позволяет замещать согласующего на время (отпуск/болезнь), не меняя ему роль.
create table delegations (
  id              text primary key,
  delegator_email text not null references users(email),  -- кого замещают
  delegator_role  text not null,                            -- фиксируем роль на момент создания
  delegate_email  text not null references users(email),   -- кто замещает
  starts_at       timestamptz not null,
  ends_at         timestamptz not null,
  comment         text,
  created_by      text references users(email),
  created_at      timestamptz not null default now()
);
create index idx_delegations_active on delegations(delegate_email, starts_at, ends_at);

-- ─── ГЕНЕРАЦИЯ ЧЕЛОВЕКОЧИТАЕМЫХ ID ───
-- Общий атомарный счётчик для всех сущностей (ДОГ-2026-000123 и т.д.).
-- Инкремент делается через SELECT ... FOR UPDATE на единственной строке —
-- атомарно и без дублей даже при параллельных запросах на создание документов.
create table id_counters (
  name  text primary key,
  value bigint not null default 0
);
insert into id_counters (name, value) values ('global', 0);

-- ─── СИД: юрлица-примеры ───
insert into legal_entities (id, name, inn, address) values
  ('ЮЛ-001', 'ООО Компания 1', '7701234567', ''),
  ('ЮЛ-002', 'ООО Компания 2', '7709876543', '');

-- ─── СИД: первый админ (пароль: admin123, поменяйте сразу после первого входа) ───
-- хэш сгенерирован bcrypt для 'admin123'
insert into users (email, fio, role, password_hash) values
  ('admin@example.com', 'Администратор', 'Админ', '$2b$12$cYtuiwRlj1vygk5MOORXR.KXAz6c.Qz1E0qtIz6V2pViAxOq9KPMO');
