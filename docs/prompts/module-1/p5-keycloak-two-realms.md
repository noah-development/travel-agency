Configura la identidad del sistema en Keycloak. Dos realms separados, definidos como código y versionados. Keycloak ya corre vía Compose con --import-realm apuntando a infra/keycloak/realms/.

CONTEXTO DE DISEÑO — respétalo, no lo simplifiques:
Son DOS realms, no un realm con dos roles. Razón: administradores y clientes son poblaciones distintas con almacenes de usuarios, llaves de firma, políticas de contraseña y flujos de login independientes. Con un solo realm y separación por rol, un bug en la verificación de roles escala un cliente a administrador. Con realms separados ese modo de falla no existe: un token del realm de clientes no valida contra el issuer del realm de administradores. El costo asumido es que no hay SSO entre ambos y un usuario que fuera las dos cosas existiría dos veces. Aquí es aceptable.

1. infra/keycloak/realms/travel-customers.json:
   - Clientes: `web-public` (Next.js — cliente PÚBLICO, authorization code + PKCE obligatorio, sin secreto, redirect URIs de localhost y del dominio de Vercel) y `orchestrator-api` (FastAPI — resource server, sin flujos de login habilitados).
   - Roles de realm: `customer`.
   - 2 usuarios semilla con el rol asignado.

2. infra/keycloak/realms/travel-admin.json:
   - Clientes: `back-office` (Angular — público con PKCE) y `admin-api` (.NET — resource server).
   - Roles de realm: `admin`, `agent`.
   - 2 usuarios semilla.

3. AUDIENCE MAPPERS — crítico, no lo omitas. En cada realm, agrega un client scope dedicado con un protocol mapper de tipo "Audience" que inyecte el client ID del resource server correspondiente en el claim `aud`, y asígnalo como scope por default al cliente de front que lo consume. Sin esto, Keycloak emite tokens sin audiencia útil y cualquier resource server que valide solo firma e issuer aceptará tokens emitidos para otro cliente del mismo realm. Todos nuestros servicios van a validar `aud` estrictamente.

4. SECRETOS EN REPOSITORIO PÚBLICO. El repo es público desde el módulo 1, así que los JSON de realm se van a leer. Por eso:
   - Prefiere clientes públicos con PKCE en vez de confidenciales siempre que el flujo lo permita. Un cliente público no tiene secreto que filtrar.
   - Donde un cliente confidencial sea inevitable, deja un secreto placeholder obviamente falso y documenta que solo sirve en local.
   - Las contraseñas de los usuarios semilla deben ser evidentemente de desarrollo y estar documentadas como tales en un comentario del README, no ocultas.
   - La contraseña del admin de Keycloak viene del .env, jamás del JSON.
   - Deja tiempos de vida de token en los defaults de Keycloak (access token de ~5 min). No los alargues por comodidad: quiero que el flujo de refresh se ejercite desde el principio, no que aparezca como sorpresa en el módulo 5.

5. tools/verify_auth.py — script de verificación en Python que, para CADA realm:
   - Descargue el documento de discovery OIDC y valide que responde.
   - Obtenga un token de un usuario semilla vía password grant (solo para verificación local; el flujo real de la app es authorization code + PKCE).
   - Decodifique el token y afirme: `iss` correcto, `aud` contiene el resource server esperado, los roles esperados están presentes.
   - Afirme además que un token del realm de clientes NO valida contra las llaves públicas del realm de administradores. Esta aserción negativa es el punto: prueba que la separación es real y no decorativa.
   Salida compacta, código de salida 0/1.

6. tools/dev.py keycloak-export — subcomando que exporte los realms del contenedor vivo de vuelta a infra/keycloak/realms/. Necesario porque cualquier cambio hecho en la consola de administración se pierde en el siguiente `reset` si no se exporta. Documenta este round-trip en el README.

7. Agrega UNA línea al CLAUDE.md: los realms se editan como código en infra/keycloak/realms/; si se cambia algo en la consola de Keycloak, hay que exportar antes de commitear. Solo esa línea; el CLAUDE.md no crece con explicaciones.

8. docs/decisiones/0004-identidad-dos-realms.md: dos realms sobre un realm con roles, con el trade-off de SSO explícito; clientes públicos con PKCE sobre confidenciales dado el repo público; validación estricta de audiencia.

Verifica que `python tools/dev.py reset` seguido de `python tools/verify_auth.py` pasa en limpio, incluyendo la aserción negativa entre realms.