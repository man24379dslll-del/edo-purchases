-- Применить на уже развёрнутой БД. При развороте с нуля не нужен —
-- 001_init.sql уже включает все эти изменения.

alter table contracts add column if not exists amount numeric(16,2);
alter table contracts add column if not exists category text not null default 'Прочее';
alter table contracts add column if not exists contract_type text not null default 'Системный';
alter table contracts add column if not exists approval_tier int;
alter table contracts drop column if exists is_standard;

create table if not exists payment_schedule (
  id          text primary key,
  contract_id text not null references contracts(id) on delete cascade,
  due_date    date not null,
  amount      numeric(16,2) not null,
  status      text not null default 'Запланирован',
  comment     text,
  created_by  text references users(email),
  created_at  timestamptz not null default now(),
  paid_at     timestamptz
);
create index if not exists idx_payment_schedule_due_date on payment_schedule(due_date);
create index if not exists idx_payment_schedule_contract on payment_schedule(contract_id);
