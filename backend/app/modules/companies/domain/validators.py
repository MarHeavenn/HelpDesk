"""Reglas de validacion y normalizacion de empresas (HU-19).

Cubre RF-126 (alta), RF-127 (datos de contacto), RF-128 (forma normalizada
del nombre), RF-131 (actualizacion), RF-137 (literales exactos de dominio) y
RF-139 (tolerancia de empresas heredadas).

Reglas:
- El nombre se recorta; la forma de comparacion recorta, normaliza a NFC y
  pasa a minusculas (RF-128). El nombre almacenado es la cadena recortada tal
  como llega (RF-143) y siempre mide 2-100 caracteres, salvo el propio nombre
  heredado de una empresa que se actualiza sin cambiar su forma normalizada
  (RF-128 y RF-139).
- El correo de contacto es obligatorio en el alta, se recorta, pasa a
  minusculas, admite hasta 254 caracteres y comparte sintaxis y mensaje con
  HU-13 (RF-127).
- Persona de contacto: 2-100 caracteres tras recorte. Telefono: hasta 32
  caracteres tras recorte. Cadena vacia o solo espacios equivale a `null` y
  `null` borra en la actualizacion.
- Los mensajes de dominio son literales de RF-137: se lanzan como
  `CompanyDomainError.detail` y no se traducen despues.
- La validacion sintactica del correo replica la de HU-13 con la misma
  biblioteca y los mismos argumentos, para que el mensaje sea identico sin
  que `companies.domain` importe `identity` (separacion entre modulos).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Mapping

from email_validator import EmailNotValidError
from email_validator import validate_email as _validate_email_syntax

from app.modules.companies.domain.errors import CompanyDomainError

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 100
CONTACT_NAME_MIN_LENGTH = 2
CONTACT_NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 254
PHONE_MAX_LENGTH = 32

NAME_LENGTH_MESSAGE = "name must have 2-100 characters"
CONTACT_NAME_LENGTH_MESSAGE = "contact name must have 2-100 characters"
EMAIL_REQUIRED_MESSAGE = "email is required"
EMAIL_LENGTH_MESSAGE = "email exceeds 254 characters"
PHONE_LENGTH_MESSAGE = "phone exceeds 32 characters"
EMPTY_UPDATE_MESSAGE = "at least one field is required"
RESEND_FIELDS_MESSAGE = "resend does not accept name or email"
INVITATION_FIELDS_MESSAGE = "name and email are required"


class _Missing:
    """Centinela que distingue un campo omitido de uno enviado como `null`."""

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _Missing()


@dataclass(frozen=True)
class CompanyContactData:
    """Datos de contacto ya validados de un alta."""

    name: str
    name_normalized: str
    email: str
    phone: str | None
    contact_name: str | None


@dataclass(frozen=True)
class CompanyAdministratorData:
    """Nombre y correo ya normalizados de la administradora invitada."""

    name: str
    email: str


def normalize_company_name(raw: str) -> str:
    """Forma normalizada de comparacion de RF-128.

    Recorta, normaliza a NFC y pasa a minusculas. No aplica el rango: las
    empresas heredadas pueden tener formas fuera de 2-100 (RF-139).
    """
    if not isinstance(raw, str):
        raise CompanyDomainError(NAME_LENGTH_MESSAGE)
    return unicodedata.normalize("NFC", raw.strip()).lower()


def validate_company_name(raw: str) -> str:
    """Devuelve el nombre recortado y exige 2-100 caracteres (RF-126)."""
    if not isinstance(raw, str):
        raise CompanyDomainError(NAME_LENGTH_MESSAGE)
    name = raw.strip()
    if not (NAME_MIN_LENGTH <= len(name) <= NAME_MAX_LENGTH):
        raise CompanyDomainError(NAME_LENGTH_MESSAGE)
    return name


def validate_company_name_change(
    raw: str, current_name_normalized: str | None = None
) -> str:
    """Nombre de una actualizacion (RF-128 y RF-139).

    Un cambio que conserva la forma normalizada propia no es conflicto y no
    vuelve a exigir el rango: seguir editando una empresa heredada con un
    nombre fuera de 2-100 es valido. Un cambio efectivo si exige 2-100.
    """
    if not isinstance(raw, str):
        raise CompanyDomainError(NAME_LENGTH_MESSAGE)
    name = raw.strip()
    if not name:
        raise CompanyDomainError(NAME_LENGTH_MESSAGE)
    if normalize_company_name(name) == current_name_normalized:
        return name
    return validate_company_name(name)


def normalize_company_email(raw: str) -> str:
    """Recorta, pasa a minusculas y aplica el limite de 254 (RF-127)."""
    if not isinstance(raw, str):
        raise CompanyDomainError(EMAIL_REQUIRED_MESSAGE)
    email = raw.strip().lower()
    if not email:
        raise CompanyDomainError(EMAIL_REQUIRED_MESSAGE)
    if len(email) > EMAIL_MAX_LENGTH:
        raise CompanyDomainError(EMAIL_LENGTH_MESSAGE)
    return email


def validate_company_email(raw: str) -> str:
    """Normaliza y valida la sintaxis del correo con las reglas de HU-13."""
    email = normalize_company_email(raw)
    try:
        _validate_email_syntax(email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise CompanyDomainError(str(exc)) from exc
    return email


def normalize_contact_name(raw: str | None) -> str | None:
    """Recorta la persona de contacto; vacia o solo espacios es `None`."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise CompanyDomainError(CONTACT_NAME_LENGTH_MESSAGE)
    contact_name = raw.strip()
    if not contact_name:
        return None
    if not (
        CONTACT_NAME_MIN_LENGTH
        <= len(contact_name)
        <= CONTACT_NAME_MAX_LENGTH
    ):
        raise CompanyDomainError(CONTACT_NAME_LENGTH_MESSAGE)
    return contact_name


