"""Tests for tools/check_portability.py.

Loaded via importlib from its file path rather than a package import,
since `tools` has no src-layout package to import from.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "check_portability.py"
_spec = importlib.util.spec_from_file_location("check_portability", MODULE_PATH)
check_portability = importlib.util.module_from_spec(_spec)
sys.modules["check_portability"] = check_portability
_spec.loader.exec_module(check_portability)

FORBIDDEN = ("boto3", "botocore", "@aws-sdk/*", "azure-*")


def test_forbidden_import_in_apps_fails(tmp_path):
    file = tmp_path / "apps" / "orchestrator" / "s3_client.py"
    file.parent.mkdir(parents=True)
    file.write_text("import boto3\n")

    violations, warning = check_portability.check_python_file(file, FORBIDDEN)

    assert warning is None
    assert len(violations) == 1
    assert violations[0].imported == "boto3"
    assert violations[0].line == 1
    assert violations[0].pattern == "boto3"


def test_same_import_in_infra_adapters_is_exempt(monkeypatch, tmp_path):
    monkeypatch.setattr(check_portability, "REPO_ROOT", tmp_path)
    file = tmp_path / "infra" / "adapters" / "aws_storage.py"
    file.parent.mkdir(parents=True)
    file.write_text("import boto3\n")
    config = check_portability.Config(forbidden=FORBIDDEN, exceptions=("infra/adapters/",))

    violations, warning = check_portability.check_file(file, config)

    assert violations == []
    assert warning is None


def test_forbidden_name_in_docstring_passes(tmp_path):
    file = tmp_path / "notes.py"
    file.write_text('"""This module discusses boto3 but never imports it."""\n')

    violations, warning = check_portability.check_python_file(file, FORBIDDEN)

    assert violations == []
    assert warning is None


def test_forbidden_name_in_string_literal_passes(tmp_path):
    file = tmp_path / "notes.py"
    file.write_text('MESSAGE = "please migrate away from boto3"\n')

    violations, warning = check_portability.check_python_file(file, FORBIDDEN)

    assert violations == []
    assert warning is None


def test_aliased_import_is_detected(tmp_path):
    file = tmp_path / "client.py"
    file.write_text("import boto3 as aws_sdk\n")

    violations, warning = check_portability.check_python_file(file, FORBIDDEN)

    assert warning is None
    assert len(violations) == 1
    assert violations[0].imported == "boto3"


def test_from_import_is_detected(tmp_path):
    file = tmp_path / "client.py"
    file.write_text("from botocore.exceptions import ClientError\n")

    violations, warning = check_portability.check_python_file(file, FORBIDDEN)

    assert warning is None
    assert len(violations) == 1
    assert violations[0].imported == "botocore.exceptions"
    assert violations[0].pattern == "botocore"


def test_allowed_import_passes(tmp_path):
    file = tmp_path / "client.py"
    file.write_text("import fastapi\nfrom pathlib import Path\n")

    violations, warning = check_portability.check_python_file(file, FORBIDDEN)

    assert violations == []
    assert warning is None


def test_js_import_and_require_are_detected(tmp_path):
    file = tmp_path / "client.ts"
    file.write_text(
        "import { S3Client } from '@aws-sdk/client-s3';\n"
        "const azureBlob = require('azure-storage');\n"
    )

    violations = check_portability.check_js_file(file, FORBIDDEN)

    assert [v.imported for v in violations] == ["@aws-sdk/client-s3", "azure-storage"]


def test_matches_forbidden_wildcard_and_submodule():
    assert check_portability.matches_forbidden("boto3.session", FORBIDDEN) == "boto3"
    assert check_portability.matches_forbidden("@aws-sdk/client-s3", FORBIDDEN) == "@aws-sdk/*"
    assert check_portability.matches_forbidden("fastapi", FORBIDDEN) is None


def test_unparseable_python_file_with_forbidden_import_is_caught_by_fallback(tmp_path):
    file = tmp_path / "client.py"
    file.write_text("import boto3\ndef broken(\n")  # unclosed paren: SyntaxError

    violations, warning = check_portability.check_python_file(file, FORBIDDEN)

    assert warning is not None
    assert "could not parse as Python" in str(warning)
    assert len(violations) == 1
    assert violations[0].imported == "boto3"
    assert violations[0].line == 1


def test_unparseable_python_file_without_forbidden_import_only_warns(tmp_path):
    file = tmp_path / "client.py"
    file.write_text("import fastapi\ndef broken(\n")  # unclosed paren: SyntaxError

    violations, warning = check_portability.check_python_file(file, FORBIDDEN)

    assert violations == []
    assert warning is not None
    assert "could not parse as Python" in str(warning)


def test_unparseable_file_with_file_args_is_not_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(check_portability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_portability,
        "CONFIG_PATH",
        Path(__file__).resolve().parent.parent / "portability.toml",
    )
    file = tmp_path / "broken.py"
    file.write_text("def broken(\n")

    exit_code = check_portability.main([str(file)])

    assert exit_code == 0


def test_unparseable_file_with_no_args_is_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(check_portability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_portability,
        "CONFIG_PATH",
        Path(__file__).resolve().parent.parent / "portability.toml",
    )
    file = tmp_path / "broken.py"
    file.write_text("def broken(\n")

    exit_code = check_portability.main([])

    assert exit_code == 1


def test_json_output_blocks_on_violation(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_portability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_portability,
        "CONFIG_PATH",
        Path(__file__).resolve().parent.parent / "portability.toml",
    )
    file = tmp_path / "client.py"
    file.write_text("import boto3\n")

    exit_code = check_portability.main(["--json", str(file)])
    out = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert out["decision"] == "block"
    assert "boto3" in out["reason"]


def test_json_output_is_informational_only_for_parse_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_portability, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_portability,
        "CONFIG_PATH",
        Path(__file__).resolve().parent.parent / "portability.toml",
    )
    file = tmp_path / "broken.py"
    file.write_text("import fastapi\ndef broken(\n")

    exit_code = check_portability.main(["--json", str(file)])
    out = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "decision" not in out
    assert "could not parse as Python" in out["hookSpecificOutput"]["additionalContext"]
