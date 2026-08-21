from fastapi.testclient import TestClient

from orchestrator.auth.dependencies import get_current_claims
from orchestrator.main import app


def test_plan_trip_without_token_returns_401(client: TestClient) -> None:
    response = client.post("/trips/plan", json={"query": "a week in Japan"})
    assert response.status_code == 401


def test_plan_trip_with_auth_override_returns_500_today(client: TestClient) -> None:
    """The orchestration skeleton is fully wired: with auth stubbed out via
    a dependency override, the request reaches llm.client.call_with_retries
    (Piece C), which today raises NotImplementedError -- surfaced by
    FastAPI as a 500. This is expected until the user implements the four
    pieces."""
    app.dependency_overrides[get_current_claims] = lambda: {"sub": "user-1"}
    try:
        response = client.post("/trips/plan", json={"query": "a week in Japan"})
    finally:
        app.dependency_overrides.pop(get_current_claims, None)
    assert response.status_code == 500
