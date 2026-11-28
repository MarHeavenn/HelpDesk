-- HU-26 A2: users sera el registro canonico compatible con las FK de tickets.
-- No cambia claves, hashes, estados ni migraciones previas. La tabla operativa
-- anterior se conserva para la transicion de los adaptadores A3-A5.
-- El runner aplica todo este archivo y su registro de version en una transaccion.
-- No desplegar parcialmente A2-A5 sobre la aplicacion activa.

-- Impedir escrituras entre la comprobacion y la copia; permitir lecturas.
-- Si hay actividad incompatible, fallar sin esperar ni modificar datos.
LOCK TABLE companies IN SHARE MODE NOWAIT;
LOCK TABLE users, identity_invitation_accounts IN SHARE ROW EXCLUSIVE MODE NOWAIT;

DO $$
BEGIN
    -- Validar antes de convertir: no generar UUID nuevos para cuentas heredadas.
    IF EXISTS (
        SELECT 1 FROM identity_invitation_accounts
        WHERE account_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
           OR (company_id IS NOT NULL AND
               company_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    ) THEN
        RAISE EXCEPTION 'HU26 reconciliation: incompatible account or company identifier'
            USING ERRCODE = '23514';
    END IF;

    -- Textos distintos no pueden colapsar en el mismo UUID al convertirlos.
    IF EXISTS (
        SELECT account_id::uuid FROM identity_invitation_accounts
        GROUP BY account_id::uuid HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'HU26 reconciliation: duplicate normalized account identifier'
            USING ERRCODE = '23514';
    END IF;

    IF EXISTS (
        SELECT 1 FROM identity_invitation_accounts AS a
        WHERE a.company_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM companies AS c WHERE c.id = a.company_id::uuid
          )
    ) THEN
        RAISE EXCEPTION 'HU26 reconciliation: account references a missing company'
            USING ERRCODE = '23514';
    END IF;

    -- La tabla operativa antigua admite combinaciones que users no admite.
    -- No reparar esas combinaciones inventando credenciales o aceptaciones.
    IF EXISTS (
        SELECT 1 FROM identity_invitation_accounts
        WHERE btrim(name) = '' OR btrim(email) = ''
           OR role NOT IN ('cliente', 'tecnico', 'supervisor', 'administrador')
           OR (invitation_status = 'accepted' AND
               (password_hash IS NULL OR btrim(password_hash) = ''))
           OR (invitation_status = 'pending' AND password_hash IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'HU26 reconciliation: incompatible account credentials or fields'
            USING ERRCODE = '23514';
    END IF;

    -- No escoger una de dos cuentas con el mismo correo, ni sobrescribir
    -- versiones divergentes del mismo ID. Comparacion nula-segura de todos
    -- los campos persistidos, incluidas fechas e invitacion.
    IF EXISTS (
        SELECT 1
        FROM identity_invitation_accounts AS a
        JOIN users AS u
          ON u.id = a.account_id::uuid OR lower(u.email) = lower(a.email)
        WHERE ROW(
            u.id, u.company_id, u.name, u.email, u.phone, u.role, u.status,
            u.invitation_status, u.password_hash, u.invitation_token_hash,
            u.invitation_expires_at, u.invitation_used_at, u.created_at
        ) IS DISTINCT FROM ROW(
            a.account_id::uuid, a.company_id::uuid, a.name, a.email, a.phone,
            a.role, a.status, a.invitation_status, a.password_hash,
            a.invitation_token_hash, a.invitation_expires_at,
            a.invitation_used_at, a.created_at
        )
    ) THEN
        -- No incluir hashes, tokens ni valores de cuentas en el diagnostico.
        RAISE EXCEPTION 'HU26 reconciliation: conflicting canonical and operational accounts'
            USING ERRCODE = '23514';
    END IF;

    -- La validacion completa precede cualquier insercion. Las filas canonicas
    -- existentes quedan intactas; no se elimina ni actualiza ninguna cuenta.
    INSERT INTO users (
        id, company_id, name, email, phone, role, status, invitation_status,
        password_hash, invitation_token_hash, invitation_expires_at,
        invitation_used_at, created_at
    )
    SELECT
        a.account_id::uuid, a.company_id::uuid, a.name, a.email, a.phone,
        a.role, a.status, a.invitation_status, a.password_hash,
        a.invitation_token_hash, a.invitation_expires_at,
        a.invitation_used_at, a.created_at
    FROM identity_invitation_accounts AS a
    WHERE NOT EXISTS (SELECT 1 FROM users AS u WHERE u.id = a.account_id::uuid);
END $$;
