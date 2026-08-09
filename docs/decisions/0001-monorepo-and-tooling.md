# 0001 - Monorepo and base tooling

## Status

Accepted

## Context

We're starting a new project with at least two application runtimes
(Python/FastAPI for the orchestrator, Next.js for the web app), shared
libraries in both languages, and infrastructure as code. The team develops
on native Windows (no WSL) but deploys and runs CI on Linux.

## Decision

- **Monorepo over polyrepo**: the orchestrator, web app, shared libraries,
  and infrastructure live in a single repository. Changes that cross the
  orchestrator/web/library boundary (e.g. a new API contract) are reviewed
  and merged atomically, without coordinating versions across repos.

- **uv over Poetry** for Python dependencies and environments. uv resolves
  faster, manages the project's Python version directly (no separate
  pyenv-like tool needed), and has native workspace support, which is how
  `apps/orchestrator`, `libs/*`, and `tools` are organized here.

- **pnpm over npm** for TypeScript dependencies. pnpm resolves the workspace
  (`apps/*`, `packages/*`) with hard links and a shared store, avoiding
  duplicated `node_modules` across the web app and shared packages. Nx and
  Turborepo are not added: with only two apps, the cost of configuring and
  maintaining a task orchestrator outweighs the benefit; this will be
  revisited if the number of packages grows.

- **Native development on Windows, no WSL; Linux CI is the source of
  truth.** The team works directly on Windows with Python, Node, and the
  .NET SDK installed on the system. Docker is reserved for infrastructure
  (databases, Keycloak, etc.) using named volumes, never bind mounts of
  source code, so we don't depend on filesystem parity between Windows and
  Linux. All repo tooling is written in Python instead of Bash, so it runs
  the same way on both operating systems.

## Consequences

- A single `git clone` brings in all related code; refactors that cross
  apps and libraries are a single PR.
- The repo requires Python, Node/pnpm, and (where applicable) the .NET SDK
  installed directly on Windows; there is no dev container.
- Since CI runs on Linux, any Windows/Linux behavior divergence (line
  endings, paths, shell scripts) must be caught in CI, not assumed to be
  resolved locally; hence the `.gitattributes` forcing `eol=lf` and the
  ban on Bash scripts in `tools/`.
- If the number of packages or build time grows enough to justify task
  caching or cross-package dependency graphs, the decision not to use
  Nx/Turborepo will be revisited.
