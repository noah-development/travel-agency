Construye el ANDAMIAJE del servicio orquestador en apps/orchestrator. Este prompt tiene una restricción central que domina todo lo demás:

HAY CUATRO PIEZAS QUE NO DEBES IMPLEMENTAR. Las voy a escribir yo a mano. Para cada una dejas la firma, el docstring, los tipos, y el cuerpo con `raise NotImplementedError("lo escribe el usuario")` más un comentario `# TODO(usuario)` explicando qué va ahí. No las implementes "para que compile", no dejes una versión mínima "de referencia", no las completes aunque parezcan triviales. Si al terminar alguna de las cuatro tiene código funcional, el entregable está mal.

Las cuatro son:
  A) La llamada al modelo de Anthropic.
  B) El modelo Pydantic de la respuesta estructurada de viaje.
  C) La política de reintentos y manejo de errores de la llamada al LLM.
  D) La validación del JWT de Keycloak.

--- LO QUE SÍ CONSTRUYES ---

1. ESTRUCTURA
apps/orchestrator/
  src/orchestrator/
    main.py            -> app FastAPI, routers montados, lifespan
    config.py          -> settings con pydantic-settings
    logging.py         -> logging estructurado en JSON
    api/
      health.py        -> /health y /ready, implementados de verdad
      trips.py         -> el endpoint principal (esqueleto, ver abajo)
    llm/
      client.py        -> PIEZA A y C van aquí
      schemas.py       -> PIEZA B va aquí
    auth/
      jwt.py           -> PIEZA D va aquí
      dependencies.py  -> dependencia de FastAPI que consume jwt.py
  tests/
  pyproject.toml
  Dockerfile

Miembro del workspace de uv que ya existe en la raíz.

2. DEPENDENCIAS
fastapi, uvicorn[standard], pydantic, pydantic-settings, anthropic, httpx, PyJWT[crypto], structlog. Para tests: pytest, pytest-asyncio, respx (o el mock de httpx que prefieras). Fija versiones mínimas razonables, no pines exactos.

3. CONFIGURACIÓN (config.py, completo)
Settings con pydantic-settings leyendo del .env de la raíz. Campos: ANTHROPIC_API_KEY, ANTHROPIC_MODEL (default claude-haiku-4-5, modelo barato para desarrollo), KEYCLOAK_URL, KEYCLOAK_CUSTOMERS_REALM, KEYCLOAK_CUSTOMERS_API_CLIENT, LOG_LEVEL, ENVIRONMENT.
Falla al arrancar si falta algo obligatorio, con mensaje que diga qué variable falta. Un servicio que arranca a medias y falla en la primera petición es peor que uno que no arranca.
Actualiza .env.example con lo nuevo.

4. LOGGING (logging.py, completo)
structlog emitiendo JSON. Cada log lleva request_id (generado por middleware si no viene en el header), path, método, status y duración. Configura para que el request_id se propague por contexto sin pasarlo como argumento.
NUNCA loguear el contenido de tokens, el API key, ni el cuerpo completo de las respuestas del LLM.

5. HEALTH (health.py, completo)
/health devuelve 200 siempre que el proceso viva. /ready verifica que la configuración cargó y que el JWKS de Keycloak es alcanzable. Son distintos y el Dockerfile y el compose usan /health.

6. EL ENDPOINT (trips.py, esqueleto)
POST /trips/plan. Recibe un request con la consulta en lenguaje natural. Protegido por la dependencia de auth.
El cuerpo del handler queda como orquestación explícita: valida entrada, llama al cliente de LLM, devuelve la respuesta. Las llamadas a las piezas A-D quedan escritas como invocaciones a funciones que aún no existen o que lanzan NotImplementedError. Quiero ver el flujo completo aunque no corra.

7. PIEZAS A, B, C, D — SOLO FIRMAS
En cada una escribe:
  - La firma completa con type hints.
  - Un docstring que describa qué debe hacer, qué recibe y qué devuelve.
  - En el docstring de cada una, una sección "Consideraciones" listando las decisiones que tengo que tomar. Ejemplos de lo que espero ahí:
      A: streaming vs. no streaming, dónde vive el system prompt, manejo del context window.
      B: qué campos tiene un itinerario mínimo, qué es opcional, cómo se representa una fecha ambigua.
      C: qué errores son transitorios y cuáles no, backoff, presupuesto máximo de reintentos, qué hacer al agotarlo.
      D: validar firma contra JWKS con caché, y validar iss, aud y exp. Menciona explícitamente que aud debe verificarse contra el client id del resource server, no solo la firma.
  - `raise NotImplementedError("lo escribe el usuario")`.
  - Un comentario `# TODO(usuario): ...`

Para la PIEZA D, además: escribe `dependencies.py` COMPLETO. La dependencia de FastAPI que extrae el bearer del header, llama a la función de jwt.py y traduce los errores a 401/403 con el WWW-Authenticate correcto sí la implementas — lo que no implementas es la verificación criptográfica en sí.

8. TESTS (completos, y deben FALLAR)
Escribe los tests de las cuatro piezas contra el comportamiento esperado según los docstrings. Deben fallar hoy con NotImplementedError y pasar cuando yo escriba las implementaciones. Son mi especificación ejecutable.
Marca esos tests con `@pytest.mark.xfail(strict=True, reason="pendiente de implementación por el usuario")` para que la suite quede verde y CI no se rompa, pero avise si alguno empieza a pasar sin que se haya quitado la marca.
Los tests de health, config y logging sí deben pasar hoy.

9. DOCKERFILE
Multi-stage con uv, imagen final slim, usuario no-root, healthcheck contra /health. No lo agregues al compose: el servicio corre nativo en Windows durante desarrollo, esto es para CI y despliegue.

10. DOCUMENTACIÓN
apps/orchestrator/README.md con: cómo correr en local (uvicorn con reload, nativo, no en Docker), cómo correr los tests, y una sección "Pendiente de implementación" listando las cuatro piezas con su archivo y línea.

11. Un ADR docs/decisions/0005-orchestrator-scaffolding.md (prosa en español) explicando el reparto: qué se generó y qué se escribe a mano, con la razón.

--- VERIFICACIÓN ---
- `uv run uvicorn` levanta el servicio y /health responde 200.
- `uv run pytest` pasa, con los tests de las cuatro piezas marcados xfail.
- ruff y check_portability limpios.
- /trips/plan devuelve 500 o NotImplementedError, que es lo esperado hoy.

Al terminar, reporta la lista exacta de archivo:línea donde quedó cada TODO(usuario).