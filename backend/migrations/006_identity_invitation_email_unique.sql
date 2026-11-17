-- HU-19 R2: unicidad global del correo entre instancias (RF-135, criterio 7).
--
-- El almacén de cuentas (`identity_invitation_accounts`) no imponía unicidad
-- sobre el correo normalizado. Dos altas concurrentes (incluso en procesos o
-- instancias distintas) con el mismo correo de administrador inicial podían
-- crear dos cuentas y dos empresas. Esta migración añade un índice único
-- sobre `lower(email)`, que es la forma canónica en la que el repositorio
-- compara correos (`normalize_email`).
--
-- Duplicados heredados: si ya existen correos duplicados, la migración falla
-- deliberadamente con un mensaje que los identifica, sin elegir ni borrar
-- datos. La resolución de esos duplicados es una tarea manual previa; la
-- migración no modifica filas existentes ni aplica `ON CONFLICT`.

DO $$
DECLARE
    duplicated_emails text;
BEGIN
    SELECT string_agg(lower_email, ', ' ORDER BY lower_email)
    INTO duplicated_emails
    FROM (
        SELECT lower(email) AS lower_email
        FROM identity_invitation_accounts
        GROUP BY lower(email)
        HAVING count(*) > 1
    ) AS duplicates;

    IF duplicated_emails IS NOT NULL THEN
        RAISE EXCEPTION
            'correos duplicados en identity_invitation_accounts: %',
            duplicated_emails;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS identity_invitation_email_unique
    ON identity_invitation_accounts (lower(email));
