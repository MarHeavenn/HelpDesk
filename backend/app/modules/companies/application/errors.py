"""Errores de `companies` con la forma de RF-137 (HU-19).

`detail` es siempre una cadena; la interfaz la devuelve como
`{"detail": <cadena>}` sin reinterpretarla. `CompanyDomainError` se define en
`domain/errors.py` para respetar la separacion de capas y se reexporta aqui,
que es el punto de importacion de las capas de aplicacion e interfaz. Los
errores de existencia y conflicto pertenecen a la aplicacion: no son reglas
de forma del dominio.
"""

from app.modules.companies.domain.errors import CompanyDomainError


class CompanyNotFoundError(ValueError):
    """La empresa no existe o no es visible para el alcance de la sesion."""

    def __init__(self, detail: str = "company not found") -> None:
        super().__init__(detail)
        self.detail = detail


class CompanyConflictError(ValueError):
    """Conflicto generico de RF-137 (`empresa no disponible`)."""

    def __init__(self, detail: str = "empresa no disponible") -> None:
        super().__init__(detail)
        self.detail = detail


__all__ = [
    "CompanyDomainError",
    "CompanyNotFoundError",
    "CompanyConflictError",
]
