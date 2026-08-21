-- Применить на уже развёрнутой БД, где в таблице documents ещё нет doc_type.
-- При развороте с нуля этот файл не нужен — 001_init.sql уже включает doc_type.

alter table documents add column if not exists doc_type text;
