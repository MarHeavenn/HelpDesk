-- HU-19: gestion de empresas clientes (RF-126, RF-128 y RF-139).
-- Se aplica despues de 001_init.sql, 002_identity_accounts.sql y
-- 003_identity_invitation_state.sql. No modifica migraciones previas.
--
-- D-2: la unicidad del nombre se resuelve en la aplicacion con un bloqueo
-- transaccional por forma normalizada. El indice de esta migracion es NO
-- unico porque las empresas heredadas pueden tener nombres duplicados.

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS email text,
    ADD COLUMN IF NOT EXISTS phone text,
    ADD COLUMN IF NOT EXISTS contact_name text,
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS name_normalized text;

-- Toda empresa preexistente queda en estado active (RF-139).
UPDATE companies
SET status = 'active'
WHERE status IS NULL;

-- Forma normalizada de RF-128: recorte, NFC y minusculas. Se conserva el
-- nombre original y no se renombra ninguna empresa heredada.
UPDATE companies
SET name_normalized = lower(normalize(btrim(name), NFC))
WHERE name_normalized IS NULL;

ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_status_check;
ALTER TABLE companies
    ADD CONSTRAINT companies_status_check
        CHECK (status IN ('active', 'inactive'));

-- Indice NO unico, solo para localizar candidatos a duplicado (D-2).
CREATE INDEX IF NOT EXISTS companies_name_normalized_idx
    ON companies (name_normalized);
