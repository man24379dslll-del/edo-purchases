-- Применить, если 001_init.sql был выполнен ДО добавления SLA/делегирования/
-- доработки отклонённых документов. При развороте с нуля этот файл не нужен —
-- всё уже включено в 001_init.sql.

alter table approvals add column if not exists activated_at timestamptz;
alter table approvals add column if not exists deadline timestamptz;
alter table approvals add column if not exists escalated boolean not null default false;
alter table approvals add column if not exists revision int not null default 1;
create index if not exists idx_approvals_deadline on approvals(deadline) where state = 'active';

alter table contracts add column if not exists revision int not null default 1;
alter table purchases add column if not exists revision int not null default 1;
alter table amendments add column if not exists revision int not null default 1;

create table if not exists delegations (
  id              text primary key,
  delegator_email text not null references users(email),
  delegator_role  text not null,
  delegate_email  text not null references users(email),
  starts_at       timestamptz not null,
  ends_at         timestamptz not null,
  comment         text,
  created_by      text references users(email),
  created_at      timestamptz not null default now()
);
create index if not exists idx_delegations_active on delegations(delegate_email, starts_at, ends_at);
