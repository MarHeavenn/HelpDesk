# Runbook — `006_identity_invitation_email_unique.sql`

## Qué hace la migración

Añade el índice único `identity_invitation_email_unique` sobre
`identity_invitation_accounts (lower(email))`, la misma forma canónica con la
que el repositorio compara correos (`normalize_email`). Cierra la carrera de
dos altas concurrentes con el mismo correo de administrador inicial, incluso
entre procesos o instancias distintas (HU-19 RF-135, criterio 7).

La migración **no** modifica filas ni aplica `ON CONFLICT`. Si ya existen
correos duplicados (ignorando mayúsculas), falla deliberadamente con
`correos duplicados en identity_invitation_accounts: <lista>` y el esquema
queda intacto. Los duplicados se resuelven manualmente antes de reintentarla.

## 1. Detectar duplicados heredados

```sql
SELECT lower(email) AS email_normalizado,
       array_agg(account_id ORDER BY created_at) AS cuentas,
       array_agg(email ORDER BY created_at)        AS correos_originales,
       count(*)                                   AS total
FROM identity_invitation_accounts
GROUP BY lower(email)
HAVING count(*) > 1
ORDER BY lower(email);
```

Sin resultados (0 filas) no hay nada que resolver: se puede reejecutar la
migración. Con resultados, cada fila son las cuentas que comparten correo
normalizado (pueden diferir solo en mayúsculas o espacios periféricos).

Para ver el detalle de cada cuenta implicada (empresa, rol, estado e
invitación) sin exponer hashes ni tokens:

```sql
SELECT account_id, name, email, role, company_id, status,
       invitation_status, created_at
FROM identity_invitation_accounts
WHERE lower(email) IN (
    SELECT lower(email)
    FROM identity_invitation_accounts
    GROUP BY lower(email)
    HAVING count(*) > 1
)
ORDER BY lower(email), created_at, account_id;
```

## 2. Resolverlos manualmente

Para cada grupo, decidir cuál cuenta **conserva** el correo y qué pasa con las
demás. No hay una regla automática: se elige según quién debe poder iniciar
sesión y qué historial conviene mantener.

1. **Cuenta que conserva el correo**: no se toca (o se normaliza a minúsculas
   con `lower(btrim(email))`); si está `pending`, conviene reenviar o completar
   su aceptación por el flujo normal de invitaciones.
2. **Otras cuentas**: se les asigna un correo distinto y válido (el de la
   persona o el de su empresa) con
   `UPDATE identity_invitation_accounts SET email = ... WHERE account_id = ...;`
   o se desactivan con
   `UPDATE identity_invitation_accounts SET status = 'deactivated' WHERE account_id = ...;`
   (desactivar no borra historial y sigue exigiendo correo único).
3. Nunca borrar cuentas para “ganar” unicidad: la historia y los tickets
   referencian esos `account_id`. Si hiciera falta un borrado, es una decisión
   aparte, fuera de este runbook.
4. Repetir la consulta del apartado 1 hasta que devuelva 0 filas.

Todos los cambios se hacen en una transacción (`BEGIN; … COMMIT;`) y se
verifican después de commitear.

## 3. Reejecutar la migración

El runner es idempotente y solo aplica versiones no registradas en
`schema_migrations`:

```powershell
$env:DATABASE_URL="postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk"
python backend\migrations\run.py
```

Si `006` falló, no quedó registrada y se reintenta desde el inicio (tras
resolver los duplicados). Comprobar el índice:

```sql
\d identity_invitation_accounts
-- debe listar: "identity_invitation_email_unique" UNIQUE, btree (lower(email))
```

Verificación de comportamiento: `cd backend` y
`python -m pytest tests/test_database_integration.py -q` (las pruebas de base
de datos se omiten sin `DATABASE_URL`).

> Este documento no contiene secretos ni datos reales; los ejemplos usan
> marcadores genéricos.
