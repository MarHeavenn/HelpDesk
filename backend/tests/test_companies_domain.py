"""Dominio de empresa de HU-19 (RF-126, RF-127, RF-128, RF-131, RF-136,
RF-137 y RF-139).

Cubre la forma normalizada del nombre (recorte, NFC y minusculas), el rango
2-100 con su excepcion para empresas heredadas, los datos de contacto, los
literales exactos de dominio y las dos ramas de la invitacion del
administrador. Son pruebas unitarias: no necesitan PostgreSQL.
"""

from __future__ import annotations

import unicodedata

import pytest

from app.modules.companies.application.errors import CompanyDomainError
from app.modules.companies.domain import errors as domain_errors
from app.modules.companies.domain.validators import (
    MISSING,
    CompanyAdministratorData,
    CompanyContactData,
    normalize_company_email,
    normalize_company_name,
    normalize_contact_name,
    normalize_phone,
    validate_company_email,
    validate_company_name,
    validate_company_name_change,
    validate_company_update,
    validate_invitation_payload,
    validate_new_company,
    validate_resend_payload,
)
from app.modules.identity.infrastructure.email_validator import EmailValidator

LONG_LEGACY_NAME = "A" * 120  # nombre heredado fuera del rango 2-100 (RF-139)


def _detail(exc: pytest.ExceptionInfo[BaseException]) -> str:
    assert isinstance(exc.value, CompanyDomainError)
    return exc.value.detail


# --- Forma normalizada del nombre (RF-128) ---------------------------------


def test_normalized_name_trims_nfc_and_lowercases() -> None:
    assert normalize_company_name("  Acme  ") == "acme"
    assert normalize_company_name("ACME NORTE") == "acme norte"
    assert normalize_company_name("Ácme") == "ácme"


def test_normalized_name_ignores_unicode_composition() -> None:
    composed = "Ácme"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    assert normalize_company_name(composed) == normalize_company_name(
        decomposed
    )


def test_normalized_name_keeps_inner_spaces() -> None:
    assert normalize_company_name("  Acme   Norte  ") == "acme   norte"


@pytest.mark.parametrize("raw", [None, 7])
def test_normalized_name_rejects_non_text(raw) -> None:
    with pytest.raises(CompanyDomainError) as exc:
        normalize_company_name(raw)
    assert _detail(exc) == "name must have 2-100 characters"


# --- Nombre en el alta (RF-126) --------------------------------------------


def test_validate_name_trims_and_accepts_limits() -> None:
    assert validate_company_name("  Acme  ") == "Acme"
    assert validate_company_name("AB") == "AB"
    assert validate_company_name("A" * 100) == "A" * 100


@pytest.mark.parametrize(
    "raw",
    ["A", "A" * 101, "", "   ", "\t\n"],
)
def test_validate_name_rejects_out_of_range(raw: str) -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_name(raw)
    assert _detail(exc) == "name must have 2-100 characters"


@pytest.mark.parametrize("raw", [None, 42])
def test_validate_name_rejects_non_text(raw) -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_name(raw)
    assert _detail(exc) == "name must have 2-100 characters"


# --- Cambio de nombre (RF-128 y RF-139) ------------------------------------


def test_name_change_with_same_normalized_form_is_not_a_conflict() -> None:
    # Cambiar solo mayusculas o espacios del propio nombre se acepta.
    assert (
        validate_company_name_change("  ACME  ", "acme")
        == "ACME"
    )
    assert (
        validate_company_name_change("acme", "acme") == "acme"
    )


def test_legacy_out_of_range_name_can_change_its_own_case() -> None:
    # RF-139: el nombre heredado fuera de 2-100 sigue siendo editable.
    normalized = normalize_company_name(LONG_LEGACY_NAME)
    changed = validate_company_name_change(LONG_LEGACY_NAME.lower(), normalized)
    assert changed == LONG_LEGACY_NAME.lower()
    assert validate_company_name_change(
        f"  {LONG_LEGACY_NAME}  ", normalized
    ) == LONG_LEGACY_NAME


def test_effective_name_change_still_enforces_the_range() -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_name_change(LONG_LEGACY_NAME, "otro")
    assert _detail(exc) == "name must have 2-100 characters"

    with pytest.raises(CompanyDomainError) as exc:
        validate_company_name_change("A", "otro")
    assert _detail(exc) == "name must have 2-100 characters"


@pytest.mark.parametrize("raw", ["", "   "])
def test_name_change_rejects_blank_name(raw: str) -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_name_change(raw, "acme")
    assert _detail(exc) == "name must have 2-100 characters"


