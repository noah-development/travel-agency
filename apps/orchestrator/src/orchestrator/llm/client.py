from orchestrator.config import Settings
from orchestrator.llm.schemas import TripPlan


async def call_anthropic_model(query: str, *, settings: Settings) -> TripPlan:
    """Llama una vez (sin reintentos -- ver call_with_retries) al modelo
    de Anthropic con `query` como turno del usuario, pidiendo una
    respuesta estructurada conforme a TripPlan (Pieza B), y devuelve la
    instancia validada.

    Recibe:
        query: consulta en lenguaje natural del usuario, ya validada y
            recortada por el caller (api/trips.py).
        settings: config de la app (anthropic_api_key, anthropic_model).

    Devuelve:
        Una instancia de TripPlan validada a partir de la salida
        estructurada del modelo.

    Consideraciones:
    - Streaming vs. no streaming: `client.messages.create` (bloqueante)
      vs. `client.messages.stream`, y como interactua con devolver un
      unico TripPlan validado (probablemente hay que bufferear el stream
      completo antes de validar) frente a cualquier requisito futuro de
      streaming hacia el cliente en POST /trips/plan.
    - Donde vive el system prompt: string inline aqui, un modulo
      prompts.py separado, o un recurso versionado -- y si necesita
      inyectar contexto del usuario/claims.
    - Como se fuerza el schema estructurado: tool-use de Anthropic con un
      JSON schema derivado de TripPlan (`TripPlan.model_json_schema()`) y
      `tool_choice` forzado, vs. prompting + parseo del texto con
      `TripPlan.model_validate_json`, y que hacer si la salida del modelo
      no valida.
    - Manejo de ventana de contexto / presupuesto de tokens: `max_tokens`
      de la request, que pasa si `query` ya es grande por si sola, y si
      hay turnos previos en alcance para este endpoint (el skeleton
      actual es de un solo turno).
    - El modelo a usar ya esta resuelto por config.py (settings.anthropic_model);
      no es una decision de esta funcion.

    # TODO(usuario): implementar la llamada real a
    # anthropic.AsyncAnthropic.
    """
    raise NotImplementedError("lo escribe el usuario")


async def call_with_retries(query: str, *, settings: Settings) -> TripPlan:
    """Envuelve call_anthropic_model (Pieza A) con una politica de
    reintentos para fallos transitorios. Esta es la funcion que
    api/trips.py invoca directamente.

    Recibe: igual que call_anthropic_model.
    Devuelve: igual que call_anthropic_model, una vez que una llamada
        tiene exito (o lanza, una vez agotado el presupuesto de
        reintentos -- ver Consideraciones).

    Consideraciones:
    - Que errores son transitorios (vale la pena reintentar) vs. no:
      p. ej. anthropic.APIConnectionError / anthropic.APITimeoutError /
      anthropic.RateLimitError / anthropic.InternalServerError (5xx) son
      candidatos a transitorios; anthropic.AuthenticationError,
      anthropic.PermissionDeniedError, anthropic.BadRequestError (4xx
      salvo 429), y un fallo de validacion de TripPlan (Pieza B) son
      candidatos a no-transitorios -- pero esta lista la decide y
      documenta esta funcion, no se asume.
    - Estrategia de backoff: delay fijo, exponencial, exponencial+jitter;
      con que libreria (tenacity no es una dependencia actual) o a mano.
    - Presupuesto maximo de reintentos: numero de intentos y/o un plazo
      de reloj para toda la llamada, y como interactua con cualquier
      timeout HTTP aguas arriba en POST /trips/plan.
    - Que hacer al agotar el presupuesto: relanzar la ultima excepcion,
      envolverla en un tipo dedicado, o degradar -- pero en cualquier
      caso debe propagarse un error, nunca devolver un TripPlan vacio ni
      None. Hoy, api/trips.py deja que lo que sea que esto lance se
      propague como 500, pendiente de esta decision.
    - Si un TripPlan que falla la validacion de Pieza B cuenta como caso
      reintentable (re-prompt al modelo) o como fallo inmediato.

    # TODO(usuario): implementar reintentos/backoff alrededor de
    # call_anthropic_model.
    """
    raise NotImplementedError("lo escribe el usuario")
