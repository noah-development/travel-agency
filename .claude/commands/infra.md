---
description: Run tools/dev.py status and report compactly which local infra services are up and healthy
---

Run `uv run python tools/dev.py status` from the repo root.

Note: this requires a `.env` file with real values and Docker running. If
`tools/dev.py` reports a missing/unfilled `.env`, relay that message as-is
rather than treating it as an unrelated failure.

Report a compact summary, one line per service (postgres, keycloak, and
rabbitmq/mssql only if they're currently up):

```
postgres:  up (healthy) | up (starting) | up (unhealthy) | down
keycloak:  up (healthy) | up (starting) | up (unhealthy) | down
```

No raw command output, no narration -- just the summary.
