---
description: Run all repo checks (lint, format, tests, cloud-portability) and report a compact pass/fail summary
---

Run the following checks from the repo root, in order. Do not stop at the
first failure — run all of them, then report.

1. `uv run ruff check .`
2. `uv run ruff format --check .`
3. `uv run pytest`
4. `uv run python tools/check_portability.py`

Note: `tools/check_portability.py` may not exist yet. If it's missing,
report that step as "missing" rather than failing the command.

After running all four, report a compact summary, one line per check:

```
ruff check:        PASS | FAIL
ruff format:        PASS | FAIL
pytest:              PASS | FAIL (N failed / N passed)
portability check:  PASS | FAIL | MISSING
```

For any FAIL, add one short line underneath naming the file/test and the
core issue — no full log dumps, no narration of what you're about to do.
