"""Conexion a PostgreSQL y operaciones basicas por empresa (TSK-025).

Regla de multitenancy: el `company_id` que reciben estas funciones debe
salir de la sesion autenticada, nunca del cuerpo de la peticion ni de un
parametro que el frontend pueda elegir. Toda consulta filtra por el.

Las operaciones no hacen commit: el llamador decide la transaccion. El
contexto `connection()` confirma al salir si no hubo excepcion y revierte
si la hubo.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import quote

import psycopg
from psycopg.rows import dict_row

TICKET_COLUMNS = (
    "id, company_id, requester_id, assignee_id, title, priority, status, "
    "created_at, updated_at"
)

USER_COLUMNS = "id, company_id, name, email, role, created_at"


def database_url() -> str:
    """Construye la URL de conexion a partir del entorno.

    Prioriza `DATABASE_URL`. Si no existe, compone la URL con
    `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST` y
    `POSTGRES_PORT`. No hay credenciales por defecto en el repositorio.
    """
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit

    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError(
            "Configura DATABASE_URL o POSTGRES_PASSWORD para conectar con PostgreSQL"
        )

    user = quote(os.environ.get("POSTGRES_USER", "helpdesk"), safe="")
    database = quote(os.environ.get("POSTGRES_DB", "helpdesk"), safe="")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{quote(password, safe='')}@{host}:{port}/{database}"


def connect() -> psycopg.Connection:
    """Abre una conexion con filas representadas como diccionarios."""
    return psycopg.connect(database_url(), row_factory=dict_row)


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """Contexto de conexion: commit al salir, rollback si hay excepcion."""
    with connect() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------
def list_company_tickets(
    conn: psycopg.Connection, company_id: str
) -> list[dict]:
    """Tickets de una empresa, mas recientes primero."""
    return conn.execute(
        f"""
        SELECT {TICKET_COLUMNS}
        FROM tickets
        WHERE company_id = %s
        ORDER BY created_at DESC
        """,
        (company_id,),
    ).fetchall()


def get_company_ticket(
    conn: psycopg.Connection, company_id: str, ticket_id: str
) -> dict | None:
    """Ticket de una empresa; `None` si no existe o es de otra empresa."""
    return conn.execute(
        f"""
        SELECT {TICKET_COLUMNS}
        FROM tickets
        WHERE company_id = %s AND id = %s
        """,
        (company_id, ticket_id),
    ).fetchone()


def create_company_ticket(
    conn: psycopg.Connection,
    *,
    company_id: str,
    requester_id: str,
    title: str,
    description: str,
    assignee_id: str | None = None,
    priority: str | None = None,
) -> dict:
    """Crea un ticket en la empresa indicada.

    La base de datos rechaza creador o tecnico de otra empresa mediante
    las claves foraneas compuestas.
    """
    return conn.execute(
        f"""
        INSERT INTO tickets (
            company_id, requester_id, assignee_id, title, description, priority
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING {TICKET_COLUMNS}
        """,
        (company_id, requester_id, assignee_id, title, description, priority),
    ).fetchone()


def assign_company_ticket(
    conn: psycopg.Connection,
    *,
    company_id: str,
    ticket_id: str,
    assignee_id: str,
) -> dict | None:
    """Asigna un ticket dentro de la empresa; no toca tickets ajenos."""
    return conn.execute(
        f"""
        UPDATE tickets
        SET assignee_id = %s
        WHERE company_id = %s AND id = %s
        RETURNING {TICKET_COLUMNS}
        """,
        (assignee_id, company_id, ticket_id),
    ).fetchone()


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------
def list_company_users(
    conn: psycopg.Connection, company_id: str
) -> list[dict]:
    """Usuarios de una empresa, sin exponer el hash de contrasena."""
    return conn.execute(
        f"""
        SELECT {USER_COLUMNS}
        FROM users
        WHERE company_id = %s
        ORDER BY name
        """,
        (company_id,),
    ).fetchall()


def create_company_user(
    conn: psycopg.Connection,
    *,
    company_id: str,
    name: str,
    email: str,
    password_hash: str,
    role: str,
) -> dict:
    """Crea un usuario en la empresa indicada."""
    return conn.execute(
        f"""
        INSERT INTO users (company_id, name, email, password_hash, role)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING {USER_COLUMNS}
        """,
        (company_id, name, email, password_hash, role),
    ).fetchone()


# ---------------------------------------------------------------------------
# SLA y comentarios (la empresa se resuelve a traves del ticket)
# ---------------------------------------------------------------------------
def list_sla_policies(
    conn: psycopg.Connection, company_id: str
) -> list[dict]:
    """Politicas de SLA de una empresa."""
    return conn.execute(
        """
        SELECT id, company_id, priority, target_minutes, created_at
        FROM sla_policies
        WHERE company_id = %s
        ORDER BY priority
        """,
        (company_id,),
    ).fetchall()


def list_ticket_comments(
    conn: psycopg.Connection, company_id: str, ticket_id: str
) -> list[dict]:
    """Comentarios de un ticket de la empresa indicada."""
    return conn.execute(
        """
        SELECT c.id, c.ticket_id, c.author_id, c.body, c.created_at
        FROM ticket_comments AS c
        JOIN tickets AS t ON t.id = c.ticket_id
        WHERE t.company_id = %s AND c.ticket_id = %s
        ORDER BY c.created_at
        """,
        (company_id, ticket_id),
    ).fetchall()


def create_ticket_comment(
    conn: psycopg.Connection,
    *,
    company_id: str,
    ticket_id: str,
    author_id: str,
    body: str,
) -> dict | None:
    """Comenta un ticket de la empresa; no toca tickets ajenos.

    El trigger de la base de datos exige ademas que el autor pertenezca a
    la misma empresa que el ticket.
    """
    return conn.execute(
        """
        INSERT INTO ticket_comments (ticket_id, author_id, body)
        SELECT t.id, %s, %s
        FROM tickets AS t
        WHERE t.id = %s AND t.company_id = %s
        RETURNING id, ticket_id, author_id, body, created_at
        """,
        (author_id, body, ticket_id, company_id),
    ).fetchone()
