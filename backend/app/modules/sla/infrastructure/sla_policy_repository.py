"""Repositorio en memoria de la configuracion de SLA (HU-14, RF-71, RF-77).

Mismo patron que `InMemoryUserRepository`/`get_user_repository` de
`identity`: almacenamiento en memoria y un singleton compartido
`get_sla_policy_repository()`, sustituible por un adaptador PostgreSQL
sin cambiar a sus consumidores.

Reglas:
- Una instancia nueva arranca con la semilla de RF-71
  (`DEFAULT_SLA_TARGET_MINUTES`); al arrancar el proceso se vuelve a ella
  porque no hay persistencia en PostgreSQL en esta historia.
- El reemplazo es total y atomico: se construye un mapa nuevo con las
  cuatro prioridades del catalogo y se asigna de una vez, de modo que la
  configuracion siempre se ve integra y gana el ultimo escritor (RF-77).
  El repositorio no valida: recibe un mapa ya validado por el dominio.
- `get_all()` devuelve una copia en orden de catalogo; mutarla no altera
  la configuracion almacenada.
- El almacenamiento se clavea por ambito (`company_id`) para que la
  futura integracion multitenant pueda usarlo sin romper el contrato.
  En esta historia solo se usa el ambito global (`None`); el kwarg es
  opcional y no cambia el comportamiento.
"""

from collections.abc import Mapping

from app.modules.sla.domain.policy_config import (
    DEFAULT_SLA_TARGET_MINUTES,
    SLA_PRIORITIES,
)


class InMemorySlaPolicyRepository:
    """Guarda los minutos objetivo por prioridad, por ambito."""

    def __init__(self) -> None:
        self._by_scope: dict[str | None, dict[str, int]] = {
            None: dict(DEFAULT_SLA_TARGET_MINUTES)
        }

    def get_target_minutes(
        self, priority: str | None, company_id: str | None = None
    ) -> int | None:
        """Minutos objetivo de la prioridad; None si no aplica o no existe."""
        if not isinstance(priority, str):
            return None
        return self._scope(company_id).get(priority)

    def get_all(self, company_id: str | None = None) -> dict[str, int]:
        """Copia de la configuracion completa en orden de catalogo."""
        scope = self._scope(company_id)
        return {priority: scope[priority] for priority in SLA_PRIORITIES}

    def replace(
        self, targets: Mapping[str, int], company_id: str | None = None
    ) -> None:
        """Sustituye la configuracion completa de forma atomica (RF-77).

        `targets` debe traer las cuatro prioridades ya validadas; el mapa
        nuevo se construye por completo antes de asignarse, asi que una
        lectura nunca observa una mezcla de escrituras y gana el ultimo
        reemplazo.
        """
        self._by_scope[company_id] = {
            priority: targets[priority] for priority in SLA_PRIORITIES
        }

    def reset(self, company_id: str | None = None) -> None:
        """Devuelve el ambito a la semilla inicial de RF-71."""
        self._by_scope[company_id] = dict(DEFAULT_SLA_TARGET_MINUTES)

    def _scope(self, company_id: str | None) -> dict[str, int]:
        """Devuelve el mapa del ambito, creandolo con la semilla si falta."""
        scope = self._by_scope.get(company_id)
        if scope is None:
            scope = dict(DEFAULT_SLA_TARGET_MINUTES)
            self._by_scope[company_id] = scope
        return scope


_policies = InMemorySlaPolicyRepository()


def get_sla_policy_repository() -> InMemorySlaPolicyRepository:
    """Devuelve el repositorio compartido de la configuracion de SLA."""
    return _policies