def test_name_change_with_unknown_current_name_enforces_the_range() -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_name_change(LONG_LEGACY_NAME, None)
    assert _detail(exc) == "name must have 2-100 characters"


def test_name_change_of_a_new_name_still_lowercases_for_comparison() -> None:
    assert validate_company_name_change("Acme Norte", "acme") == "Acme Norte"
    assert (
        normalize_company_name(validate_company_name_change("Acme Norte", "acme"))
        == "acme norte"
    )


# --- Correo de contacto (RF-127) -------------------------------------------


def _valid_email(length: int) -> str:
    """Correo sintacticamente valido con la longitud total pedida."""
    domain = "b" * 63 + "." + "c" * 63 + "." + "d" * (length - 64 - 1 - 63 - 1 - 63 - 1)
    return "a" * 64 + "@" + domain


def test_email_is_trimmed_and_lowercased() -> None:
    assert normalize_company_email("  Acme@Example.COM  ") == "acme@example.com"
    assert validate_company_email("  Acme@Example.COM  ") == "acme@example.com"


def test_email_accepts_254_characters_and_rejects_255() -> None:
    accepted = _valid_email(254)
    assert len(accepted) == 254
    assert validate_company_email(accepted) == accepted

    rejected = _valid_email(255)
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_email(rejected)
    assert _detail(exc) == "email exceeds 254 characters"


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_email_is_required(raw) -> None:
    with pytest.raises(CompanyDomainError) as exc:
        normalize_company_email(raw)
    assert _detail(exc) == "email is required"

    with pytest.raises(CompanyDomainError) as exc:
        validate_company_email(raw)
    assert _detail(exc) == "email is required"


def test_email_syntax_uses_the_identity_message() -> None:
    invalid = "not-an-email"
    with pytest.raises(ValueError) as identity_error:
        EmailValidator().validate(invalid)
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_email(invalid)
    assert _detail(exc) == str(identity_error.value)
    assert exc.value.detail.startswith("An email address must have an @-sign.")


# --- Persona de contacto (RF-127) ------------------------------------------


def test_contact_name_trims_and_accepts_limits() -> None:
    assert normalize_contact_name("  Ana Gómez  ") == "Ana Gómez"
    assert normalize_contact_name("AB") == "AB"
    assert normalize_contact_name("A" * 100) == "A" * 100


@pytest.mark.parametrize("raw", ["A", "A" * 101])
def test_contact_name_rejects_out_of_range(raw: str) -> None:
    with pytest.raises(CompanyDomainError) as exc:
        normalize_contact_name(raw)
    assert _detail(exc) == "contact name must have 2-100 characters"


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_blank_contact_name_is_null(raw) -> None:
    assert normalize_contact_name(raw) is None


# --- Telefono (RF-127) -----------------------------------------------------


def test_phone_trims_and_accepts_32_characters() -> None:
    assert normalize_phone("  +34 910 000 000  ") == "+34 910 000 000"
    assert normalize_phone("9" * 32) == "9" * 32


def test_phone_rejects_more_than_32_characters() -> None:
    with pytest.raises(CompanyDomainError) as exc:
        normalize_phone("9" * 33)
    assert _detail(exc) == "phone exceeds 32 characters"

    with pytest.raises(CompanyDomainError) as exc:
        normalize_phone("  " + "9" * 33 + "  ")
    assert _detail(exc) == "phone exceeds 32 characters"


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_blank_phone_is_null(raw) -> None:
    assert normalize_phone(raw) is None


# --- Alta (RF-126 y RF-127) ------------------------------------------------


def test_new_company_returns_normalized_contact_data() -> None:
    data = validate_new_company(
        "  Acme  ", "  Acme@Example.COM  ", "  555  " , "  Ana Gómez  "
    )
    assert isinstance(data, CompanyContactData)
    assert data == CompanyContactData(
        name="Acme",
        name_normalized="acme",
        email="acme@example.com",
        phone="555",
        contact_name="Ana Gómez",
    )


def test_new_company_without_optional_fields_keeps_them_null() -> None:
    data = validate_new_company("Acme", "acme@example.com")
    assert data.phone is None
    assert data.contact_name is None


def test_new_company_requires_a_usable_email() -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_new_company("Acme", None)
    assert _detail(exc) == "email is required"


# --- Actualizacion (RF-127 y RF-131) ---------------------------------------


def test_empty_update_is_rejected() -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_update()
    assert _detail(exc) == "at least one field is required"


