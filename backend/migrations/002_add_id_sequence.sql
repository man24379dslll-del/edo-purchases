-- Выполнить только если вы уже применяли 001_init.sql ДО того, как в него
-- добавили таблицу id_counters. Если разворачиваете БД с нуля — 001_init.sql
-- уже содержит эту таблицу, этот файл не нужен.

create table if not exists id_counters (
  name  text primary key,
  value bigint not null default 0
);
insert into id_counters (name, value) values ('global', 0)
  on conflict (name) do nothing;
