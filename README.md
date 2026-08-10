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
```

Each subcommand prints the actual `docker compose` command before running
it. Run `/infra` for a compact status check.

First run copies `.env.example` to `.env` and stops so you can fill in
real values. **Postgres credentials in `.env` only take effect the first
time the data volume is created** (`docker-entrypoint-initdb.d` only runs
on an empty volume) — changing them afterward requires `tools/dev.py
reset`, which deletes local data, to apply.

## Checks

Copy `.env.example` to `.env` and fill in the values before running anything.

Python:
```
uv sync
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
