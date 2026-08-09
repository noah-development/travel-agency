# .claude

- `settings.json` — versioned team config: permissions that let routine repo
  ops run without confirmation, plus the docker/destructive-git `ask` list.
  Add here when a *safe, routine* command keeps prompting for the team.
- `settings.local.json` (gitignored) — personal overrides, never team rules.
- `commands/` — custom slash commands. Add one when a multi-step check is
  run often enough, by hand, to be worth a `/name`.
- `agents/` — subagents with a narrow, repeatable job. Add one when a task
  needs isolated context or a strict output format, not for general help.

No skills yet — added only once a repeated pattern shows up, not ahead of
time.
