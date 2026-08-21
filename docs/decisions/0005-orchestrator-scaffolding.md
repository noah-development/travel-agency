# 0005 - Orchestrator: scaffolding generado vs. piezas escritas a mano

## Status

Accepted

## Context

`apps/orchestrator` necesitaba un primer esqueleto completo: estructura de
FastAPI, configuración, logging estructurado, health checks, Dockerfile,
tests y documentación. Pero cuatro decisiones dentro de ese servicio tienen
consecuencias que su autor debe entender a fondo, no delegar en una
generación automática: la llamada al modelo de Anthropic (streaming,
dónde vive el system prompt, cómo se fuerza el schema de salida), el
schema Pydantic de la respuesta de viaje (qué campos son el mínimo viable,
cómo se representa una fecha ambigua), la política de reintentos ante
fallos del LLM (qué es transitorio, cuánto backoff, qué hacer al agotar el
presupuesto), y la verificación criptográfica del JWT de Keycloak (cache
de JWKS, validación estricta de `iss`/`aud`/`exp`). Generar estas cuatro
piezas "para que compile" habría producido una versión de referencia que
el autor nunca revisaría con el mismo cuidado que si la escribe él mismo,
y en el caso de la pieza D eso es particularmente peligroso: un fallo
sutil en la verificación de audiencia es exactamente el tipo de bug que
[0004-identity-two-realms.md](0004-identity-two-realms.md) diseñó para
evitar a nivel de infraestructura (dos realms separados), pero que sigue
siendo posible a nivel de código si la verificación de `aud` es
descuidada.

## Decision

Se generó completo todo lo que no requiere una decisión de diseño propia
del dominio: la estructura del paquete, `config.py` (falla rápido si falta
una variable obligatoria), `logging.py` (JSON estructurado vía structlog,
`request_id` propagado por contextvars, nunca se loguean tokens ni
respuestas completas del LLM), `api/health.py` (`/health` y `/ready`
reales), el esqueleto de `api/trips.py` (orquestación explícita, ya
conectada a las piezas sin implementar), `auth/dependencies.py` (traducción
de errores a 401/403, ya real), el `Dockerfile`, los tests, y este ADR.

Las cuatro piezas -- llamada a Anthropic, schema `TripPlan`, política de
reintentos, verificación JWT -- se dejaron como firma completa, docstring
con una sección "Consideraciones" listando las decisiones pendientes, y
`raise NotImplementedError("lo escribe el usuario")` con un comentario
`# TODO(usuario)`. La única excepción real permitida en `auth/jwt.py` es
la jerarquía de dos excepciones (`TokenValidationError`,
`InvalidAudienceError`) que `auth/dependencies.py` necesita para traducir
errores a HTTP -- y esa jerarquía se mantiene deliberadamente vacía
(docstring + `pass`, sin atributos, sin lógica): es la interfaz mínima que
hace falta para que el resto del servicio compile, no una implementación
adelantada de la pieza.

**Desviación documentada en la pieza B (`TripPlan`):** un `raise
NotImplementedError` literal en el cuerpo de la clase se ejecutaría al
importar el módulo (el cuerpo de una clase corre al definirla, no al
usarla), lo cual habría roto el arranque de toda la aplicación --
contradiciendo el propio requisito de que `/health` responda 200 hoy. En
su lugar, `TripPlan` es un `BaseModel` real, vacío, con
`extra="forbid"`: import-seguro, pero no valida ningún payload real hoy
(cualquier intento produce `pydantic.ValidationError`). Sigue llevando el
docstring completo con su sección "Consideraciones" y el
`# TODO(usuario)`.

Cada pieza se probó contra el contrato descrito en su propio docstring,
con tests marcados `xfail(strict=True, reason="pendiente de
implementación por el usuario")` -- son la especificación ejecutable, no
un placeholder. En particular, la política de reintentos (pieza C) recibió
la misma cobertura que la llamada al LLM (pieza A): error transitorio
reintenta, error permanente no reintenta y propaga, agotar el presupuesto
de reintentos propaga un error (nunca un `TripPlan` vacío ni `None`), y el
backoff entre intentos se verifica con un reloj simulado, sin dormir de
verdad en la suite.

## Consequences

- `uv run uvicorn orchestrator.main:app` arranca y `/health` responde 200
  hoy mismo; `/ready` depende de que Keycloak esté arriba.
- `POST /trips/plan` responde 500 hoy, vía el `NotImplementedError`
  propagado desde `llm.client.call_with_retries` -- esperado hasta que las
  cuatro piezas se implementen.
- `uv run pytest` queda verde hoy: los tests reales (config, logging,
  health, `auth/dependencies.py`, el wiring de `trips.py`) pasan; los tres
  archivos que cubren las piezas A/B/C/D quedan `xfail(strict=True)` y
  avisarán (falla de CI) si alguno empieza a pasar sin que se haya
  quitado la marca -- señal de que el docstring quedó desactualizado
  respecto a la implementación real, o de que se implementó algo sin
  querer.
- Cualquier scaffold futuro en este repo con piezas deliberadamente sin
  implementar debe seguir el mismo patrón: código de soporte mínimo y
  explícitamente marcado como tal, y tests `xfail(strict=True)` con el
  mismo nivel de detalle para todas las piezas, no solo para la más
  obvia.
