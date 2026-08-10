Crea un custom command en .claude/commands/reporte.md, invocable como /reporte.

Su trabajo: generar un digest compacto del estado del repositorio, pensado para pegarse en una conversación con otro modelo que NO tiene acceso al repo. Optimiza para señal por token, no para completitud.

Debe emitir, en este orden:

1. `git log --oneline -15` y el estado de sincronía con origin (ahead/behind).
2. Árbol de archivos hasta 2 niveles, EXCLUYENDO node_modules, .venv, .git, bin, obj, .next. Solo rutas, sin tamaños.
3. Resultado de la última corrida de CI: nombre de cada job y su conclusión. Usa `gh run list --limit 1` y `gh run view`.
4. Lista de los hooks activos: los de pre-commit (leídos de .pre-commit-config.yaml) y los de Claude Code (leídos de .claude/settings.json), con una línea por hook indicando sobre qué dispara.
5. Conteo de líneas de CLAUDE.md, y los nombres de los archivos en .claude/commands/ y .claude/agents/.
6. Salida de /verificar.
7. Una sección "DESVIACIONES" donde listes, en prosa breve, cualquier punto donde el estado actual del repo difiera de lo que los ADRs en docs/decisiones/ declaran. Si no hay ninguna, dilo en una línea.

Límite duro: 120 líneas de salida total. Si algo se desborda, trunca y márcalo con [truncado]. Sin arte ASCII, sin banners, sin emojis.