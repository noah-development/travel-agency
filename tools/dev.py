"""Wraps `docker compose` for the project's local infra so the long
invocation (compose file path, --env-file) never has to be memorized by
hand. See docs/decisions/0003-local-infrastructure.md.

Usage:
    uv run python tools/dev.py up [--profile {messaging,mssql,full}]
    uv run python tools/dev.py down
    uv run python tools/dev.py reset
    uv run python tools/dev.py logs [service]
    uv run python tools/dev.py status
    uv run python tools/dev.py keycloak-export

Before running any subcommand, this validates the root .env file:
- If it doesn't exist, it's created from .env.example and the command
  exits so real values can be filled in.
- If it exists but still has "CHANGE_ME" placeholders, the command
  aborts and lists which variables need filling in.

This validation matters because docker-entrypoint-initdb.d (Postgres's
init mechanism) only runs once, when the data volume is empty. If
Postgres starts even once with placeholder passwords, the volume is
permanently initialized with them -- editing .env afterward has no
effect on the already-running database, and the resulting failure (an
authentication error) gives no hint that stale placeholder credentials
are the actual cause. The only fix at that point is `reset`, which
deletes the volume and reinitializes from the current .env.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = REPO_ROOT / "infra" / "compose" / "docker-compose.yml"
ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE_FILE = REPO_ROOT / ".env.example"

# Scratch output for `keycloak-export`, gitignored. Never the same path as
# infra/keycloak/realms/, which holds the hand-authored, canonical realm
# files -- see cmd_keycloak_export() for why the two must stay separate.
KEYCLOAK_EXPORT_DIR = REPO_ROOT / "infra" / "keycloak" / "exports"
KEYCLOAK_REALM_NAMES = ["travel-customers", "travel-admin"]

_PROFILE_FLAGS: dict[str, list[str]] = {
    "messaging": ["messaging"],
    "mssql": ["mssql"],
    "full": ["messaging", "mssql"],
}


def base_argv() -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE_FILE), "--env-file", str(ENV_FILE)]


def build_compose_argv(
    subcommand: str, profile: str | None = None, extra: list[str] | None = None
) -> list[str]:
    """Pure argv builder, kept separate from execution so it's unit-testable
    without a Docker daemon."""
    argv = base_argv()
    for name in _PROFILE_FLAGS.get(profile, []):
        argv += ["--profile", name]
    argv.append(subcommand)
    if extra:
        argv += extra
    return argv


def find_unfilled_vars(env_file: Path) -> list[str]:
    unfilled = []
    for line in env_file.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if "CHANGE_ME" in value:
            unfilled.append(key.strip())
    return unfilled


def ensure_env_ready() -> bool:
    if not ENV_FILE.exists():
        shutil.copyfile(ENV_EXAMPLE_FILE, ENV_FILE)
        print(f"No .env found -- created one from {ENV_EXAMPLE_FILE.name}.")
        print("Fill in the real values in .env, then run this command again.")
        return False

    unfilled = find_unfilled_vars(ENV_FILE)
    if unfilled:
        print(".env still has placeholder values. Fill these in before continuing:")
        for name in unfilled:
            print(f"  - {name}")
        print(
            "\nIf postgres has already started once (data volume already "
            'initialized), filling these in is not enough: run "reset" '
            "afterward to apply the new credentials -- it deletes local data."
        )
        return False

    return True


def build_export_argv(realm: str) -> list[str]:
    """Pure argv builder for the one-off `docker compose run` that exports
    one live realm, kept separate from execution so it's unit-testable
    without a Docker daemon (same reasoning as build_compose_argv).

    One realm per invocation, not one `--realm` flag per realm: `kc.sh
    export` only honors the last `--realm` flag given, silently dropping
    the rest, so a single call with multiple `--realm` flags exports only
    the last realm instead of failing loudly about it.
    """
    argv = base_argv()
    argv += ["run", "--rm", "-v", f"{KEYCLOAK_EXPORT_DIR}:/tmp/kc-export", "keycloak"]
    argv += ["export", "--dir", "/tmp/kc-export", "--users", "realm_file", "--realm", realm]
    return argv


def run(argv: list[str]) -> int:
    print(" ".join(argv), flush=True)
    return subprocess.run(argv, cwd=REPO_ROOT).returncode


def cmd_reset() -> int:
    print("This deletes ALL local data (Postgres, RabbitMQ, MSSQL volumes).")
    print(
        "Postgres credentials in .env only take effect when the data volume "
        "is (re)created -- this is the only way to apply new ones."
    )
    answer = input('Type "DELETE DATA" to confirm, anything else aborts: ')
    if answer != "DELETE DATA":
        print("Aborted, no changes made.")
        return 1

    down_code = run(build_compose_argv("down", extra=["-v"]))
    if down_code != 0:
        return down_code
    return run(build_compose_argv("up", extra=["-d"]))


def cmd_keycloak_export() -> int:
    """Export the live realms to KEYCLOAK_EXPORT_DIR -- a scratch,
    gitignored directory, never infra/keycloak/realms/ itself.

    The hand-authored files in infra/keycloak/realms/ are the canonical
    source and this never overwrites them: a live Keycloak export carries
    generated IDs, keys, and explicit-default fields the hand-written JSON
    doesn't, so it's structurally a much larger, different document, not
    something diffable against the canonical file. Comparing the export and
    hand-porting anything worth keeping into the canonical file is a manual
    step for whoever runs this.
    """
    KEYCLOAK_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        "Exporting to infra/keycloak/exports/ (gitignored scratch dir), not to "
        "infra/keycloak/realms/. Compare by hand and port over only what you want "
        "to keep -- a live export is not a diffable copy of the hand-authored file.\n"
        "If a real user/password was ever added via the admin console, this export "
        "can contain a real credential hash: never commit it as-is."
    )
    for realm in KEYCLOAK_REALM_NAMES:
        code = run(build_export_argv(realm))
        if code != 0:
            return code
    print(f"Exported to {KEYCLOAK_EXPORT_DIR}")
    return 0


def cmd_status() -> int:
    argv = build_compose_argv("ps", extra=["--format", "json"])
    print(" ".join(argv))
    result = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        name = entry.get("Service", entry.get("Name", "?"))
        state = entry.get("State", "?")
        health = entry.get("Health") or "no healthcheck"
        print(f"{name}: {state} ({health})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wrap docker compose for local infra.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    up_parser = subparsers.add_parser("up", help="Bring up local infra (default profile).")
    up_parser.add_argument(
        "--profile",
        choices=["messaging", "mssql", "full"],
        default=None,
        help="Also bring up the services behind this profile.",
    )

    subparsers.add_parser("down", help="Bring down local infra without deleting volumes.")

    subparsers.add_parser(
        "reset",
        help=(
            "Bring down local infra WITH volumes (deletes all local data) and "
            "bring it back up. This is the only way to apply Postgres "
            "credentials changed in .env after the data volume was already "
            "initialized -- docker-entrypoint-initdb.d only runs once, on an "
            "empty volume, so editing .env alone has no effect on a database "
            "that already exists."
        ),
    )

    logs_parser = subparsers.add_parser("logs", help="Follow logs for one service, or all.")
    logs_parser.add_argument("service", nargs="?", default=None)

    subparsers.add_parser("status", help="Report status and health for each service.")

    subparsers.add_parser(
        "keycloak-export",
        help=(
            "Export the live realms to infra/keycloak/exports/ (gitignored) for "
            "manual comparison -- never overwrites infra/keycloak/realms/."
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not ensure_env_ready():
        return 1

    if args.command == "up":
        return run(build_compose_argv("up", profile=args.profile, extra=["-d"]))
    if args.command == "down":
        return run(build_compose_argv("down"))
    if args.command == "reset":
        return cmd_reset()
    if args.command == "logs":
        extra = ["-f", *([args.service] if args.service else [])]
        return run(build_compose_argv("logs", extra=extra))
    if args.command == "status":
        return cmd_status()
    if args.command == "keycloak-export":
        return cmd_keycloak_export()

    return 1


if __name__ == "__main__":
    sys.exit(main())
