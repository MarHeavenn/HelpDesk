# Migraciones PostgreSQL (TSK-025)

Runner minimo en Python que aplica los archivos `NNN_*.sql` en orden y
registra cada version en `schema_migrations`. Es idempotente: ejecutarlo
dos veces no repite migraciones ya aplicadas.

## 1. Configurar el entorno

```powershell
Copy-Item infra\env.example infra\.env
```

Ajusta `infra/.env` si quieres otras credenciales o puerto. No subas ese
archivo a git.

## 2. Arrancar PostgreSQL

```powershell
cd infra
docker compose up -d
docker compose ps
```

El contenedor debe quedar `healthy`. El volumen `pgdata` conserva los
datos al detener o recrear el contenedor.

## 3. Aplicar las migraciones

Desde la raiz del repositorio:

```powershell
$env:DATABASE_URL="postgresql://helpdesk:helpdesk_dev@127.0.0.1:5432/helpdesk"
backend\.venv\Scripts\python.exe backend\migrations\run.py
```

Si cambiaste `POSTGRES_PORT` (por ejemplo porque el 5432 ya esta ocupado
por un PostgreSQL local), usa ese mismo puerto en la URL.

Alternativa usando las variables de Compose:

```powershell
$env:POSTGRES_PASSWORD="helpdesk_dev"
backend\.venv\Scripts\python.exe backend\migrations\run.py
```

## 4. Comprobar

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_database_integration.py -q
```

Las pruebas se saltan si PostgreSQL no esta disponible. Usa
`SKIP_DB_TESTS=1` para omitirlas explicitamente.

## 5. Detener y recrear sin perder datos

```powershell
cd infra
docker compose stop
docker compose up -d
docker compose down
docker compose up -d
```

`docker compose down` sin `-v` no elimina el volumen. Si se usa `-v`, se
borran los datos a proposito.

## Variables de entorno

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | URL completa de conexion (tiene prioridad). |
| `POSTGRES_USER` | Usuario de PostgreSQL (por defecto `helpdesk`). |
| `POSTGRES_PASSWORD` | Obligatoria si no se define `DATABASE_URL`. |
| `POSTGRES_DB` | Base de datos (por defecto `helpdesk`). |
| `POSTGRES_HOST` | Host (por defecto `127.0.0.1`). |
| `POSTGRES_PORT` | Puerto (por defecto `5432`). |

## Multitenancy

Todas las consultas de `app/infrastructure/db.py` reciben `company_id` y
lo aplican en el `WHERE`. Ese valor debe salir de la sesion autenticada,
nunca del cuerpo de la peticion. Ademas del filtro, la base de datos
impide mezclar empresas mediante claves foraneas compuestas y triggers:

- `tickets (company_id, requester_id)` y `tickets (company_id, assignee_id)`
  referencian `users (company_id, id)`.
- `ticket_comments` valida que el autor y el ticket sean de la misma empresa.
- `ticket_sla` y `ticket_comments` resuelven la empresa a traves del ticket.
