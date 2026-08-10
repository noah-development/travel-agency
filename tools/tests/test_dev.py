"""Tests for tools/dev.py.

Loaded via importlib from its file path rather than a package import,
since `tools` has no src-layout package to import from (same pattern as
tools/tests/test_check_portability.py).

Only the pure argv-building and .env-parsing logic is covered here -- the
actual up/down/reset/status subprocess calls need a live Docker daemon and
are out of scope for unit tests.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "dev.py"
_spec = importlib.util.spec_from_file_location("dev", MODULE_PATH)
dev = importlib.util.module_from_spec(_spec)
sys.modules["dev"] = dev
_spec.loader.exec_module(dev)


def test_build_compose_argv_no_profile_has_no_profile_flags():
    argv = dev.build_compose_argv("up", extra=["-d"])

    assert argv == [
        "docker",
        "compose",
        "-f",
        str(dev.COMPOSE_FILE),
        "--env-file",
        str(dev.ENV_FILE),
        "up",
        "-d",
    ]


def test_build_compose_argv_single_profile():
    argv = dev.build_compose_argv("up", profile="messaging", extra=["-d"])

    assert "--profile" in argv
    assert argv[argv.index("--profile") + 1] == "messaging"
    assert argv.count("--profile") == 1


def test_build_compose_argv_full_profile_expands_to_both():
    argv = dev.build_compose_argv("up", profile="full", extra=["-d"])

    assert argv.count("--profile") == 2
    profiles = [argv[i + 1] for i, tok in enumerate(argv) if tok == "--profile"]
    assert profiles == ["messaging", "mssql"]


def test_build_compose_argv_down_with_volumes():
    argv = dev.build_compose_argv("down", extra=["-v"])

    assert argv[-2:] == ["down", "-v"]


def test_build_compose_argv_logs_with_service():
    argv = dev.build_compose_argv("logs", extra=["-f", "postgres"])

    assert argv[-3:] == ["logs", "-f", "postgres"]


def test_build_compose_argv_logs_without_service():
    argv = dev.build_compose_argv("logs", extra=["-f"])

    assert argv[-2:] == ["logs", "-f"]


def test_find_unfilled_vars_detects_change_me(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=sk-ant-REPLACE_ME\n"
        "POSTGRES_SUPERUSER=CHANGE_ME_superuser\n"
        "POSTGRES_HOST=localhost\n"
    )

    unfilled = dev.find_unfilled_vars(env_file)

    assert unfilled == ["POSTGRES_SUPERUSER"]


def test_find_unfilled_vars_ignores_comments_and_blank_lines(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# POSTGRES_SUPERUSER=CHANGE_ME_superuser\n\nPOSTGRES_HOST=localhost\n")

    assert dev.find_unfilled_vars(env_file) == []


def test_find_unfilled_vars_empty_when_all_filled(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_SUPERUSER=devsuperuser\nPOSTGRES_HOST=localhost\n")

    assert dev.find_unfilled_vars(env_file) == []
