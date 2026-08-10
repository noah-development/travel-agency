# 0006 - Naming conventions

## Status

Accepted

## Context

El repositorio es público y funciona como portafolio técnico, incluyendo
de cara a un mercado laboral que incluye trabajo remoto para empresas de
EE. UU. Hasta ahora habían aparecido nombres de archivo en español de
forma orgánica (`docs/prompts/module-1/p3.5-commits-y-remoto.md`,
`docs/decisions/0002-enforcement-de-portabilidad.md`, etc.), mezclados
con nombres en inglés. Esa mezcla no es un problema funcional, pero sí
transmite descuido en un repositorio que alguien externo va a inspeccionar
como muestra de trabajo, y un lector angloparlante no puede navegar la
estructura de archivos por nombre.

## Decision

A partir de ahora, todo lo que sea identificador estructural del
repositorio se nombra en inglés:

- Nombres de archivos y carpetas.
- Nombres de comandos (`.claude/commands/`) y agentes (`.claude/agents/`).
- Identificadores de código: variables, funciones, clases, nombres de
  paquetes.

Se excluye explícitamente de esta regla la **prosa** dentro de:

- Los ADRs en `docs/decisions/` (el contenido, no el nombre de archivo).
- Los prompts en `docs/prompts/` (el contenido, no el nombre de archivo).

Esos documentos registran el proceso de trabajo tal como ocurrió, en el
idioma en que se pensó y se escribió; traducirlos retroactivamente no
aporta valor y arriesga introducir errores de traducción en decisiones ya
tomadas.

## Consequences

- Un ADR o un prompt puede tener nombre de archivo en inglés
  (`0002-portability-enforcement.md`) y contenido en español; eso no es
  una inconsistencia, es la regla funcionando como se espera.
- ADRs futuros que ya estaban planeados con nombre en español en la
  prosa de prompts anteriores (`0003-infraestructura-local.md`,
  `0004-identidad-dos-realms.md`) deben crearse con nombre en inglés
  cuando llegue el momento, aunque el prompt que los menciona no se haya
  editado retroactivamente.
- Cualquier archivo, carpeta, comando o agente nuevo con nombre en
  español es una desviación de esta decisión y debe corregirse antes de
  mergear.