def normalize_phone(raw: str | None) -> str | None:
    """Recorta el telefono; vacio o solo espacios es `None` (maximo 32)."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise CompanyDomainError(PHONE_LENGTH_MESSAGE)
    phone = raw.strip()
    if not phone:
        return None
    if len(phone) > PHONE_MAX_LENGTH:
        raise CompanyDomainError(PHONE_LENGTH_MESSAGE)
    return phone


def validate_new_company(
    name: str,
    email: str,
    phone: str | None = None,
    contact_name: str | None = None,
) -> CompanyContactData:
    """Valida y normaliza el alta de una empresa (RF-126 y RF-127).

    El nombre se evalua antes que el correo, en el mismo orden en que RF-135
    evalua el conflicto de nombre antes que el del correo de la administradora.
    """
    clean_name = validate_company_name(name)
    clean_email = validate_company_email(email)
    return CompanyContactData(
        name=clean_name,
        name_normalized=normalize_company_name(clean_name),
        email=clean_email,
        phone=normalize_phone(phone),
        contact_name=normalize_contact_name(contact_name),
    )


def validate_company_update(
    *,
    name: str | None | _Missing = MISSING,
    email: str | None | _Missing = MISSING,
    phone: str | None | _Missing = MISSING,
    contact_name: str | None | _Missing = MISSING,
    current_name_normalized: str | None = None,
) -> Mapping[str, str | None]:
    """Valida una actualizacion parcial (RF-127, RF-131 y RF-139).

    Devuelve solo los campos enviados, ya limpios. `MISSING` significa
    "conservar"; `None` en telefono o persona de contacto borra el valor y en
    nombre o correo es un 422 de dominio.
    """
    if (
        name is MISSING
        and email is MISSING
        and phone is MISSING
        and contact_name is MISSING
    ):
        raise CompanyDomainError(EMPTY_UPDATE_MESSAGE)

    changes: dict[str, str | None] = {}
    if name is not MISSING:
        if name is None:
            raise CompanyDomainError(NAME_LENGTH_MESSAGE)
        clean_name = validate_company_name_change(name, current_name_normalized)
        changes["name"] = clean_name
        changes["name_normalized"] = normalize_company_name(clean_name)
    if email is not MISSING:
        if email is None:
            raise CompanyDomainError(EMAIL_REQUIRED_MESSAGE)
        changes["email"] = validate_company_email(email)
    if phone is not MISSING:
        changes["phone"] = normalize_phone(phone)
    if contact_name is not MISSING:
        changes["contact_name"] = normalize_contact_name(contact_name)
    return changes


def validate_resend_payload(
    *,
    name: str | None | _Missing = MISSING,
    email: str | None | _Missing = MISSING,
) -> None:
    """La rama de reenvio no admite nombre ni correo (RF-141).

    Cualquier presencia del campo, incluso `null` o vacio, es un 422 de
    dominio: la rama solo reenvia sobre la invitacion pendiente existente.
    """
    if name is not MISSING or email is not MISSING:
        raise CompanyDomainError(RESEND_FIELDS_MESSAGE)


def _usable_text(value: object) -> str | None:
    """Devuelve el texto recortado o `None` si no es un valor utilizable."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def validate_invitation_payload(
    *,
    name: str | None | _Missing = MISSING,
    email: str | None | _Missing = MISSING,
) -> CompanyAdministratorData:
    """Nombre y correo de la rama de invitacion (RF-141).

    Si falta alguno de los dos valores utilizables el mensaje es
    `"name and email are required"`; si ambos estan presentes se aplican las
    reglas propias de cada campo.
    """
    clean_name = _usable_text(name)
    clean_email = _usable_text(email)
    if clean_name is None or clean_email is None:
        raise CompanyDomainError(INVITATION_FIELDS_MESSAGE)
    return CompanyAdministratorData(
        name=validate_company_name(clean_name),
        email=validate_company_email(clean_email),
    )
