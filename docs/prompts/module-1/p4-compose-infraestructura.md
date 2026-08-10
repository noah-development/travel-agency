Configura la infraestructura local del proyecto con Docker Compose. Contexto: Windows 11 nativo, Docker Desktop con backend WSL2. Docker levanta SOLO infraestructura — nunca código de la aplicación. Volúmenes nombrados, cero bind mounts de código.

1. infra/compose/docker-compose.yml. Sin la clave `version:` (obsoleta). Servicios:

   postgres (siempre activo):
   - Imagen pgvector/pgvector con Postgres 17, tag exacto y fijado. NO uses la imagen oficial de postgres: necesitamos la extensión pgvector desde el módulo 2 y no vamos a compilarla a mano.
   - Volumen nombrado para los datos.
   - Puerto publicado SOLO en loopback: "127.0.0.1:5432:5432". Nunca "5432:5432" — eso lo expone a la red local y en Windows además dispara el prompt del firewall.
   - Healthcheck con pg_isready.
   - Script de init en infra/compose/postgres-init/ que cree DOS bases: `keycloak` y `travel`, cada una con su propio usuario y contraseña tomados de variables de entorno. En `travel`, crear la extensión vector.

   keycloak (siempre activo):
   - Imagen oficial de Keycloak, tag exacto y fijado, versión 26.x.
   - Comando `start-dev` con `--import-realm`.
   - Backend de base de datos apuntando a la base `keycloak` del contenedor de postgres.
   - depends_on postgres con condition: service_healthy. Sin esto Keycloak arranca antes que Postgres, falla la migración y se reinicia en bucle.
   - Puerto "127.0.0.1:8080:8080".
   - Healthcheck contra el endpoint de health de Keycloak.
   - Monta infra/keycloak/realms/ como read-only. ACLARACIÓN: la regla de "sin bind mounts" aplica a código de la aplicación, no a archivos de configuración; montar los realms en modo lectura es correcto y necesario.

   rabbitmq (perfil "messaging", APAGADO por default):
   - Imagen con management plugin, tag fijado. Puertos en loopback.

   mssql (perfil "mssql", APAGADO por default):
   - SQL Server 2022, tag fijado, con límite de memoria de 2g en deploy.resources. Sin el límite se come varios GB en reposo.
   - Variable de aceptación de EULA y contraseña desde entorno.

   Los dos últimos NO se levantan hasta el módulo 4. Van declarados para que la definición exista y esté versionada, pero no consumen recursos hoy.

2. Todas las credenciales vienen del .env de la raíz. Actualiza .env.example con las variables nuevas y placeholders evidentes. Ningún valor real en ningún archivo versionado.

3. tools/dev.py — CLI en Python (no Bash) con argparse o typer, que envuelva los comandos de Compose pasando la ruta del archivo y el --env-file correctos, para que nunca tengas que recordar la invocación larga. Subcomandos:
   - up      : levanta el perfil default
   - up --profile messaging|mssql|full
   - down    : baja sin borrar volúmenes
   - reset   : baja CON volúmenes (borra datos) y vuelve a levantar. Debe pedir confirmación explícita.
   - logs [servicio]
   - status  : estado y healthcheck de cada servicio
   Cada subcomando imprime el comando de docker que va a ejecutar antes de correrlo. Esto es deliberado: quiero seguir viendo el comando real, no que la herramienta lo esconda.

4. Un custom command en .claude/commands/infra.md que invoque tools/dev.py status y reporte de forma compacta qué está arriba y qué no.

5. docs/decisiones/0003-infraestructura-local.md documentando: una sola instancia de Postgres con dos bases en local pero separadas en producción y por qué; perfiles de Compose para diferir RabbitMQ y SQL Server; puertos solo en loopback; tags fijados en vez de latest.

6. Actualiza el README con los comandos de tools/dev.py.

Verifica que `python tools/dev.py up` levanta postgres y keycloak sanos en Windows, que `status` los reporta healthy, y que `psql` puede conectarse a la base travel y ejecutar `SELECT * FROM pg_extension WHERE extname='vector'` con resultado.