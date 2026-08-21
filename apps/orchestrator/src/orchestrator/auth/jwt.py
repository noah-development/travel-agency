"""Keycloak JWT verification.

The only real code allowed in this file is the exception hierarchy below
(TokenValidationError, InvalidAudienceError) -- it exists purely as the
interface auth/dependencies.py needs to catch and translate into 401/403,
and stays deliberately empty: no attributes, no custom __init__, no
logic. verify_access_token itself -- the actual cryptographic
verification -- is written by the user.
"""

from typing import Any

from orchestrator.config import Settings


class TokenValidationError(Exception):
    """Any token validation failure other than a wrong audience (see
    InvalidAudienceError below). auth/dependencies.py maps this to HTTP
    401 with WWW-Authenticate: Bearer error="invalid_token"."""

    pass


class InvalidAudienceError(TokenValidationError):
    """Signature, issuer, and expiry are all valid, but `aud` does not
    contain the resource-server client id. auth/dependencies.py maps
    this to HTTP 403 (the token authenticates someone real in this
    realm, just not for this API)."""

    pass


async def verify_access_token(token: str, *, settings: Settings) -> dict[str, Any]:
    """Verifica criptograficamente un access token JWT emitido por
    Keycloak y devuelve sus claims.

    Recibe:
        token: el bearer token crudo, ya extraido del header
            Authorization por auth/dependencies.py (esta funcion nunca
            toca el header en si).
        settings: config de la app (keycloak_url,
            keycloak_customers_realm, keycloak_customers_api_client).

    Devuelve:
        Las claims del token como dict, una vez verificadas firma,
        issuer, audiencia y expiracion.

    Raises:
        InvalidAudienceError: firma/issuer/expiracion validos, pero `aud`
            no contiene settings.keycloak_customers_api_client
            ("orchestrator-api") -- ver
            docs/decisions/0004-identity-two-realms.md: un token valido
            por firma e issuer pero emitido para otro cliente del mismo
            realm debe seguir siendo rechazado.
        TokenValidationError: cualquier otro fallo -- firma invalida o no
            verificable, `kid` desconocido, token expirado, `iss`
            incorrecto, o un token estructuralmente invalido.

    Consideraciones:
    - Validacion de firma con JWKS cacheado: traer y cachear el JWKS del
      realm (indexado por `kid`), con un TTL y/o una estrategia de
      refresh-on-unknown-kid, en vez de pedir el JWKS en cada request.
      Los access tokens son de vida corta (~5 min, defaults de Keycloak,
      ver ADR 0004) -- eso afecta al diseno del cache del JWKS en si (que
      rota rara vez), no al de tokens decodificados (que expiran casi tan
      rapido como cualquier TTL de cache razonable).
    - `iss` debe ser exactamente settings.keycloak_issuer
      (f"{keycloak_url}/realms/{keycloak_customers_realm}").
    - `aud` debe contener settings.keycloak_customers_api_client
      ("orchestrator-api"), no solo ser no-vacio -- validar la
      pertenencia explicitamente (Keycloak puede emitir `aud` como
      lista), igual que hace tools/verify_auth.py, en vez de confiar en
      el verify_aud incorporado de PyJWT contra un unico string
      esperado.
    - Verificacion de exp/nbf/iat y tolerancia de reloj (`leeway` de
      PyJWT).
    - Usar PyJWKClient de PyJWT (sincrono, bloqueante) vs. un fetch
      basado en httpx.AsyncClient para no bloquear el event loop de
      FastAPI.
    - Que pasa si falla el fetch del JWKS en si (red caida, Keycloak
      abajo): distinguirlo de un token realmente invalido --
      probablemente un 5xx y no un 401/403, lo cual implica que esta
      funcion debe lanzar algo que auth/dependencies.py pueda
      diferenciar de TokenValidationError/InvalidAudienceError (p. ej. no
      capturarlo ahi y dejar que se propague como 500).

    # TODO(usuario): implementar fetch/cache de JWKS + verificacion de
    # firma/iss/aud/exp aqui.
    """
    raise NotImplementedError("lo escribe el usuario")
