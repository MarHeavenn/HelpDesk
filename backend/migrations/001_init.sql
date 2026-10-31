-- DeskHelp - esquema inicial multitenant (TSK-025)
--
-- Una unica base de datos y un unico conjunto de tablas para todas las
-- empresas. La separacion logica se hace con company_id en las tablas que
-- pertenecen a una empresa (users, tickets y sla_policies). Las tablas
-- ticket_sla y ticket_comments heredan la empresa a traves de su ticket.
--
-- Este archivo no abre transaccion: el runner (run.py) aplica cada
-- migracion dentro de una transaccion. Para ejecutarlo a mano con psql,
-- usa `psql -1 -f 001_init.sql`.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- companies
-- ---------------------------------------------------------------------------
CREATE TABLE companies (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT companies_name_not_blank CHECK (btrim(name) <> '')
);

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
-- El email es unico a nivel global: el login actual identifica al usuario
-- solo por email, sin conocer la empresa.
CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
    name          text NOT NULL,
    email         text NOT NULL,
    password_hash text NOT NULL,
    role          text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT users_email_not_blank CHECK (btrim(email) <> ''),
    CONSTRAINT users_password_hash_not_blank CHECK (btrim(password_hash) <> ''),
    CONSTRAINT users_role_check CHECK (role IN ('cliente', 'tecnico', 'administrador')),
    -- Necesaria para las claves foraneas compuestas de tickets.
    CONSTRAINT users_company_id_id_unique UNIQUE (company_id, id)
);

CREATE UNIQUE INDEX users_email_lower_unique ON users (lower(email));
CREATE INDEX users_company_id_idx ON users (company_id);

-- ---------------------------------------------------------------------------
-- Catalogos compartidos
-- ---------------------------------------------------------------------------
CREATE TABLE priorities (
    name       text PRIMARY KEY,
    sort_order smallint NOT NULL UNIQUE,
    CONSTRAINT priorities_name_not_blank CHECK (btrim(name) <> '')
);

CREATE TABLE statuses (
    name       text PRIMARY KEY,
    sort_order smallint NOT NULL UNIQUE,
    CONSTRAINT statuses_name_not_blank CHECK (btrim(name) <> '')
);

INSERT INTO priorities (name, sort_order) VALUES
    ('Crítica', 1),
    ('Alta', 2),
    ('Media', 3),
    ('Baja', 4);

INSERT INTO statuses (name, sort_order) VALUES
    ('Abierto', 1),
    ('En progreso', 2),
    ('Resuelto', 3),
    ('Cerrado', 4);

-- ---------------------------------------------------------------------------
-- tickets
-- ---------------------------------------------------------------------------
-- Las claves foraneas compuestas (company_id, requester_id) y
-- (company_id, assignee_id) obligan a que el creador y el tecnico asignado
-- pertenezcan a la misma empresa que el ticket. No es una regla solo del
-- backend: la base de datos la impide.
CREATE TABLE tickets (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id   uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
    requester_id uuid NOT NULL,
    assignee_id  uuid,
    title        text NOT NULL,
    description  text NOT NULL,
    priority     text REFERENCES priorities (name) ON UPDATE CASCADE,
    status       text NOT NULL DEFAULT 'Abierto' REFERENCES statuses (name) ON UPDATE CASCADE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tickets_title_length CHECK (char_length(btrim(title)) BETWEEN 1 AND 200),
    CONSTRAINT tickets_description_length CHECK (char_length(btrim(description)) BETWEEN 1 AND 5000),
    CONSTRAINT tickets_requester_company_fk
        FOREIGN KEY (company_id, requester_id)
        REFERENCES users (company_id, id) ON DELETE RESTRICT,
    CONSTRAINT tickets_assignee_company_fk
        FOREIGN KEY (company_id, assignee_id)
        REFERENCES users (company_id, id) ON DELETE RESTRICT
);

CREATE INDEX tickets_company_created_idx ON tickets (company_id, created_at DESC);
CREATE INDEX tickets_company_requester_idx ON tickets (company_id, requester_id);
CREATE INDEX tickets_company_assignee_idx
    ON tickets (company_id, assignee_id) WHERE assignee_id IS NOT NULL;

CREATE FUNCTION tickets_touch_updated_at() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER tickets_touch_updated_at
BEFORE UPDATE ON tickets
FOR EACH ROW EXECUTE FUNCTION tickets_touch_updated_at();

