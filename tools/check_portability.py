"""Enforce the cloud-portability rule: no cloud-provider SDK may be
imported outside infra/adapters/.

Usage:
    uv run python tools/check_portability.py [FILE ...]

With no arguments, scans the whole repository. With arguments, scans only
the given files (used by pre-commit to check staged files).

Exit code is 0 with no violations, 1 otherwise. Each violation is printed
as a single "path:line: ..." line, one per offending import.

Python files (.py) are parsed with the `ast` module and checked for
Import/ImportFrom nodes. This is deliberate: a regex cannot distinguish a
real import from a mention of the same name inside a docstring, a string
literal, or a comment, and those false positives are exactly what makes
teams disable a check like this. The AST gives us the real structure of
the file.

TypeScript/JavaScript files (.ts, .tsx, .js, .mjs) are checked with a
line-by-line regex scan for `import` statements and `require()` calls.
This is weaker than the Python AST check: it can be fooled by a matching
string inside a multi-line comment or a template literal, for instance.
That trade-off is accepted on purpose — pulling in a real TypeScript
parser as a tooling dependency just for this check is not worth it. If
false positives on the JS/TS side become a real problem, revisit this.
"""

from __future__ import annotations

import ast
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


def check_python_file(path: Path, forbidden: tuple[str, ...]) -> list[Violation]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

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
    return violations


def check_js_file(path: Path, forbidden: tuple[str, ...]) -> list[Violation]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    violations = []
    for lineno, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        for regex in (JS_IMPORT_RE, JS_REQUIRE_RE, JS_DYNAMIC_IMPORT_RE):
            match = regex.search(raw_line)
            if not match:
                continue
            imported = match.group(1)
            pattern = matches_forbidden(imported, forbidden)
            if pattern:
                violations.append(Violation(path, lineno, imported, pattern))
    return violations


def should_skip(path: Path) -> bool:
    return any(part in IGNORED_DIR_PARTS for part in path.parts)


def check_file(path: Path, config: Config) -> list[Violation]:
    if should_skip(path) or not path.is_file():
        return []

    try:
        rel_path = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel_path = path.as_posix()

    if is_exempt(rel_path, config.exceptions):
        return []

    if path.suffix in PY_SUFFIXES:
        return check_python_file(path, config.forbidden)
    if path.suffix in JS_SUFFIXES:
        return check_js_file(path, config.forbidden)
    return []


def iter_target_files(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(p) for p in paths]
    return [path for suffix in PY_SUFFIXES | JS_SUFFIXES for path in REPO_ROOT.rglob(f"*{suffix}")]


def main(argv: list[str]) -> int:
    config = load_config()
    violations = [
        violation for path in iter_target_files(argv) for violation in check_file(path, config)
    ]
    for violation in violations:
        print(violation)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
