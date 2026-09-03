-- Применить на уже развёрнутой БД. При развороте с нуля не нужен —
-- 001_init.sql уже включает это изменение.

alter table users add column if not exists contractor_id text references contractors(id);
