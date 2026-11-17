"""Frontera de `companies` hacia otros modulos para consultar el estado.

`identity` y `tickets` consumen este contrato para bloquear las altas nuevas
en una empresa inactiva (RF-136) y para resolver el alcance (RF-134, RF-141).
Devuelve solo el estado o `None`: nunca la entidad `Company`, sus datos de
contacto, sus cuentas, sus tickets ni el repositorio.
"""

from __future__ import annotations

from app.modules.companies.infrastructure.company_repository import (
    InMemoryCompanyRepository,
    get_company_repository,
)


def get_company_status(
    company_id: str | None, companies: InMemoryCompanyRepository | None = None
) -> str | None:
    """Estado persistido de la empresa: `active`, `inactive` o `None`."""
    if company_id is None:
        return None
    repository = companies if companies is not None else get_company_repository()
    company = repository.find_by_id(company_id)
    return company.status if company is not None else None


def company_exists(
    company_id: str | None, companies: InMemoryCompanyRepository | None = None
) -> bool:
    """True solo si la empresa existe; no revela ningun otro dato."""
    if company_id is None:
        return False
    repository = companies if companies is not None else get_company_repository()
    return repository.find_by_id(company_id) is not None
