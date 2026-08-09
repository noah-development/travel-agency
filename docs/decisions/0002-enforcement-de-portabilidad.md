# 0002 - Cloud portability enforcement

## Status

Accepted

## Context

CLAUDE.md sets a hard rule: no cloud-provider-specific SDK (`boto3`,
`azure-*`, `@google-cloud/*`, etc.) may be imported outside
`infra/adapters/`. The point is that switching cloud providers touches a
single folder, which is what gets validated in module 6 by running the
same adapter against two clouds. A rule that only lives as text in a
document doesn't hold: someone forgets it, someone ignores it under time
pressure, or an import slips into a large PR that nobody catches in
manual review.

`tools/check_portability.py` implements the rule as code: AST-based
checking for Python, line-scanning for TypeScript/JavaScript, against the
versioned allowlist in `tools/portability.toml`.

## Decision

**Three enforcement layers** are applied instead of a single one:

1. **Claude Code hook** (`.claude/settings.json`, `PostToolUse` on
   `Edit|Write`) — runs the check against the file that was just touched,
   immediately after each edit the assistant makes.
2. **Pre-commit** (`.pre-commit-config.yaml`) — runs the check on staged
   files before every local commit, regardless of who or what produced
   the change.
3. **CI** (`.github/workflows/ci.yml`, `portability` job) — runs the
   check against the whole repository on every push and pull request to
   `main`.

All three layers share the same source of truth
(`tools/check_portability.py` + `tools/portability.toml`), so there is no
duplicated logic to drift out of sync — each layer just invokes the same
script at a different point in the workflow.

### Why three layers instead of one

- **The Claude Code hook** is the fastest layer: it gives feedback in the
  same turn a forbidden import was written, before the code even reaches
  a commit. But it only covers changes made by the assistant inside a
  Claude Code session — it doesn't cover hand-written commits, changes
  from other tools, or an assistant session without the hook configured.
- **Pre-commit** covers any local commit regardless of origin (editor,
  another assistant, terminal), but it depends on every developer having
  run `pre-commit install` in their clone, and it can be bypassed with
  `git commit --no-verify`.
- **CI** is the only layer that cannot be skipped or uninstalled: it runs
  on the server against the actual state of the PR, independent of each
  machine's local setup. It's the final safety net, but it arrives late —
  feedback shows up minutes after the push, not at the moment the code
  was written.

Each layer covers the previous one's blind spot. Relying on a single
layer means relying on its specific blind spot: CI alone is slow but
inescapable; pre-commit alone is fast but skippable and incomplete; the
Claude Code hook alone is immediate but doesn't cover changes outside
that session. All three together mean evading the rule takes deliberate
effort at every layer, not a lapse in just one.

## Required checks on GitHub

In `main`'s branch protection settings (Settings → Branches → Branch
protection rules → `main` → *Require status checks to pass before
merging*), the four jobs of the `CI` workflow defined in
`.github/workflows/ci.yml` must be marked as **required**:

- `lint`
- `portability`
- `secrets`
- `tests`

All four are fast (minutes, no image builds or deploys) and run on every
push/PR to `main`, so there's no cost to blocking the merge until they
pass. `portability` is the one that directly enforces this decision; the
other three (`lint`, `secrets`, `tests`) are included because requiring
one check but not the others leaves gaps equivalent to the problem this
document is trying to solve.

## Consequences

- A forbidden import has to survive three independent checks to reach
  `main`: the hook, pre-commit, and CI. In practice this shouldn't happen
  unless someone uninstalls pre-commit, isn't using Claude Code, and also
  has permission to bypass branch protection.
- All three layers read the same configuration
  (`tools/portability.toml`), so extending the forbidden-package list is
  a single change that propagates to all three automatically.
- If the check becomes slow in the future (e.g. scanning a much larger
  repo), the layer most affected is CI, which scans the whole repo on
  every PR; the hook and pre-commit only touch individual or staged files
  and shouldn't feel that cost.
