import pytest

from app.main import initialize_database


def test_missing_database_configuration_requires_explicit_unit_fallback(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL o POSTGRES_PASSWORD"):
        initialize_database()

    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    initialize_database()
