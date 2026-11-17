"""Errores de dominio del modulo `companies` (HU-19, RF-137).

La forma de error de RF-137 es `{"detail": <cadena>}` para la validacion de
dominio y para los conflictos. El error base vive en `domain` para no
invertir la direccion de dependencias entre capas; la capa de aplicacion lo
reexporta desde `application/errors.py`.
"""


class CompanyDomainError(ValueError):
    """Regla de dominio de empresa incumplida.

    `detail` es el mensaje exacto que la interfaz devolvera en el cuerpo de
    error de RF-137, sin traducciones posteriores.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
