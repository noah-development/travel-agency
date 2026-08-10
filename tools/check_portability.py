"""Enforce the cloud-portability rule: no cloud-provider SDK may be
imported outside infra/adapters/.

Usage:
    uv run python tools/check_portability.py [--json] [FILE ...]

With no arguments, scans the whole repository (the CI case). With file
arguments, scans only the given files (the pre-commit and PostToolUse-hook
case, where a file is mid-edit).

Exit code semantics differ by invocation mode:

- With file arguments: a file that fails to parse is NOT a failure by
  itself (exit 0 unless a real forbidden-import violation was found). A
  file being edited is very often syntactically invalid for a moment —
  failing the hook on every keystroke would just teach people to ignore
  it. The parse failure is still reported, just not as a blocking exit
  code.
- With no arguments (whole-repo scan): a file that fails to parse IS a
  failure (exit 1), even with zero forbidden imports found. CI only ever
  runs against a complete, committed tree, so invalid Python landing on
  main is a bug in its own right and must never pass silently.

In both modes, forbidden imports found (via AST or the fallback scan
below) always produce exit 1.

Python files (.py) are parsed with the `ast` module and checked for
Import/ImportFrom nodes. This is deliberate: a regex cannot distinguish a
real import from a mention of the same name inside a docstring, a string
literal, or a comment, and those false positives are exactly what makes
teams disable a check like this. The AST gives us the real structure of
the file.

If a Python file fails to parse (SyntaxError), the check does not abort
or silently skip it — a broken file must not become a blind spot. Instead
it falls back to the same weaker line-by-line regex scan used for
TypeScript/JavaScript below (adapted to Python's `import`/`from` syntax),
and reports the parse failure as a warning alongside whatever the
fallback scan finds.

TypeScript/JavaScript files (.ts, .tsx, .js, .mjs) are checked with a
line-by-line regex scan for `import` statements and `require()` calls.
This is weaker than the Python AST check: it can be fooled by a matching
string inside a multi-line comment or a template literal, for instance.
That trade-off is accepted on purpose — pulling in a real TypeScript
parser as a tooling dependency just for this check is not worth it. If
false positives on the JS/TS side become a real problem, revisit this.

--json emits the Claude Code PostToolUse hook JSON format instead of
plain text, for use as the PostToolUse hook command (see
.claude/settings.json). When violations are found, it prints
`{"decision": "block", "reason": "..."}` — for PostToolUse, that surfaces
the reason to Claude as feedback in the same turn (the turn is not
ended), so Claude can fix the import before moving on. When there are
only parse warnings (no violations), it prints
`hookSpecificOutput.additionalContext` instead, which is informational
and does not block. Without --json, the existing plain-text output is
unchanged (used by CI and the pre-commit hook, neither of which is
Claude Code and would not understand hook JSON).
"""

from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "portability.toml"

PY_SUFFIXES = {".py"}
JS_SUFFIXES = {".ts", ".tsx", ".js", ".mjs"}

IGNORED_DIR_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".pytest_cache",
    ".ruff_cache",
    ".turbo",
}

