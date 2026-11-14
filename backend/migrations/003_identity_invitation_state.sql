-- HU-13: estado compartido de cuenta e invitación para operaciones
-- procesadas por repositorios/instancias independientes.
CREATE TABLE IF NOT EXISTS identity_invitation_accounts (
    account_id              text PRIMARY KEY,
    company_id              text,
    name                    text NOT NULL,
    email                   text NOT NULL,
    phone                   text,
    role                    text NOT NULL,
    status                  text NOT NULL,
    invitation_status       text NOT NULL,
    password_hash           text,
    invitation_token_hash   text,
    invitation_expires_at   timestamptz,
    invitation_used_at      timestamptz,
    CONSTRAINT identity_invitation_accounts_status_check
        CHECK (status IN ('active', 'deactivated')),
    CONSTRAINT identity_invitation_accounts_invitation_status_check
        CHECK (invitation_status IN ('pending', 'accepted'))
);

CREATE UNIQUE INDEX IF NOT EXISTS identity_invitation_token_hash_unique
    ON identity_invitation_accounts (invitation_token_hash)
    WHERE invitation_token_hash IS NOT NULL;
