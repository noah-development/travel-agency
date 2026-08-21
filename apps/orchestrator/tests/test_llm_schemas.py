import pytest

from orchestrator.llm.schemas import TripPlan


@pytest.mark.xfail(strict=True, reason="pendiente de implementacion por el usuario")
def test_trip_plan_validates_minimal_itinerary() -> None:
    """TripPlan currently has zero fields and extra="forbid", so this
    raises pydantic.ValidationError today. The payload below documents
    the *shape* expected once the user decides Piece B's real fields
    (see the "Consideraciones" in llm/schemas.py) -- the exact keys here
    are illustrative, not a spec the user must match verbatim."""
    plan = TripPlan.model_validate(
        {
            "destination": "Cancun",
            "start_date": "2026-09-01",
            "end_date": "2026-09-10",
        }
    )
    assert plan.destination == "Cancun"
