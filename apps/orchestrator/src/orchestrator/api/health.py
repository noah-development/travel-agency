import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from orchestrator.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Always 200 as long as the process can handle a request at all."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(settings: Settings = Depends(get_settings)) -> JSONResponse:  # noqa: B008
    """200 only if config loaded (implied by the Depends above succeeding)
    AND Keycloak's JWKS endpoint is reachable.

    Does not verify any token itself; see auth/jwt.py for that (still
    unimplemented). This check is deliberately independent of auth/jwt.py
    so /ready stays fully real without pre-deciding that module's JWKS
    caching strategy.
    """
    keycloak_ok = await _check_keycloak_jwks_reachable(settings)
    checks = {"config": True, "keycloak_jwks": keycloak_ok}
    status_code = 200 if all(checks.values()) else 503
    return JSONResponse(status_code=status_code, content={"checks": checks})


async def _check_keycloak_jwks_reachable(settings: Settings) -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            discovery_response = await client.get(settings.keycloak_discovery_url)
            discovery_response.raise_for_status()
            jwks_uri = discovery_response.json()["jwks_uri"]
            jwks_response = await client.get(jwks_uri)
            jwks_response.raise_for_status()
            return bool(jwks_response.json().get("keys"))
    except (httpx.HTTPError, KeyError, ValueError):
        return False
