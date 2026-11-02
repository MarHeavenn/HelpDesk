"""Configuracion de tiempos objetivo de SLA (RF-41).

En HU-05 la configuracion es global, interna y fija: los cuatro valores
iniciales del documento general. La consulta y la modificacion publicas
por parte del administrador corresponden a HU-14; por eso no hay
repositorio ni operacion HTTP en esta historia.

La prioridad se compara con el catalogo exacto de HU-03. Una prioridad
desconocida no tiene tiempo objetivo y el ticket se queda sin SLA.
"""

DEFAULT_SLA_TARGET_MINUTES: dict[str, int] = {
    "Crítica": 120,
    "Alta": 240,
    "Media": 720,
    "Baja": 1440,
}


def target_minutes_for(priority: str | None) -> int | None:
    """Devuelve los minutos objetivo de la prioridad o None si no aplica."""
    if priority is None:
        return None
    return DEFAULT_SLA_TARGET_MINUTES.get(priority)
