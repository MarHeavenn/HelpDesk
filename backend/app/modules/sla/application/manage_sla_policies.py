"""Casos de uso de la configuracion de SLA (HU-14, RF-72..RF-75).

`list_sla_policies` y `replace_sla_policies` implementan la consulta y el
reemplazo total de los tiempos objetivo, reservados al rol
`administrador`. La regla de autorizacion vive aqui, no en el
controlador (constitucion): `ensure_sla_admin` comprueba el rol **antes
de leer o escribir** el repositorio, de modo que un rol sin permiso no
obtiene datos ni modifica la configuracion.

La validacion y la conversion de horas a minutos son del dominio
(`validate_policy_targets`, RF-74); estos casos de uso solo coordinan
guardia -> validacion -> persistencia -> respuesta. El mensaje de rechazo
es unico (`"not found"`), que la interfaz traduce a 404 uniforme sin
revelar la existencia del recurso (RF-75).
"""

from collections.abc import Mapping

from app.modules.sla.domain.entities import SlaPolicy
from app.modules.sla.domain.policy_config import (
    SLA_PRIORITIES,
    validate_policy_targets,
)
from app.modules.sla.infrastructure.sla_policy_repository import (
    InMemorySlaPolicyRepository,
)

SLA_ADMIN_ROLE = "administrador"

# Mismo mensaje para cualquier rol sin permiso (404 uniforme, RF-75).
SLA_POLICIES_NOT_FOUND_MESSAGE = "not found"


class SlaPolicyAccessDeniedError(ValueError):
    """El rol del actor no puede consultar ni modificar la configuracion."""


def ensure_sla_admin(actor_role: str | None) -> None:
    """Exige el rol `administrador`; cualquier otro lanza el 404 uniforme.

    Se invoca al principio de cada caso de uso, antes de tocar el
    repositorio, para no revelar datos ni permitir escrituras (RF-75).
    """
    if actor_role != SLA_ADMIN_ROLE:
        raise SlaPolicyAccessDeniedError(SLA_POLICIES_NOT_FOUND_MESSAGE)


def _to_policies(targets: Mapping[str, int]) -> list[SlaPolicy]:
    """Proyecta los minutos por prioridad a la lista ordenada del catalogo."""
    return [
        SlaPolicy(priority=priority, target_minutes=targets[priority])
        for priority in SLA_PRIORITIES
    ]


def list_sla_policies(
    actor_role: str | None,
    policies: InMemorySlaPolicyRepository,
) -> list[SlaPolicy]:
    """Devuelve la configuracion vigente en orden de catalogo (RF-72).

    Solo lectura: no muta el repositorio ni los tickets. Un rol distinto
    de `administrador` recibe `SlaPolicyAccessDeniedError` sin datos.
    """
    ensure_sla_admin(actor_role)
    return _to_policies(policies.get_all())


def replace_sla_policies(
    actor_role: str | None,
    values: Mapping[str, object],
    policies: InMemorySlaPolicyRepository,
) -> list[SlaPolicy]:
    """Valida y reemplaza la configuracion completa (RF-73, RF-74).

    La guardia de rol se ejecuta antes que la validacion (RF-75); si la
    validacion del dominio falla, no se escribe nada. Devuelve la lista
    resultante en orden de catalogo.
    """
    ensure_sla_admin(actor_role)
    targets = validate_policy_targets(values)
    policies.replace(targets)
    return _to_policies(targets)
