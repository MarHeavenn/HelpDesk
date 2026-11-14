-- HU-13: estados, invitaciones y compatibilidad de cuentas existentes.
-- Esta migracion se ejecuta despues de 001_init.sql. No modificar 001.

-- Las cuentas autorregistradas pueden existir sin tenant y las pendientes aún
-- no tienen credenciales. Las filas existentes se normalizan más abajo antes
-- de instalar las restricciones nuevas.
ALTER TABLE users
    ALTER COLUMN company_id DROP NOT NULL,
    ALTER COLUMN password_hash DROP NOT NULL;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_password_hash_not_blank;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS phone text,
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS invitation_status text NOT NULL DEFAULT 'accepted',
    ADD COLUMN IF NOT EXISTS invitation_token_hash text,
    ADD COLUMN IF NOT EXISTS invitation_expires_at timestamptz,
    ADD COLUMN IF NOT EXISTS invitation_used_at timestamptz;

-- Toda cuenta creada por 001 ya tenía credenciales y se considera aceptada;
-- no se rota ni se reescribe su hash, rol, empresa o estado activo.
UPDATE users
SET status = 'active', invitation_status = 'accepted'
WHERE invitation_status IS NULL;

ALTER TABLE users
    ADD CONSTRAINT users_role_check
        CHECK (role IN ('cliente', 'tecnico', 'supervisor', 'administrador')),
    ADD CONSTRAINT users_password_hash_not_blank
        CHECK (password_hash IS NULL OR btrim(password_hash) <> ''),
    ADD CONSTRAINT users_status_check
        CHECK (status IN ('active', 'deactivated')),
    ADD CONSTRAINT users_invitation_status_check
        CHECK (invitation_status IN ('pending', 'accepted')),
    ADD CONSTRAINT users_invitation_hash_check
        CHECK (
            (invitation_status = 'pending' AND password_hash IS NULL)
            OR (invitation_status = 'accepted' AND password_hash IS NOT NULL)
        );

CREATE UNIQUE INDEX IF NOT EXISTS users_invitation_token_hash_unique
    ON users (invitation_token_hash)
    WHERE invitation_token_hash IS NOT NULL;
