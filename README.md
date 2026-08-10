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

`docker compose` files live in `infra/compose/` and are added as services
are introduced (Postgres, Keycloak, etc.):

```
docker compose -f infra/compose/docker-compose.yml up -d
```

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
