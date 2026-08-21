# orchestrator

LLM trip-planning orchestrator service (FastAPI). See
[docs/decisions/0005-orchestrator-scaffolding.md](../../docs/decisions/0005-orchestrator-scaffolding.md)
for what's scaffolded vs. hand-written, and
[docs/decisions/0004-identity-two-realms.md](../../docs/decisions/0004-identity-two-realms.md)
for the Keycloak identity model this service authenticates against.

## Run locally

Native, not Docker — this service runs directly on Windows during
development (see ADR 0001/0003); Docker is reserved for local infra
(Postgres, Keycloak) and for CI/deployment of this service's image.

From the **repo root** (config.py resolves `.env` relative to the current
working directory):

```
uv sync --all-packages
uv run uvicorn orchestrator.main:app --reload --no-access-log
```

Requires a `.env` file at the repo root with real values — copy
`.env.example` and fill it in (`ANTHROPIC_API_KEY` at minimum; Keycloak
must be reachable at `KEYCLOAK_URL` for `/ready` and for any authenticated
request, once auth is implemented). Run `python tools/dev.py up` first to
bring up local Keycloak/Postgres.

`GET /health` responds 200 as soon as the process is up. `GET /ready`
additionally checks that Keycloak's JWKS endpoint is reachable.

## Run tests

From the repo root:

```
uv run pytest apps/orchestrator
```

(or bare `uv run pytest` to run the whole workspace).

## Pendiente de implementación

Cuatro piezas se dejaron deliberadamente sin implementar — firma, tipos,
docstring con una sección "Consideraciones", y
`raise NotImplementedError("lo escribe el usuario")`. Cada una tiene tests
`xfail(strict=True)` en `tests/` que documentan el contrato esperado.

| Pieza | Archivo:línea del `raise NotImplementedError` | `# TODO(usuario)` | Función/clase |
| --- | --- | --- | --- |
| A — Llamada al modelo de Anthropic | `src/orchestrator/llm/client.py:44` | `src/orchestrator/llm/client.py:41` | `call_anthropic_model` |
| B — Schema Pydantic de la respuesta de viaje | N/A (ver nota abajo) | `src/orchestrator/llm/schemas.py:44` | `TripPlan` |
| C — Política de reintentos / manejo de errores | `src/orchestrator/llm/client.py:82` | `src/orchestrator/llm/client.py:79` | `call_with_retries` |
| D — Validación del JWT de Keycloak | `src/orchestrator/auth/jwt.py:90` | `src/orchestrator/auth/jwt.py:87` | `verify_access_token` |

**Nota sobre la pieza B**: a diferencia de las otras tres, `TripPlan` es
una clase Pydantic, no una función — un `raise NotImplementedError`
literal en el cuerpo de la clase rompería el arranque de toda la app (el
cuerpo de una clase se ejecuta al importarla). Por eso `TripPlan` es un
`BaseModel` real pero vacío (`extra="forbid"`): no implementa nada
funcional, pero es import-seguro. Ver
[docs/decisions/0005-orchestrator-scaffolding.md](../../docs/decisions/0005-orchestrator-scaffolding.md).

`POST /trips/plan` responde **500 hoy** (vía el `NotImplementedError`
propagado desde `call_with_retries`) — esperado hasta que las cuatro
piezas de arriba estén implementadas.
