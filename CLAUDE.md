# CLAUDE.md

Monorepo for an LLM-based travel agent: a Python/FastAPI orchestrator and a
Next.js web app, plus the infrastructure that supports them.

## Language

All code, identifiers, and comments are in English, regardless of the
language used in conversation with the user.

## Environment

- Native Windows development, no WSL. Docker is only for local infra
  (Postgres, Keycloak) via named volumes, never bind-mounted source.
- CI runs on Linux and is the source of truth: Windows/Linux divergence
  (line endings, paths) must be caught there, not assumed fixed locally.

## Commands

Python (from repo root):
```
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

TypeScript: `pnpm install`

Local infra: `docker compose -f infra/compose/docker-compose.yml up -d`

## Rules

- **Cloud portability**: no cloud provider SDK is imported outside
  `infra/adapters/`. No exceptions.
- **Secrets**: never write real values into versioned files. Only
  `.env.example` with placeholders.
- **Repo tooling** (scripts under `tools/`) is written in Python, never
  Bash, so it runs identically on Windows and Linux CI.

## Commits and branches

- Conventional commits, validated by the `commit-msg` pre-commit hook.
- Branches: `type/short-description` (e.g. `feat/flight-search`).
