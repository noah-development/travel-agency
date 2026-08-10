# 0003 - Local infrastructure

## Status

Accepted

## Context

El módulo 2 necesita pgvector y el trabajo de identidad necesita Keycloak
hablando con Postgres, así que hace falta infraestructura local levantable
con un solo comando, reproducible en Windows nativo (sin WSL) y sin
consumir recursos por servicios que todavía no se usan (RabbitMQ, SQL
Server, que llegan en un módulo posterior). Docker solo levanta
infraestructura, nunca código de la aplicación: `infra/keycloak/realms/`
es la única excepción, un mount de solo lectura de configuración, no de
código fuente.

## Decision

**Una sola instancia de Postgres con dos bases en local, separadas por
servicio en producción**: `infra/compose/postgres-init/01-init-databases.sh`
crea `keycloak` y `travel`, cada una con su propio usuario y contraseña.
En local, una sola instancia es menos piezas que mantener arrancadas y
menos RAM/CPU reservada para un entorno de un solo desarrollador. En
producción cada servicio tendrá su propia instancia (o su propio motor
gestionado) separada, porque ahí sí importan el aislamiento de
blast-radius (un incidente en la base de Keycloak no debe poder tocar la
de `travel`), las políticas de backup independientes, y la posibilidad de
escalar cada una por separado. La separación por usuario/base ya en local
hace que ese salto a producción sea de configuración, no de esquema: el
código de la aplicación nunca asume que ambas bases comparten instancia.

**Perfiles de Compose para diferir RabbitMQ y SQL Server**: ambos
servicios están declarados y versionados en
`infra/compose/docker-compose.yml` con `profiles: ["messaging"]` y
`profiles: ["mssql"]` respectivamente, pero no se levantan con `up` por
defecto. La definición existe desde ya (así no hay que recordarla ni
reinventarla cuando llegue el módulo que los necesita), pero no consumen
CPU/RAM/puertos hasta que se pidan explícitamente con
`tools/dev.py up --profile messaging|mssql|full`.

**Puertos solo en loopback**: todos los puertos publicados usan
`127.0.0.1:<puerto>:<puerto>` (nunca `<puerto>:<puerto>` a secas). Publicar
sin loopback expone el servicio a toda la red local, no solo a la propia
máquina, y en Windows además dispara el prompt del firewall en cada
arranque. El puerto de management de Keycloak (9000, donde vive el
healthcheck) directamente no se publica: solo se necesita dentro de la red
de Compose.

**Tags fijados en vez de `latest`**: cada imagen (`pgvector/pgvector`,
`quay.io/keycloak/keycloak`, `rabbitmq`, `mcr.microsoft.com/mssql/server`)
usa un tag específico, nunca `latest` ni un tag flotante por mayor. Esto es
reproducibilidad: un `docker compose pull` en una máquina distinta, o
meses después, trae exactamente la misma versión, no lo que sea que se
haya publicado como "latest" ese día. Es la misma razón por la que
`tools/install_gitleaks.py` pinea una versión exacta en vez de descargar
la última (ver
[0002-portability-enforcement.md](0002-portability-enforcement.md)).

## Consequences

- Cambiar credenciales de Postgres en `.env` después del primer arranque
  no tiene efecto sobre la base ya inicializada:
  `docker-entrypoint-initdb.d` solo corre una vez, con el volumen vacío.
  La única forma de aplicar credenciales nuevas es `tools/dev.py reset`,
  que borra el volumen y reinicializa. Esto está documentado en
  `.env.example`, en el `--help` de `reset`, y en el README.
- Migrar `keycloak`/`travel` a instancias separadas en producción es un
  cambio de configuración de conexión (host, credenciales), no de
  esquema ni de código de aplicación.
- Levantar `messaging` o `mssql` es una decisión explícita
  (`--profile`); nadie paga el costo de RAM de SQL Server por accidente
  al correr `tools/dev.py up` sin argumentos.
- Los tags fijados significan que actualizar una imagen es un cambio de
  una línea en `docker-compose.yml`, explícito y revisable en el PR, en
  vez de un cambio silencioso la próxima vez que alguien haga `pull`.
