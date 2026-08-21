from pydantic import BaseModel, ConfigDict


class TripPlan(BaseModel):
    """Structured trip-planning response the LLM must produce for
    POST /trips/plan.

    Recibe: nada directamente -- esto es un schema, no una funcion. Se usa
    tanto para restringir lo que la Pieza A le pide al modelo de Anthropic
    (salida estructurada / tool-use schema) como para validar la respuesta
    del modelo antes de que api/trips.py la devuelva.

    Devuelve: N/A (schema).

    Consideraciones:
    - Campos minimos de un itinerario: destino(s), fecha de inicio/fin,
      lista de dias/actividades -- frente a una estructura mas rica
      (vuelos, presupuesto, desglose por dia). Decidir primero el minimo
      viable.
    - Que campos son opcionales: el modelo no siempre va a poder inferir
      fechas exactas, presupuesto, o numero de viajeros desde una
      consulta en lenguaje natural corta.
    - Como representar una fecha ambigua o parcial (p. ej. "en marzo"):
      texto libre en un campo separado, ISO parcial, o un flag
      `dates_confirmed: bool` junto a fechas concretas.
    - Si conviene mantener un campo de texto libre/explicativo junto a los
      campos estructurados, para la respuesta conversacional al usuario
      ademas del dato estructurado.
    - Unidades y locale para moneda y fechas.

    Nota de implementacion: esta clase se define deliberadamente sin
    campos y con extra="forbid", asi que hoy valida cualquier payload real
    como error (pydantic.ValidationError). No es una version de
    referencia funcional, es un placeholder que aun no hace nada -- una
    clase Pydantic no puede tener un `raise NotImplementedError` literal
    en el cuerpo sin romper el arranque de toda la app (el cuerpo de una
    clase se ejecuta al importarla, no al usarla), asi que esta es la
    desviacion documentada del patron de las otras tres piezas. Ver
    docs/decisions/0005-orchestrator-scaffolding.md.
    """

    model_config = ConfigDict(extra="forbid")

    # TODO(usuario): reemplazar este placeholder vacio con los campos
    # reales de la respuesta estructurada del viaje.
