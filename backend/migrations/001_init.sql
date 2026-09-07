-- ══════════════════════════════════════════════════════════════
-- ЭДО ДОГОВОРОВ — схема Supabase/Railway (Postgres)
-- Выполнить в SQL Editor (Supabase) или через psql-консоль (Railway)
-- ══════════════════════════════════════════════════════════════

create extension if not exists "pgcrypto";

-- ─── ПОЛЬЗОВАТЕЛИ ───
-- role — обычный текст (не Postgres enum): список ролей меняется на уровне
-- Python-кода (ALL_ROLES в app/models.py), so enum only adds migration pain
-- when the role list changes, as it just did.
create table users (
  email         text primary key,
  fio           text not null,
  role          text not null,
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

-- Логин для портала контрагента — заполняется только для role='Контрагент'.
-- Добавляем через ALTER, а не сразу в CREATE TABLE users, т.к. на момент
-- создания users таблицы contractors ещё не существует.
alter table users add column contractor_id text references contractors(id);

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
  price_per_unit    numeric(16,2) default 0,
  amount            numeric(16,2),  -- сумма договора; NULL допустим для длительных договоров без известной цены
  category          text not null default 'Прочее',
  contract_type     text not null default 'Системный',  -- 'Системный' | 'Разовая закупка'
  approval_tier     int,  -- 1 или 2, вычисляется при создании (см. app/services/workflow.determine_tier)
  status            text not null default 'На согласовании',
  valid_until       date,
  comment           text,
  file_url          text
);
create index idx_contracts_status on contracts(status);
create index idx_contracts_contractor on contracts(contractor_id);

-- ─── СОГЛАСОВАНИЯ ───
-- Маршрут строится ЦЕЛИКОМ сразу при создании договора, по уровню (approval_tier):
--   уровень 1: Юрист → Бухгалтер → Директор
--   уровень 2: только Директор
create table approvals (
  approval_id    text primary key,
  contract_id    text not null references contracts(id) on delete cascade,
  stage          int not null,
  approver_role  text not null,
  approver_email text,
  decision       text not null default 'Ожидает',
  decision_date  timestamptz,
  comment        text,
  created_at     timestamptz not null default now(),
  state          text not null default 'active'  -- active | pending | done
);
create index idx_approvals_contract on approvals(contract_id);
create index idx_approvals_role_state on approvals(approver_role, state);

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

-- ─── ГЕНЕРАЦИЯ ЧЕЛОВЕКОЧИТАЕМЫХ ID ───
create table id_counters (
  name  text primary key,
  value bigint not null default 0
);
insert into id_counters (name, value) values ('global', 0);

-- ─── ХРАНИЛИЩЕ ДОКУМЕНТОВ (реестр загруженных файлов) ───
create table documents (
  id              text primary key,
  stored_filename text not null unique,
  original_name   text not null,
  url             text not null,
  size_bytes      bigint,
  uploaded_by     text references users(email),
  uploaded_at     timestamptz not null default now(),
  entity_type     text,
  entity_id       text,
  entity_subject  text,
  doc_type        text
);
create index idx_documents_entity on documents(entity_type, entity_id);
create index idx_documents_uploaded_by on documents(uploaded_by);
create index idx_documents_uploaded_at on documents(uploaded_at desc);

-- ─── ПЛАТЁЖНЫЙ КАЛЕНДАРЬ ───
create table payment_schedule (
  id          text primary key,
  contract_id text not null references contracts(id) on delete cascade,
  due_date    date not null,
  amount      numeric(16,2) not null,
  status      text not null default 'Запланирован',  -- 'Запланирован' | 'Оплачен'
  comment     text,
  created_by  text references users(email),
  created_at  timestamptz not null default now(),
  paid_at     timestamptz
);
create index idx_payment_schedule_due_date on payment_schedule(due_date);
create index idx_payment_schedule_contract on payment_schedule(contract_id);

-- ─── СИД: юрлица-примеры ───
insert into legal_entities (id, name, inn, address) values
  ('ЮЛ-001', 'ООО Компания 1', '7701234567', ''),
  ('ЮЛ-002', 'ООО Компания 2', '7709876543', '');

-- ─── СИД: первый админ (пароль: admin123, поменяйте сразу после первого входа) ───
insert into users (email, fio, role, password_hash) values
  ('admin@example.com', 'Администратор', 'Админ', '$2b$12$cYtuiwRlj1vygk5MOORXR.KXAz6c.Qz1E0qtIz6V2pViAxOq9KPMO');
