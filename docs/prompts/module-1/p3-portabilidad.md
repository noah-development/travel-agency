Implementa la regla de portabilidad de nube del proyecto y sus tres puntos de enforcement.

La regla: ningún SDK específico de proveedor de nube puede importarse fuera de infra/adapters/. El propósito es que cambiar de AWS a Azure toque una sola carpeta. La regla se prueba en el módulo 6 corriendo el mismo adaptador contra dos nubes.

1. tools/check_portability.py — Python puro, sin dependencias fuera de la stdlib salvo las ya declaradas en el workspace. Debe:

   - Para archivos .py: usar el módulo `ast` de la stdlib para recorrer los nodos Import e ImportFrom. NO uses expresiones regulares para esto: un regex no distingue un import real de una mención en un docstring, de un string, o de un comentario, y los falsos positivos son lo que hace que la gente desactive el check. El AST te da la estructura real del archivo.
   - Para archivos .ts/.tsx/.js/.mjs: escaneo por líneas de sentencias import y llamadas require(). Documenta explícitamente en el docstring que este escaneo es más débil que el AST de Python y por qué se aceptó el trade-off (no queremos un parser de TS como dependencia del tooling).
   - Mantener la lista de paquetes prohibidos en un archivo de configuración aparte y versionado (tools/portability.toml), no hardcodeada. Semilla inicial: boto3, botocore, aws-cdk-lib, @aws-sdk/*, azure-*, @azure/*, google-cloud-*, @google-cloud/*. La lista se ampliará; que agregar una entrada no requiera tocar código.
   - Exceptuar infra/adapters/ y las rutas de test que ejerciten adaptadores. Las excepciones también van en el TOML, no en el código.
   - Salir con código 0 si todo bien, 1 si hay violaciones, imprimiendo archivo:línea y el import ofensor. Un mensaje por violación, sin banners ni arte ASCII.
   - Aceptar una lista de archivos como argumentos; si no recibe ninguno, escanear todo el repo. Esto permite que el pre-commit le pase solo lo staged y que CI lo corra completo.

2. tools/tests/test_check_portability.py con casos que cubran: import prohibido en apps/ (falla), el mismo import en infra/adapters/ (pasa), mención del nombre prohibido dentro de un docstring o de un string literal en Python (pasa — es el caso que justifica usar AST), import con alias, y from ... import.

3. Pre-commit de Git usando el framework `pre-commit` (instalable con uv, corre nativo en Windows). .pre-commit-config.yaml con: el check de portabilidad sobre archivos staged, ruff check, ruff format, detect-private-key, y check-added-large-files. Documenta en el README la línea exacta para instalar los hooks.

4. Hook de Claude Code en .claude/settings.json: un PostToolUse sobre Edit y Write que ejecute el check sobre el archivo tocado. Debe ser un hook y no una skill ni una instrucción del CLAUDE.md, porque tiene que ocurrir siempre, sin depender de que el modelo lo recuerde. Invócalo por su ruta de Python (uv run python tools/check_portability.py), nunca por un script de shell.

5. .github/workflows/ci.yml — ETAPA A únicamente. Corre en ubuntu-latest sobre push y pull_request a main. Jobs:
   - lint: setup de Python con uv, ruff check y ruff format --check.
   - portability: corre tools/check_portability.py sobre todo el repo.
   - secrets: gitleaks sobre el historial completo del PR.
   - tests: pytest sobre tools/ (por ahora es lo único con tests).
   Configura concurrency para cancelar corridas anteriores del mismo branch. NO agregues jobs de build de imágenes, ni de deploy, ni de Node todavía: eso es la etapa B, en la semana 3.

6. Protege main: documenta en docs/decisiones/0002-enforcement-de-portabilidad.md qué checks deben marcarse como required en la configuración del repositorio de GitHub, y por qué se eligieron tres capas de enforcement (Claude Code, pre-commit, CI) en vez de una sola.

Verifica al terminar que el check corre en Windows sin ajustes de ruta y que los tests pasan.