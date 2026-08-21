from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from orchestrator.auth.dependencies import get_current_claims
from orchestrator.config import Settings, get_settings
from orchestrator.llm import client as llm_client
from orchestrator.llm.schemas import TripPlan
from orchestrator.logging import logger

router = APIRouter()


class TripPlanRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


@router.post("/plan", response_model=TripPlan)
async def plan_trip(
    body: TripPlanRequest,
    claims: dict = Depends(get_current_claims),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> TripPlan:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be empty")

    # Never log claims/token wholesale -- only non-sensitive metadata.
    logger.info("trip_plan_requested", subject=claims.get("sub"))

    # TODO(usuario): once llm.client.call_with_retries (Piece C, which
    # wraps Piece A) is implemented, this call succeeds; today it raises
    # NotImplementedError, surfaced by FastAPI as a 500.
    trip_plan = await llm_client.call_with_retries(query=query, settings=settings)

    return trip_plan