def test_update_keeps_only_the_fields_received() -> None:
    assert validate_company_update(phone=" 555 ") == {"phone": "555"}
    assert validate_company_update(
        email="  Acme@Example.COM  "
    ) == {"email": "acme@example.com"}


def test_update_returns_the_new_normalized_name() -> None:
    assert validate_company_update(
        name="  Acme Norte  ", current_name_normalized="acme"
    ) == {"name": "Acme Norte", "name_normalized": "acme norte"}


def test_update_accepts_the_legacy_out_of_range_own_name() -> None:
    normalized = normalize_company_name(LONG_LEGACY_NAME)
    assert validate_company_update(
        name=LONG_LEGACY_NAME.lower(),
        current_name_normalized=normalized,
    ) == {
        "name": LONG_LEGACY_NAME.lower(),
        "name_normalized": normalized,
    }


def test_update_null_name_is_a_domain_error() -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_update(name=None, current_name_normalized="acme")
    assert _detail(exc) == "name must have 2-100 characters"


def test_update_null_or_blank_email_is_a_domain_error() -> None:
    for raw in (None, "", "   "):
        with pytest.raises(CompanyDomainError) as exc:
            validate_company_update(email=raw)
        assert _detail(exc) == "email is required"


def test_update_null_deletes_optional_fields() -> None:
    assert validate_company_update(phone=None) == {"phone": None}
    assert validate_company_update(contact_name=None) == {
        "contact_name": None
    }
    assert validate_company_update(phone="   ", contact_name="  ") == {
        "phone": None,
        "contact_name": None,
    }


def test_update_validates_each_field_with_its_message() -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_company_update(name="A", current_name_normalized="acme")
    assert _detail(exc) == "name must have 2-100 characters"

    with pytest.raises(CompanyDomainError) as exc:
        validate_company_update(phone="9" * 33)
    assert _detail(exc) == "phone exceeds 32 characters"

    with pytest.raises(CompanyDomainError) as exc:
        validate_company_update(contact_name="A")
    assert _detail(exc) == "contact name must have 2-100 characters"

    with pytest.raises(CompanyDomainError) as exc:
        validate_company_update(email="not-an-email")
    assert "must have an @-sign" in _detail(exc)


def test_update_omitted_optional_fields_are_not_returned() -> None:
    changes = validate_company_update(
        name="Acme", current_name_normalized="acme"
    )
    assert set(changes) == {"name", "name_normalized"}


# --- Rama de reenvio de la invitacion (RF-141) -----------------------------


def test_resend_accepts_an_empty_body() -> None:
    assert validate_resend_payload() is None


@pytest.mark.parametrize("name", ["Acme", "", None])
def test_resend_rejects_name(name) -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_resend_payload(name=name)
    assert _detail(exc) == "resend does not accept name or email"


@pytest.mark.parametrize("email", ["acme@example.com", "", None])
def test_resend_rejects_email(email) -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_resend_payload(email=email)
    assert _detail(exc) == "resend does not accept name or email"


# --- Rama de invitacion de la administradora (RF-141) ---------------------


def test_invitation_returns_normalized_administrator_data() -> None:
    data = validate_invitation_payload(
        name="  Ana Gómez  ", email="  Ana@Example.COM  "
    )
    assert isinstance(data, CompanyAdministratorData)
    assert data == CompanyAdministratorData(
        name="Ana Gómez", email="ana@example.com"
    )


def test_invitation_requires_both_usable_values() -> None:
    for name, email in (
        (MISSING, "ana@example.com"),
        ("Ana Gómez", MISSING),
        (None, None),
        ("   ", "ana@example.com"),
        ("Ana Gómez", "   "),
        (MISSING, MISSING),
    ):
        with pytest.raises(CompanyDomainError) as exc:
            validate_invitation_payload(name=name, email=email)
        assert _detail(exc) == "name and email are required"


def test_invitation_validates_values_that_are_usable() -> None:
    with pytest.raises(CompanyDomainError) as exc:
        validate_invitation_payload(name="A", email="ana@example.com")
    assert _detail(exc) == "name must have 2-100 characters"

    with pytest.raises(CompanyDomainError) as exc:
        validate_invitation_payload(name="Ana Gómez", email="not-an-email")
    assert "must have an @-sign" in _detail(exc)


# --- Forma del error de dominio (RF-137) -----------------------------------


def test_domain_error_carries_a_string_detail() -> None:
    error = CompanyDomainError("algo invalido")
    assert error.detail == "algo invalido"
    assert str(error) == "algo invalido"
    assert isinstance(error, ValueError)


def test_application_errors_exports_the_domain_error() -> None:
    assert CompanyDomainError is domain_errors.CompanyDomainError
