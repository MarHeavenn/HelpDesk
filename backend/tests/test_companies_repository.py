"""Repositorio de empresas de HU-19 (RF-126, RF-128, RF-139).

Cubre el patron de repositorio (alta, busqueda, listado, actualizacion,
compensacion, conteo, vaciado y singleton), la tolerancia de nombres
normalizados duplicados (D-2) y el bloqueo transaccional por forma
normalizada, tanto en memoria como contra PostgreSQL.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone

import psycopg
import pytest

from app.infrastructure import db
from app.modules.companies.domain.entities import Company
from app.modules.companies.infrastructure.company_repository import (
    InMemoryCompanyRepository,
    get_company_repository,
)
from migrations.run import apply_migrations


def _company(
    name: str = "Acme",
    *,
    normalized: str | None = None,
    company_id: str | None = None,
) -> Company:
    return Company(
        id=company_id or str(uuid.uuid4()),
        name=name,
        name_normalized=normalized if normalized is not None else name.strip().lower(),
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def in_memory_repository(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    repository = InMemoryCompanyRepository()
    yield repository
    repository._by_id.clear()


@pytest.fixture(scope="module")
def postgres_ready() -> None:
    if not (
        os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_PASSWORD")
    ):
        pytest.skip("PostgreSQL no configurado")
    try:
        conn = db.connect()
    except (psycopg.OperationalError, RuntimeError) as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    try:
        apply_migrations(conn)
    finally:
        conn.close()


def test_add_find_list_count_and_remove(in_memory_repository) -> None:
    first = _company("Acme")
    second = _company("Globex")

    in_memory_repository.add(first)
    in_memory_repository.add(second)

    assert in_memory_repository.find_by_id(first.id) is first
    assert in_memory_repository.find_by_id("missing") is None
    assert in_memory_repository.find_by_id(None) is None
    assert in_memory_repository.list_all() == [first, second]
    assert in_memory_repository.count() == 2

    in_memory_repository.remove(first.id)

    assert in_memory_repository.find_by_id(first.id) is None
    assert in_memory_repository.count() == 1


def test_update_replaces_the_stored_company(in_memory_repository) -> None:
    company = _company("Acme")
    in_memory_repository.add(company)

    company.name = "Acme Renovada"
    company.name_normalized = "acme renovada"
    company.email = "contacto@acme.test"
    in_memory_repository.update(company)

    stored = in_memory_repository.find_by_id(company.id)
    assert stored is company
    assert stored.name == "Acme Renovada"
    assert stored.email == "contacto@acme.test"


def test_duplicate_normalized_names_are_tolerated(in_memory_repository) -> None:
    first = _company("  Ácme  ", normalized="ácme")
    second = _company("ácme", normalized="ácme")

    in_memory_repository.add(first)
    in_memory_repository.add(second)

    assert in_memory_repository.count() == 2
    assert in_memory_repository.find_by_id(first.id) is first
    assert in_memory_repository.find_by_id(second.id) is second


def test_singleton_and_clear(in_memory_repository) -> None:
    assert get_company_repository() is get_company_repository()

    repository = get_company_repository()
    repository.add(_company("Singleton"))
    assert repository.count() == 1
    repository.clear()
    assert repository.count() == 0


def test_in_memory_name_lock_serializes_the_same_normalized_name(
    in_memory_repository,
) -> None:
    active = 0
    max_active = 0
    guard = threading.Lock()

    def worker() -> None:
        nonlocal active, max_active
        with in_memory_repository.name_lock("ácme"):
            with guard:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with guard:
                active -= 1

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert max_active == 1


def test_missing_database_and_seam_raises_without_silent_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)
    repository = InMemoryCompanyRepository()

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        repository.add(_company())

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        with repository.name_lock("acme"):
            pass


def test_add_and_load_persist_against_postgres(postgres_ready) -> None:
    repository = InMemoryCompanyRepository()
    company = _company("Persistente")
    company.email = "contacto@persistente.test"
    try:
        repository.add(company)

        with db.connection() as conn:
            row = conn.execute(
                """
                SELECT name, name_normalized, email, phone, contact_name, status
                FROM companies WHERE id = %s
                """,
                (company.id,),
            ).fetchone()
            assert row == {
                "name": "Persistente",
                "name_normalized": "persistente",
                "email": "contacto@persistente.test",
                "phone": None,
                "contact_name": None,
                "status": "active",
            }

            loaded = repository.load_persistent_for_update(company.id, conn)
            assert loaded is not None
            assert loaded.id == company.id
            assert loaded.name == company.name
            assert loaded.name_normalized == company.name_normalized
            assert loaded.email == company.email
    finally:
        repository.remove(company.id)


def test_update_persists_against_postgres(postgres_ready) -> None:
    repository = InMemoryCompanyRepository()
    company = _company("Antes")
    try:
        repository.add(company)
        company.name = "Después"
        company.name_normalized = "después"
        company.status = "inactive"
        repository.update(company)

        with db.connection() as conn:
            row = conn.execute(
                "SELECT name, name_normalized, status FROM companies WHERE id = %s",
                (company.id,),
            ).fetchone()
            assert row == {
                "name": "Después",
                "name_normalized": "después",
                "status": "inactive",
            }
    finally:
        repository.remove(company.id)


def test_name_lock_holds_an_advisory_transaction_lock_in_postgres(
    postgres_ready,
) -> None:
    repository = InMemoryCompanyRepository()
    normalized = f"lock-{uuid.uuid4()}"

    with repository.name_lock(normalized) as conn:
        assert conn is not None
        with db.connect() as probe:
            acquired = probe.execute(
                "SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) "
                "AS acquired",
                (normalized,),
            ).fetchone()["acquired"]
        assert acquired is False

    with db.connect() as probe:
        acquired = probe.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS acquired",
            (normalized,),
        ).fetchone()["acquired"]
    assert acquired is True
