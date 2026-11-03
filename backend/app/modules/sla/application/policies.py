"""Configuracion de tiempos objetivo de SLA (RF-41, RF-71, RF-76).

El catalogo y la semilla inicial viven en el dominio
(`sla.domain.policy_config`); aqui se reexporta la semilla para no
romper los imports de HU-05.

Desde HU-14 la configuracion es administrable: `target_minutes_for`
deja de leer la constante y consulta la configuracion vigente del
repositorio en memoria **en cada llamada** (RF-76). La lectura es O(1) y
no se cachea, de modo que un reemplazo de la configuracion se refleja en
la siguiente consulta de cualquier ticket activo.

La prioridad se compara con el catalogo exacto de HU-03. Una prioridad
desconocida no tiene tiempo objetivo y el ticket se queda sin SLA.
"""

from app.modules.sla.domain.policy_config import (
    DEFAULT_SLA_TARGET_MINUTES,
)
from app.modules.sla.infrastructure.sla_policy_repository import (
    InMemorySlaPolicyRepository,
    get_sla_policy_repository,
)

__all__ = ["DEFAULT_SLA_TARGET_MINUTES", "target_minutes_for"]


def target_minutes_for(
    priority: str | None,
    policies: InMemorySlaPolicyRepository | None = None,
) -> int | None:
    """Devuelve los minutos objetivo vigentes o None si no aplica.

    `policies` permite inyectar el repositorio en pruebas; si falta, se
    usa el singleton compartido. La configuracion se relee siempre, sin
    cache (RF-76).
    """
    if priority is None:
        return None
    repository = policies if policies is not None else get_sla_policy_repository()
    return repository.get_target_minutes(priority)
