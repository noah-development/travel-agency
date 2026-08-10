# 0004 - Identidad: dos realms separados

## Status

Accepted

## Context

El módulo 1 necesita un modelo de identidad para dos poblaciones de usuarios
completamente distintas: clientes de la agencia (web pública, Next.js) y
personal interno (back office, Angular). El repo es público desde el módulo 1
(ver [0006-naming-conventions.md](0006-naming-conventions.md)), así que
cualquier configuración de identidad que se versiona queda expuesta:
`infra/keycloak/realms/*.json` se lee por cualquiera.

## Decision

**Dos realms (`travel-customers`, `travel-admin`), no un realm con roles.**
Administradores y clientes son poblaciones distintas con almacenes de
usuarios, llaves de firma, políticas de contraseña y flujos de login
independientes. Con un solo realm y separación por rol, un bug en la
verificación de roles escala un cliente a administrador. Con realms
separados ese modo de falla no existe: un token del realm de clientes no
valida contra las llaves públicas del realm de administradores, porque son
llaves distintas -- no es una regla de aplicación que pueda tener un bug, es
una propiedad criptográfica del sistema. El costo asumido es explícito: no
hay SSO entre ambos, y un usuario que fuera las dos cosas (cliente y agente,
por ejemplo) existiría dos veces. Aceptable en este dominio.
`tools/verify_auth.py` prueba esta propiedad con una aserción negativa (el
`kid` de un token de `travel-customers` está ausente del JWKS de
`travel-admin`), no la asume.

**Clientes públicos con PKCE en vez de confidenciales, donde el flujo lo
permite.** `web-public` (Next.js) y `back-office` (Angular) son clientes
públicos: sin secreto, nada que filtrar en un repo público. Los resource
servers (`orchestrator-api`, `admin-api`) son clientes `bearerOnly`: nunca
se autentican a sí mismos ni tienen flujo de login, así que tampoco
necesitan secreto -- esto evita por completo el caso "cliente confidencial
con secreto placeholder" para el módulo 1. Si `bearerOnly` no se comporta
bien contra la versión de Keycloak en uso, el fallback documentado es un
cliente confidencial con todos los flujos deshabilitados y un secreto
placeholder obviamente falso.

**El password grant vive en un tercer cliente dedicado, `verifier-cli`, no
en los clientes reales.** `tools/verify_auth.py` necesita autenticarse como
un usuario semilla sin implementar un flujo de PKCE en un script de CLI, y
la alternativa obvia -- habilitar Direct Access Grants en `web-public`/
`back-office` con una nota de "apagar antes de producción" -- deja
permanentemente habilitado en un repo público un flujo que la aplicación
real nunca usa, con un comentario como única mitigación. Eso es deuda
anotada, no deuda eliminada. Aislar el password grant en `verifier-cli`
(público, sin secreto, `standardFlowEnabled: false`, nunca desplegado)
elimina la deuda en vez de dejarla anotada: `web-public` y `back-office`
solo pueden hacer authorization code + PKCE.

**Validación de audiencia estricta vía audience mappers.** Cada realm tiene
un client scope dedicado (`orchestrator-api-audience`,
`admin-api-audience`) con un protocol mapper de tipo "Audience" que inyecta
el client ID del resource server correspondiente en el claim `aud`,
asignado como scope por default a los clientes de front y a `verifier-cli`.
Sin esto, un token válido por firma e issuer pero emitido para otro cliente
del mismo realm sería aceptado igual por cualquier resource server que solo
valide firma e issuer. Todos los servicios validan `aud` estrictamente
contra su propio client ID.

**Tiempos de vida de token en los defaults de Keycloak** (~5 min de access
token). No se alargan: el flujo de refresh se ejercita desde el principio,
no aparece como sorpresa más adelante.

## Consequences

- No hay SSO entre `travel-customers` y `travel-admin`; alguien que sea
  cliente y agente a la vez tiene dos cuentas separadas, una por realm.
- `web-public` y `back-office` no pueden usarse para obtener tokens vía
  password grant -- ni en desarrollo ni en producción -- porque
  `directAccessGrantsEnabled` está en `false`. Cualquier necesidad futura de
  probar login sin navegador pasa por `verifier-cli`, no por reactivar el
  grant en el cliente real.
- `verifier-cli` es un cliente con más privilegio de login que los clientes
  reales (password grant habilitado) y existe en ambos realms. No se
  despliega en ningún front end; su alcance es exclusivamente
  `tools/verify_auth.py` corriendo en local.
- Cualquier resource server nuevo que se agregue más adelante debe seguir el
  mismo patrón: cliente `bearerOnly` (o confidencial con secreto placeholder
  si `bearerOnly` no aplica) y validación estricta de `aud`, nunca solo de
  `iss`.
- Si `bearerOnly` resulta problemático contra una versión futura de
  Keycloak, el cambio a cliente confidencial con secreto placeholder es
  local a ese cliente, no al diseño de dos realms.
