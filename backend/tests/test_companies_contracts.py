"""HU-19 T3 — contratos entre módulos y dirección de dependencias.

Cubre RF-132, RF-134, RF-136, RF-140 y RF-141:

- `get_company_account_stats` cuenta todas las cuentas de la empresa,
  incluidas las desactivadas y las de invitación pendiente, sin importar el
  rol, y deriva `has_administrator` y `administrator_invitation_pending`.
- `list_company_administrators` devuelve solo `{id, created_at, status,
  invitation_status}` ordenado por `created_at` ascendente y luego `id`.
- `get_company_ticket_stats` cuenta todos los tickets de la empresa, excluye
  los que no tienen empresa y siempre devuelve las cuatro claves del reparto
  con suma igual al total.
- `list_unassigned_accounts` excluye las cuentas con empresa y con rol
  `administrador` y ordena por la forma normalizada de RF-128 y luego `id`.
- `get_company_status` devuelve `active`, `inactive` o `None`.
- Los tres contratos devuelven solo DTOs inmutables y ningún `*_contract.py`
  importa el contrato de otro módulo ni repositorios ajenos; importar
  `app.main` no produce ciclos.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import uuid
from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import psycopg
import pytest

from app.infrastructure import db

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.companies.domain.entities import Company
from app.modules.companies.infrastructure.company_repository import (
    get_company_repository,
)
from app.modules.companies.interface.company_status_contract import (
    company_exists,
    get_company_status,
)
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.company_account_contract import (
    CompanyAccountStats,
    CompanyAdministratorView,
    UnassignedAccountView,
    get_company_account_stats,
    list_company_administrators,
    list_unassigned_accounts,
)
from app.modules.tickets.domain.entities import STATUSES, Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)
from app.modules.tickets.interface.company_ticket_contract import (
    CompanyTicketStats,
    get_company_ticket_stats,
)


@pytest.fixture(autouse=True)
def clean_stores():
    users = get_user_repository()
    tickets = get_ticket_repository()
    companies = get_company_repository()
    users.clear()
    tickets.clear()
    companies.clear()
    yield
    users.clear()
    tickets.clear()
    companies.clear()


def _company(status: str = "active", name: str = "Acme") -> Company:
    return Company(
        id=str(uuid.uuid4()),
        name=name,
        name_normalized=name.strip().lower(),
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def _user(
    *,
    company_id: str | None = None,
    role: str = "tecnico",
    status: str = "active",
    invitation_status: str = "accepted",
    name: str = "Cuenta",
    user_id: str | None = None,
    created_at: datetime | None = None,
) -> User:
    return User(
        id=user_id or str(uuid.uuid4()),
        name=name,
        email=f"{uuid.uuid4().hex}@ejemplo.com",
        password_hash=None,
        role=role,
        company_id=company_id,
        status=status,
        invitation_status=invitation_status,
        created_at=created_at or datetime.now(timezone.utc),
    )


def _ticket(company_id: str | None, status: str) -> Ticket:
    return Ticket(
        id=str(uuid.uuid4()),
        title="Ticket",
        description="Descripción",
        requester_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        status=status,
        company_id=company_id,
    )


# ---------------------------------------------------------------------------
# RF-132 / RF-143 — agregados de cuentas
# ---------------------------------------------------------------------------

def test_company_account_stats_counts_every_account_regardless_of_role_or_state():
    company = _company()
    get_user_repository().add(_user(company_id=company.id, role="tecnico"))
    get_user_repository().add(
        _user(company_id=company.id, role="cliente", status="deactivated")
    )
    get_user_repository().add(
        _user(
            company_id=company.id,
            role="administrador",
            invitation_status="pending",
        )
    )
    get_user_repository().add(
        _user(
            company_id=company.id,
            role="administrador",
            status="deactivated",
            invitation_status="accepted",
        )
    )
    get_user_repository().add(_user(company_id=company.id, role="supervisor"))

    stats = get_company_account_stats(company.id)

    assert isinstance(stats, CompanyAccountStats)
    assert stats.users_total == 5
    assert stats.has_administrator is False
    assert stats.administrator_invitation_pending is True


def test_company_account_stats_derives_administrator_flags_from_rf_143():
    company = _company()
    get_user_repository().add(
        _user(
            company_id=company.id,
            role="administrador",
            invitation_status="accepted",
        )
    )

    stats = get_company_account_stats(company.id)

    assert stats.users_total == 1
    assert stats.has_administrator is True
    assert stats.administrator_invitation_pending is False


def test_company_account_stats_ignores_other_companies_and_empty_company():
    company = _company()
    other = _company(name="Otro")
    get_user_repository().add(_user(company_id=other.id, role="administrador"))

    stats = get_company_account_stats(company.id)

    assert stats.users_total == 0
    assert stats.has_administrator is False
    assert stats.administrator_invitation_pending is False


# ---------------------------------------------------------------------------
# RF-141 — administradoras de la empresa
# ---------------------------------------------------------------------------

def test_company_administrators_are_ordered_by_created_at_then_id():
    company = _company()
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    middle = datetime(2026, 1, 2, tzinfo=timezone.utc)
    newer = datetime(2026, 1, 3, tzinfo=timezone.utc)
    # Insertadas fuera de orden y con empate en `middle` para fijar el
    # desempate por identificador ascendente.
    get_user_repository().add(
        _user(
            company_id=company.id,
            role="administrador",
            user_id="c",
            created_at=newer,
        )
    )
    get_user_repository().add(
        _user(
            company_id=company.id,
            role="administrador",
            user_id="b",
            created_at=middle,
        )
    )
    get_user_repository().add(
        _user(
            company_id=company.id,
            role="administrador",
            user_id="a",
            created_at=middle,
        )
    )
    get_user_repository().add(
        _user(
            company_id=company.id,
            role="administrador",
            user_id="z",
            created_at=older,
        )
    )
    get_user_repository().add(
        _user(company_id=company.id, role="tecnico", created_at=older)
    )
    get_user_repository().add(
        _user(company_id=_company().id, role="administrador", created_at=older)
    )

    administrators = list_company_administrators(company.id)

    assert [view.id for view in administrators] == ["z", "a", "b", "c"]
    assert all(isinstance(view, CompanyAdministratorView) for view in administrators)
    assert administrators[0].created_at == older
    assert {field.name for field in fields(CompanyAdministratorView)} == {
        "id",
        "created_at",
        "status",
        "invitation_status",
    }


def test_company_administrators_view_is_immutable_and_keeps_rf_141_fields():
    company = _company()
    created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    get_user_repository().add(
        _user(
            company_id=company.id,
            role="administrador",
            user_id="admin-1",
            status="active",
            invitation_status="pending",
            created_at=created_at,
        )
    )

    view = list_company_administrators(company.id)[0]

    assert view.id == "admin-1"
    assert view.created_at == created_at
    assert view.status == "active"
    assert view.invitation_status == "pending"
    assert is_dataclass(view)
    with pytest.raises(FrozenInstanceError):
        view.status = "deactivated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RF-132 / RF-143 — agregados de tickets
# ---------------------------------------------------------------------------

def test_company_ticket_stats_counts_every_company_ticket_in_every_state():
    company = _company()
    other = _company(name="Otro")
    counts = {
        "Abierto": 2,
        "En progreso": 1,
        "Resuelto": 3,
        "Cerrado": 0,
    }
    for status, amount in counts.items():
        for _ in range(amount):
            get_ticket_repository().add(_ticket(company.id, status))
    get_ticket_repository().add(_ticket(other.id, "Abierto"))
    get_ticket_repository().add(_ticket(None, "Abierto"))

    stats = get_company_ticket_stats(company.id)

    assert isinstance(stats, CompanyTicketStats)
    assert stats.tickets_total == 6
    assert set(stats.by_status) == set(STATUSES)
    assert stats.by_status["Abierto"] == 2
    assert stats.by_status["En progreso"] == 1
    assert stats.by_status["Resuelto"] == 3
    assert stats.by_status["Cerrado"] == 0
    assert sum(stats.by_status.values()) == stats.tickets_total


def test_company_ticket_stats_always_returns_the_four_keys_even_when_empty():
    company = _company()

    stats = get_company_ticket_stats(company.id)

    assert stats.tickets_total == 0
    assert set(stats.by_status) == {"Abierto", "En progreso", "Resuelto", "Cerrado"}
    assert all(value == 0 for value in stats.by_status.values())


def test_company_ticket_stats_dto_is_immutable():
    company = _company()
    get_ticket_repository().add(_ticket(company.id, "Abierto"))

    stats = get_company_ticket_stats(company.id)

    assert isinstance(stats.by_status, MappingProxyType)
    with pytest.raises(FrozenInstanceError):
        stats.tickets_total = 99  # type: ignore[misc]
    with pytest.raises(TypeError):
        stats.by_status["Abierto"] = 99  # type: ignore[index]


# ---------------------------------------------------------------------------
# RF-140 — cuentas sin empresa
# ---------------------------------------------------------------------------

def test_list_unassigned_accounts_excludes_company_and_administrator_accounts():
    company = _company()
    get_user_repository().add(_user(company_id=company.id, role="tecnico"))
    get_user_repository().add(
        _user(company_id=None, role="administrador", name="Admin plataforma")
    )
    get_user_repository().add(_user(company_id=None, role="tecnico", name="Uno"))
    get_user_repository().add(
        _user(company_id=None, role="cliente", name="Dos", status="deactivated")
    )

    accounts = list_unassigned_accounts()

    assert [account.name for account in accounts] == ["Dos", "Uno"]
    assert all(isinstance(account, UnassignedAccountView) for account in accounts)
    assert {field.name for field in fields(UnassignedAccountView)} == {
        "id",
        "name",
        "email",
        "role",
        "status",
    }


def test_list_unassigned_accounts_orders_by_normalized_name_then_id():
    first_id = "00000000-0000-0000-0000-000000000001"
    second_id = "00000000-0000-0000-0000-000000000002"
    # «Zoe» pasa a `zoe`, que en code points es anterior a `ángel` (á es
    # U+00E1), de modo que la normalización cambia el orden.
    get_user_repository().add(
        _user(company_id=None, role="tecnico", name="  Ángela ", user_id=first_id)
    )
    get_user_repository().add(
        _user(company_id=None, role="cliente", name="Zoe", user_id=second_id)
    )
    # Dos cuentas con el mismo nombre normalizado: manda el identificador.
    get_user_repository().add(
        _user(
            company_id=None,
            role="tecnico",
            name="borja",
            user_id="00000000-0000-0000-0000-00000000000a",
        )
    )
    get_user_repository().add(
        _user(
            company_id=None,
            role="cliente",
            name="BORJA",
            user_id="00000000-0000-0000-0000-000000000009",
        )
    )

    accounts = list_unassigned_accounts()

    assert [account.id for account in accounts] == [
        "00000000-0000-0000-0000-000000000009",
        "00000000-0000-0000-0000-00000000000a",
        second_id,
        first_id,
    ]


# ---------------------------------------------------------------------------
# RF-136 / RF-134 / RF-141 — estado de empresa
# ---------------------------------------------------------------------------

def test_get_company_status_returns_active_inactive_or_none():
    active = _company(status="active")
    inactive = _company(status="inactive")
    get_company_repository().add(active)
    get_company_repository().add(inactive)

    assert get_company_status(active.id) == "active"
    assert get_company_status(inactive.id) == "inactive"
    assert get_company_status(str(uuid.uuid4())) is None
    assert company_exists(active.id) is True
    assert company_exists(str(uuid.uuid4())) is False


# ---------------------------------------------------------------------------
# Persistencia de la fecha de alta (migracion 005, RF-141)
# ---------------------------------------------------------------------------

def test_company_administrator_created_at_is_persisted_in_postgres():
    try:
        conn = db.connect()
    except (psycopg.OperationalError, RuntimeError) as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    try:
        company = _company()
        created_at = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        user = _user(
            company_id=company.id,
            role="administrador",
            user_id="created-at-admin",
            created_at=created_at,
        )
        repository = get_user_repository()
        repository.add(user)
        try:
            with conn.transaction(force_rollback=True):
                loaded = repository.load_persistent_for_update(user.id, conn)
                assert loaded is not None
                assert loaded.created_at == created_at
            views = list_company_administrators(company.id)
            assert [view.id for view in views] == ["created-at-admin"]
            assert views[0].created_at == created_at
        finally:
            repository.clear()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dirección de dependencias
# ---------------------------------------------------------------------------

def _contract_files() -> list[Path]:
    modules_root = BACKEND_ROOT / "app" / "modules"
    return sorted(modules_root.rglob("*_contract.py"))


def test_contracts_only_import_their_own_module():
    contracts = _contract_files()
    assert contracts, "no se encontraron contratos que revisar"
    violations: list[str] = []
    for path in contracts:
        owner = path.relative_to(BACKEND_ROOT / "app" / "modules").parts[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            if not module or not module.startswith("app.modules."):
                continue
            imported_owner = module.split(".")[2]
            if imported_owner != owner:
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} importa "
                    f"`{module}` de `{imported_owner}`"
                )
    assert not violations, "contratos con imports ajenos:\n" + "\n".join(violations)


def test_importing_app_main_does_not_produce_cycles():
    environment = dict(os.environ)
    python_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        str(BACKEND_ROOT) + os.pathsep + python_path if python_path else str(BACKEND_ROOT)
    )
    environment.setdefault("HELPDESK_ALLOW_IN_MEMORY", "1")
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=str(BACKEND_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"import app.main falló:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "circular import" not in combined
    assert "most likely due to a circular import" not in combined


def test_companies_module_does_not_import_foreign_application_or_infrastructure():
    companies_root = BACKEND_ROOT / "app" / "modules" / "companies"
    forbidden: list[str] = []
    for path in companies_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            if not module or not module.startswith("app.modules."):
                continue
            parts = module.split(".")
            if len(parts) < 4 or parts[2] == "companies":
                continue
            if parts[3] in {"application", "infrastructure"}:
                forbidden.append(
                    f"{path.relative_to(BACKEND_ROOT)} importa `{module}`"
                )
    assert not forbidden, "imports ajenos prohibidos:\n" + "\n".join(forbidden)
