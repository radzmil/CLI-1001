-- Apply to the portal's existing PostgreSQL clients table before enabling profile writes.
BEGIN;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS bot_name VARCHAR(100);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS display_name VARCHAR(150);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS email VARCHAR(254);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS portal_password_hash TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS logo_data BYTEA;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS logo_mime VARCHAR(20);
COMMIT;