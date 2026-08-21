import httpx
import pytest
import respx

from orchestrator.auth.jwt import InvalidAudienceError, TokenValidationError, verify_access_token
from orchestrator.config import Settings


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        keycloak_url="http://localhost:8080",
        keycloak_customers_realm="travel-customers",
        keycloak_customers_api_client="orchestrator-api",
    )


def _mock_discovery_and_jwks(settings: Settings, jwks: dict) -> None:
    jwks_uri = f"{settings.keycloak_url}/realms/{settings.keycloak_customers_realm}/protocol/jwks"
    respx.get(settings.keycloak_discovery_url).mock(
        return_value=httpx.Response(200, json={"jwks_uri": jwks_uri})
    )
    respx.get(jwks_uri).mock(return_value=httpx.Response(200, json=jwks))


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
@pytest.mark.asyncio
@respx.mock
async def test_valid_token_returns_claims(signed_token, jwks_payload) -> None:
    settings = _settings()
    token = signed_token(iss=settings.keycloak_issuer, aud=settings.keycloak_customers_api_client)
    _mock_discovery_and_jwks(settings, jwks_payload())

    claims = await verify_access_token(token, settings=settings)

    assert claims["iss"] == settings.keycloak_issuer
    assert claims["sub"] == "test-user"


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
@pytest.mark.asyncio
@respx.mock
async def test_wrong_audience_raises_invalid_audience_error(signed_token, jwks_payload) -> None:
    settings = _settings()
    token = signed_token(iss=settings.keycloak_issuer, aud="some-other-client")
    _mock_discovery_and_jwks(settings, jwks_payload())

    with pytest.raises(InvalidAudienceError):
        await verify_access_token(token, settings=settings)


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
@pytest.mark.asyncio
@respx.mock
async def test_expired_token_raises_token_validation_error(signed_token, jwks_payload) -> None:
    settings = _settings()
    token = signed_token(
        iss=settings.keycloak_issuer, aud=settings.keycloak_customers_api_client, exp_delta=-60
    )
    _mock_discovery_and_jwks(settings, jwks_payload())

    with pytest.raises(TokenValidationError):
        await verify_access_token(token, settings=settings)


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
@pytest.mark.asyncio
@respx.mock
async def test_wrong_issuer_raises_token_validation_error(signed_token, jwks_payload) -> None:
    settings = _settings()
    token = signed_token(
        iss=f"{settings.keycloak_url}/realms/travel-admin",
        aud=settings.keycloak_customers_api_client,
    )
    _mock_discovery_and_jwks(settings, jwks_payload())

    with pytest.raises(TokenValidationError):
        await verify_access_token(token, settings=settings)
