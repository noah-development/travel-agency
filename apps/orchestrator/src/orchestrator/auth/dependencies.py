from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request

from orchestrator.auth.jwt import InvalidAudienceError, TokenValidationError, verify_access_token
from orchestrator.config import Settings, get_settings


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("authorization")
    if not header:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Authorization header must be 'Bearer <token>'",
            headers={"WWW-Authenticate": 'Bearer error="invalid_request"'},
        )
    return token


async def get_current_claims(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> dict[str, Any]:
    """FastAPI dependency: extracts the bearer token, delegates
    cryptographic verification to auth.jwt.verify_access_token (Piece D,
    currently unimplemented), and translates its errors into 401/403.

    Never logs the token or the returned claims wholesale.
    """
    token = _extract_bearer_token(request)
    try:
        return await verify_access_token(token, settings=settings)
    except InvalidAudienceError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TokenValidationError as exc:
        www_authenticate = f'Bearer error="invalid_token", error_description="{exc}"'
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"WWW-Authenticate": www_authenticate},
        ) from exc
