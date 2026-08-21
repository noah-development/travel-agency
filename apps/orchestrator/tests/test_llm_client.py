"""Executable specification for Pieces A (call_anthropic_model) and C
(call_with_retries). Piece C gets the same level of scrutiny as Piece A --
these are not smoke tests, each one pins down a specific behavior
described in call_with_retries's own docstring.

Transient/permanent failures are stood in with builtin TimeoutError /
PermissionError rather than real anthropic.* exception types, since the
exact transient-vs-permanent classification (which real anthropic.*Error
subclasses count as which) is itself part of what the user decides when
implementing Piece C -- these tests pin down the *retry policy's*
behavior given a transient vs. a permanent failure, not the exact
exception taxonomy.
"""

import httpx
import pytest
import respx

from orchestrator.config import Settings
from orchestrator.llm import client as llm_client
from orchestrator.llm.schemas import TripPlan


def _settings() -> Settings:
    return Settings(
        _env_file=None, anthropic_api_key="sk-ant-test", keycloak_url="http://localhost:8080"
    )


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
@pytest.mark.asyncio
@respx.mock
async def test_call_anthropic_model_returns_validated_trip_plan() -> None:
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "{}"}],
                "model": "claude-haiku-4-5",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )
    )
    result = await llm_client.call_anthropic_model("plan a trip to Japan", settings=_settings())
    assert isinstance(result, TripPlan)


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
@pytest.mark.asyncio
async def test_retries_on_transient_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def flaky(query: str, *, settings: Settings) -> TripPlan:
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("transient: simulated APITimeoutError/RateLimitError/5xx")
        return TripPlan()

    monkeypatch.setattr(llm_client, "call_anthropic_model", flaky)

    result = await llm_client.call_with_retries("plan a trip", settings=_settings())

    assert calls["count"] == 2
    assert isinstance(result, TripPlan)


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
@pytest.mark.asyncio
async def test_does_not_retry_permanent_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def always_permanent(query: str, *, settings: Settings) -> TripPlan:
        calls["count"] += 1
        raise PermissionError("permanent: simulated AuthenticationError/BadRequestError")

    monkeypatch.setattr(llm_client, "call_anthropic_model", always_permanent)

    with pytest.raises(PermissionError):
        await llm_client.call_with_retries("plan a trip", settings=_settings())

    assert calls["count"] == 1


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
@pytest.mark.asyncio
async def test_propagates_error_when_retry_budget_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    async def always_transient(query: str, *, settings: Settings) -> TripPlan:
        calls["count"] += 1
        raise TimeoutError("transient: simulated APITimeoutError")

    monkeypatch.setattr(llm_client, "call_anthropic_model", always_transient)

    # Exhausting the retry budget must propagate an error -- never return
    # None or an empty TripPlan silently.
    with pytest.raises(TimeoutError):
        await llm_client.call_with_retries("plan a trip", settings=_settings())

    assert calls["count"] >= 2  # at least one retry actually happened


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
@pytest.mark.asyncio
async def test_backoff_sleeps_between_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    calls = {"count": 0}

    async def flaky_twice(query: str, *, settings: Settings) -> TripPlan:
        calls["count"] += 1
        if calls["count"] < 3:
            raise TimeoutError("transient: simulated APITimeoutError")
        return TripPlan()

    monkeypatch.setattr(llm_client, "call_anthropic_model", flaky_twice)

    result = await llm_client.call_with_retries("plan a trip", settings=_settings())

    assert isinstance(result, TripPlan)
    assert len(sleep_calls) >= 2  # one backoff sleep before each of the two retries
    assert all(delay > 0 for delay in sleep_calls)
    # asyncio.sleep is faked above -- this test must not actually sleep in
    # wall-clock time regardless of the backoff strategy chosen.
