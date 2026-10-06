-- Apply to the portal's existing PostgreSQL clients table before enabling profile writes.
BEGIN;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS bot_name VARCHAR(100);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS display_name VARCHAR(150);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS email VARCHAR(254);
COMMIT;