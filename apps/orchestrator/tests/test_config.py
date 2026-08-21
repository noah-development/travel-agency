import pytest

from orchestrator.config import get_settings


def test_missing_required_var_raises_runtime_error(
    isolated_cwd: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The host shell may already export these (e.g. for other tooling) --
    # delete them explicitly rather than relying on them being unset.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("KEYCLOAK_URL", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        get_settings()


def test_defaults(settings_env: None) -> None:
    settings = get_settings()
    assert settings.anthropic_model == "claude-haiku-4-5"
    assert settings.keycloak_customers_realm == "travel-customers"
    assert settings.keycloak_customers_api_client == "orchestrator-api"
    assert settings.log_level == "INFO"
    assert settings.environment == "development"


def test_keycloak_issuer_and_discovery_url(settings_env: None) -> None:
    settings = get_settings()
    assert settings.keycloak_issuer == "http://localhost:8080/realms/travel-customers"
    assert settings.keycloak_discovery_url == (
        "http://localhost:8080/realms/travel-customers/.well-known/openid-configuration"
    )
