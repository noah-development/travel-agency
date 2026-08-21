import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from orchestrator.auth import dependencies
from orchestrator.auth.jwt import InvalidAudienceError, TokenValidationError
from orchestrator.config import Settings


def _build_protected_app() -> FastAPI:
    protected_app = FastAPI()

    @protected_app.get("/protected")
    async def protected(claims: dict = Depends(dependencies.get_current_claims)) -> dict:  # noqa: B008
        return {"claims": claims}

    return protected_app


@pytest.fixture
def protected_client(settings_env: None) -> TestClient:
    return TestClient(_build_protected_app(), raise_server_exceptions=False)


def test_missing_authorization_header_returns_401(protected_client: TestClient) -> None:
    response = protected_client.get("/protected")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_malformed_authorization_header_returns_401(protected_client: TestClient) -> None:
    response = protected_client.get("/protected", headers={"Authorization": "Token abc"})
    assert response.status_code == 401
    assert "invalid_request" in response.headers["www-authenticate"]


def test_valid_token_returns_claims(
    protected_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_verify(token: str, *, settings: Settings) -> dict:
        return {"sub": "user-1"}

    monkeypatch.setattr(dependencies, "verify_access_token", fake_verify)

    response = protected_client.get("/protected", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json() == {"claims": {"sub": "user-1"}}


def test_token_validation_error_returns_401(
    protected_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_verify(token: str, *, settings: Settings) -> dict:
        raise TokenValidationError("bad token")

    monkeypatch.setattr(dependencies, "verify_access_token", fake_verify)

    response = protected_client.get("/protected", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401
    assert "invalid_token" in response.headers["www-authenticate"]


def test_invalid_audience_returns_403(
    protected_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_verify(token: str, *, settings: Settings) -> dict:
        raise InvalidAudienceError("wrong audience")

    monkeypatch.setattr(dependencies, "verify_access_token", fake_verify)

    response = protected_client.get(
        "/protected", headers={"Authorization": "Bearer wrong-aud-token"}
    )

    assert response.status_code == 403
