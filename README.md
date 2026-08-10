# travel-agency

Monorepo for an LLM-based travel agent. Includes a Python/FastAPI
orchestrator, a Next.js web app, and the infrastructure that supports them.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) >= 0.11
- Node.js >= 20
- pnpm (via `corepack enable`)
- Docker Desktop (for local infrastructure)

## Local infrastructure

`docker compose` files live in `infra/compose/`. `tools/dev.py` wraps the
compose invocation (file path, `--env-file`) so it never has to be typed
by hand:

```
python tools/dev.py up                          # postgres + keycloak
python tools/dev.py up --profile messaging       # + rabbitmq
python tools/dev.py up --profile mssql           # + sql server
python tools/dev.py up --profile full            # + both
python tools/dev.py down                         # stop, keep volumes
python tools/dev.py reset                        # stop, DELETE volumes, restart
python tools/dev.py logs [service]
python tools/dev.py status
python tools/dev.py keycloak-export
```

Each subcommand prints the actual `docker compose` command before running
it. Run `/infra` for a compact status check.

First run copies `.env.example` to `.env` and stops so you can fill in
real values. **Postgres credentials in `.env` only take effect the first
time the data volume is created** (`docker-entrypoint-initdb.d` only runs
on an empty volume) — changing them afterward requires `tools/dev.py
reset`, which deletes local data, to apply.

## Identity (Keycloak)

Two separate realms, defined as code in `infra/keycloak/realms/` and
imported automatically on container start (`--import-realm`) — see
[docs/decisions/0004-identity-two-realms.md](docs/decisions/0004-identity-two-realms.md)
for why two realms instead of one with roles.

- **`travel-customers`**: role `customer`; clients `web-public` (Next.js,
  public, authorization code + PKCE) and `orchestrator-api` (FastAPI,
  bearer-only resource server, no login flow). Seed users `customer.one`,
  `customer.two`.
- **`travel-admin`**: roles `admin`, `agent`; clients `back-office`
  (Angular, public, authorization code + PKCE) and `admin-api` (.NET,
  bearer-only resource server). Seed users `admin.one` (`admin`),
  `agent.one` (`agent`).
- **`verifier-cli`**: a third client in both realms, used only by
  `tools/verify_auth.py` for the password grant. It's the only client with
  `directAccessGrantsEnabled` — the real front-end clients only ever do
  authorization code + PKCE, so that flow can't linger unused on a
  publicly-deployed client.

Every seed user's password is `DevPassword123!` — deliberately obvious,
deliberately not hidden anywhere, because it isn't a real secret. The
Keycloak admin console password is the one real secret here and comes only
from `.env` (`KC_BOOTSTRAP_ADMIN_USERNAME`/`KC_BOOTSTRAP_ADMIN_PASSWORD`),
never from the realm JSON.

Verify both realms end-to-end (discovery document, token issuance, signature,
`iss`/`aud`/role claims, and that a `travel-customers` token does **not**
validate against `travel-admin`'s keys):

```
uv run python tools/verify_auth.py
```

The realm JSON files in `infra/keycloak/realms/` are hand-authored and
canonical — `tools/dev.py keycloak-export` never overwrites them. It exports
the live container's realms to the gitignored `infra/keycloak/exports/`
instead, for manual comparison: a live export carries generated IDs, keys,
and explicit-default fields the hand-written JSON doesn't, so it's never
going to be a small diff. Anything worth keeping from a console change gets
ported into the canonical file by hand. Review an export before it goes
anywhere near git — if a real user/password was ever added through the
console, the export can contain a real credential hash.

## Checks

Copy `.env.example` to `.env` and fill in the values before running anything.

Python:
```
uv sync --all-packages
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

TypeScript:
```
pnpm install
```

### Git hooks

Install the pre-commit hooks once after `uv sync`. This project uses two
separate hook types, so both installs are required:

```
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

The second one enables the conventional-commit check on commit messages;
skipping it is the most common way this ends up not actually enforced.

Design decisions live in [docs/decisions](docs/decisions).
