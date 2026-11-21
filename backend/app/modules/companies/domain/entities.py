"""Entidad de empresa cliente (HU-19, RF-126 y RF-143).

La empresa es la raiz del catalogo: nombre y su forma normalizada de
comparacion (RF-128), datos de contacto (RF-127) y estado persistido
`active`/`inactive` (RF-136). Las reglas de validacion y normalizacion
viven en esta capa; la persistencia las replica sin decidir por su cuenta.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Company:
    """Empresa cliente con nombre ya recortado y su forma normalizada."""

    id: str
    name: str
    name_normalized: str
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_name: Optional[str] = None
    status: str = "active"
    created_at: datetime = field(default_factory=_utc_now)
