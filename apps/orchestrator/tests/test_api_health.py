import httpx
import respx
from fastapi.testclient import TestClient

from orchestrator.config import get_settings


def test_health_always_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@respx.mock
def test_ready_ok_when_keycloak_reachable(client: TestClient) -> None:
    settings = get_settings()
    jwks_uri = f"{settings.keycloak_url}/realms/{settings.keycloak_customers_realm}/protocol/jwks"
    respx.get(settings.keycloak_discovery_url).mock(
        return_value=httpx.Response(200, json={"jwks_uri": jwks_uri})
    )
    respx.get(jwks_uri).mock(return_value=httpx.Response(200, json={"keys": [{"kid": "abc"}]}))

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"config": True, "keycloak_jwks": True}


@respx.mock
def test_ready_503_when_keycloak_unreachable(client: TestClient) -> None:
    settings = get_settings()
    respx.get(settings.keycloak_discovery_url).mock(side_effect=httpx.ConnectError("boom"))

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"config": True, "keycloak_jwks": False}