# Matches `import x from 'mod'`, `import 'mod'`, `import { x } from "mod"`,
# optionally preceded by `export`.
JS_IMPORT_RE = re.compile(r"""^\s*(?:export\s+)?import\s+(?:.+?\s+from\s+)?['"]([^'"]+)['"]""")
# Matches `require('mod')`.
JS_REQUIRE_RE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
# Matches dynamic `import('mod')`.
JS_DYNAMIC_IMPORT_RE = re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)""")
JS_IMPORT_PATTERNS = (JS_IMPORT_RE, JS_REQUIRE_RE, JS_DYNAMIC_IMPORT_RE)
JS_COMMENT_PREFIXES = ("//", "*", "/*")

# Fallback scan for Python files that failed to parse. Matches `import
# mod.sub` and `from mod.sub import name`. Weaker than the AST check: it
# only sees the first name on an `import a, b` line and can be fooled by
# a match inside a triple-quoted string, but a degraded scan on a broken
# file beats no scan at all.
PY_IMPORT_RE = re.compile(r"^\s*import\s+([\w][\w.]*)")
PY_FROM_IMPORT_RE = re.compile(r"^\s*from\s+([\w][\w.]*)\s+import\b")
PY_IMPORT_PATTERNS = (PY_IMPORT_RE, PY_FROM_IMPORT_RE)
PY_COMMENT_PREFIXES = ("#",)


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    imported: str
    pattern: str

    def __str__(self) -> str:
        return (
            f"{self.path.as_posix()}:{self.line}: "
            f"forbidden import '{self.imported}' (matches '{self.pattern}')"
        )


@dataclass(frozen=True)
class ParseWarning:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path.as_posix()}: warning: {self.message}"


@dataclass(frozen=True)
class Config:
    forbidden: tuple[str, ...]
    exceptions: tuple[str, ...]


def load_config(path: Path = CONFIG_PATH) -> Config:
    with path.open("rb") as f:
        data = tomllib.load(f)
    forbidden = tuple(data.get("packages", {}).get("forbidden", []))
    exceptions = tuple(data.get("exceptions", {}).get("paths", []))
    return Config(forbidden=forbidden, exceptions=exceptions)


def matches_forbidden(name: str, patterns: tuple[str, ...]) -> str | None:
    """Return the pattern that forbids `name`, or None if it's allowed.

    A trailing `*` on a pattern matches any name with that prefix (used
    for scoped/namespaced packages like "@aws-sdk/*"). A pattern without
    a trailing `*` matches the name exactly or as a dotted parent module
    (so "boto3" also forbids "boto3.session").
    """
    for pattern in patterns:
        if pattern.endswith("*"):
            if name.startswith(pattern[:-1]):
                return pattern
        elif name == pattern or name.startswith(pattern + "."):
            return pattern
    return None


def is_exempt(rel_path: str, exceptions: tuple[str, ...]) -> bool:
    return any(rel_path == exc or rel_path.startswith(exc) for exc in exceptions)


def scan_lines_for_imports(
    path: Path,
    lines: list[str],
    forbidden: tuple[str, ...],
    patterns: tuple[re.Pattern[str], ...],
    comment_prefixes: tuple[str, ...],
) -> list[Violation]:
    violations = []
    for lineno, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if any(stripped.startswith(prefix) for prefix in comment_prefixes):
            continue
        for regex in patterns:
            match = regex.search(raw_line)
            if not match:
                continue
            imported = match.group(1)
            pattern = matches_forbidden(imported, forbidden)
            if pattern:
                violations.append(Violation(path, lineno, imported, pattern))
    return violations


def check_python_file(
    path: Path, forbidden: tuple[str, ...]
) -> tuple[list[Violation], ParseWarning | None]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], None

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        warning = ParseWarning(
            path,
            f"could not parse as Python (line {exc.lineno}: {exc.msg}); "
            "falling back to a weaker line-based import scan",
        )
        violations = scan_lines_for_imports(
            path, source.splitlines(), forbidden, PY_IMPORT_PATTERNS, PY_COMMENT_PREFIXES
        )
        return violations, warning

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                pattern = matches_forbidden(alias.name, forbidden)
                if pattern:
                    violations.append(Violation(path, node.lineno, alias.name, pattern))
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            pattern = matches_forbidden(node.module, forbidden)
            if pattern:
                violations.append(Violation(path, node.lineno, node.module, pattern))
    return violations, None


def check_js_file(path: Path, forbidden: tuple[str, ...]) -> list[Violation]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    return scan_lines_for_imports(path, lines, forbidden, JS_IMPORT_PATTERNS, JS_COMMENT_PREFIXES)


def should_skip(path: Path) -> bool:
    return any(part in IGNORED_DIR_PARTS for part in path.parts)


def check_file(path: Path, config: Config) -> tuple[list[Violation], ParseWarning | None]:
    if should_skip(path) or not path.is_file():
        return [], None

    try:
        rel_path = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel_path = path.as_posix()

    if is_exempt(rel_path, config.exceptions):
        return [], None

    if path.suffix in PY_SUFFIXES:
        return check_python_file(path, config.forbidden)
    if path.suffix in JS_SUFFIXES:
        return check_js_file(path, config.forbidden), None
    return [], None


def iter_target_files(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(p) for p in paths]
    return [path for suffix in PY_SUFFIXES | JS_SUFFIXES for path in REPO_ROOT.rglob(f"*{suffix}")]


def build_hook_payload(violations: list[Violation], warnings: list[ParseWarning]) -> dict | None:
    """Build the Claude Code PostToolUse hook JSON payload, or None if
    there is nothing to report."""
    if not violations and not warnings:
        return None

    payload: dict = {}
    if violations:
        payload["decision"] = "block"
        payload["reason"] = "\n".join(str(v) for v in violations)
    if warnings:
        payload["hookSpecificOutput"] = {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(str(w) for w in warnings),
        }
    return payload


def main(argv: list[str]) -> int:
    json_mode = "--json" in argv
    file_args = [arg for arg in argv if arg != "--json"]

    config = load_config()
    violations: list[Violation] = []
    warnings: list[ParseWarning] = []
    for path in iter_target_files(file_args):
        file_violations, warning = check_file(path, config)
        violations.extend(file_violations)
        if warning is not None:
            warnings.append(warning)

    if json_mode:
        payload = build_hook_payload(violations, warnings)
        if payload is not None:
            print(json.dumps(payload))
    else:
        for violation in violations:
            print(violation)
        for warning in warnings:
            print(warning)

    if file_args:
        return 1 if violations else 0
    return 1 if violations or warnings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
