import json

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient as StarletteTestClient

from orchestrator.config import Settings
from orchestrator.logging import RequestContextMiddleware, configure_logging, logger


def test_configure_logging_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(_env_file=None, anthropic_api_key="x", keycloak_url="http://localhost:8080")
    configure_logging(settings)
    logger.info("test_event", foo="bar")
    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "test_event"
    assert payload["foo"] == "bar"
    assert "timestamp" in payload
    assert payload["level"] == "info"


def _build_ping_app() -> Starlette:
    async def endpoint(request):
        return PlainTextResponse("ok")

    ping_app = Starlette(routes=[Route("/ping", endpoint)])
    ping_app.add_middleware(RequestContextMiddleware)
    return ping_app


def test_request_context_middleware_generates_request_id() -> None:
    with StarletteTestClient(_build_ping_app()) as test_client:
        response = test_client.get("/ping")
    assert response.status_code == 200
    assert response.headers["x-request-id"]


def test_request_context_middleware_preserves_incoming_request_id() -> None:
    with StarletteTestClient(_build_ping_app()) as test_client:
        response = test_client.get("/ping", headers={"X-Request-Id": "fixed-id-123"})
    assert response.headers["x-request-id"] == "fixed-id-123"