-- ---------------------------------------------------------------------------
-- sla_policies
-- ---------------------------------------------------------------------------
CREATE TABLE sla_policies (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id     uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
    priority       text NOT NULL REFERENCES priorities (name) ON UPDATE CASCADE,
    target_minutes integer NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sla_policies_target_positive CHECK (target_minutes > 0),
    CONSTRAINT sla_policies_company_priority_unique UNIQUE (company_id, priority)
);

CREATE INDEX sla_policies_company_idx ON sla_policies (company_id);

-- Cada empresa nace con sus cuatro politicas por prioridad:
-- Critica 2 h, Alta 4 h, Media 12 h y Baja 24 h.
CREATE FUNCTION seed_company_sla_policies() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO sla_policies (company_id, priority, target_minutes)
    VALUES
        (NEW.id, 'Crítica', 120),
        (NEW.id, 'Alta', 240),
        (NEW.id, 'Media', 720),
        (NEW.id, 'Baja', 1440);
    RETURN NEW;
END;
$$;

CREATE TRIGGER companies_seed_sla_policies
AFTER INSERT ON companies
FOR EACH ROW EXECUTE FUNCTION seed_company_sla_policies();

-- ---------------------------------------------------------------------------
-- ticket_sla
-- ---------------------------------------------------------------------------
-- La empresa se identifica a traves del ticket. due_at se calcula en la
-- base de datos a partir del objetivo congelado en target_minutes.
CREATE TABLE ticket_sla (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id         uuid NOT NULL UNIQUE REFERENCES tickets (id) ON DELETE CASCADE,
    target_minutes    integer NOT NULL,
    started_at        timestamptz NOT NULL DEFAULT now(),
    first_response_at timestamptz,
    resolved_at       timestamptz,
    breached          boolean,
    due_at            timestamptz NOT NULL,
    CONSTRAINT ticket_sla_target_positive CHECK (target_minutes > 0),
    CONSTRAINT ticket_sla_first_response_after_start
        CHECK (first_response_at IS NULL OR first_response_at >= started_at),
    CONSTRAINT ticket_sla_resolved_after_start
        CHECK (resolved_at IS NULL OR resolved_at >= started_at)
);

CREATE FUNCTION ticket_sla_set_due_at() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.due_at := NEW.started_at + make_interval(mins => NEW.target_minutes);
    RETURN NEW;
END;
$$;

CREATE TRIGGER ticket_sla_set_due_at
BEFORE INSERT OR UPDATE OF started_at, target_minutes ON ticket_sla
FOR EACH ROW EXECUTE FUNCTION ticket_sla_set_due_at();

-- ---------------------------------------------------------------------------
-- ticket_comments
-- ---------------------------------------------------------------------------
-- La empresa se identifica a traves del ticket. El trigger impide que un
-- usuario de otra empresa comente un ticket ajeno.
CREATE TABLE ticket_comments (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id  uuid NOT NULL REFERENCES tickets (id) ON DELETE CASCADE,
    author_id  uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    body       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ticket_comments_body_not_blank CHECK (btrim(body) <> '')
);

CREATE INDEX ticket_comments_ticket_idx ON ticket_comments (ticket_id, created_at);
CREATE INDEX ticket_comments_author_idx ON ticket_comments (author_id);

CREATE FUNCTION enforce_comment_same_company() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    ticket_company uuid;
    author_company uuid;
BEGIN
    SELECT company_id INTO ticket_company FROM tickets WHERE id = NEW.ticket_id;
    SELECT company_id INTO author_company FROM users WHERE id = NEW.author_id;

    IF ticket_company IS NULL THEN
        RAISE EXCEPTION 'ticket % does not exist', NEW.ticket_id
            USING ERRCODE = '23503';
    END IF;

    IF author_company IS NULL THEN
        RAISE EXCEPTION 'user % does not exist', NEW.author_id
            USING ERRCODE = '23503';
    END IF;

    IF ticket_company <> author_company THEN
        RAISE EXCEPTION 'comment author and ticket must belong to the same company'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER ticket_comments_same_company
BEFORE INSERT OR UPDATE OF ticket_id, author_id ON ticket_comments
FOR EACH ROW EXECUTE FUNCTION enforce_comment_same_company();
