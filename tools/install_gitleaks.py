"""Download and verify the gitleaks CLI binary from its GitHub release.

Usage:
    uv run python tools/install_gitleaks.py [DEST_DIR]

DEST_DIR defaults to tools/.bin/. The resolved path to the extracted
binary is printed on stdout as the last line, so callers (CI, other
scripts) can capture it with e.g. `$(uv run python tools/install_gitleaks.py)`.

We use the gitleaks CLI directly instead of gitleaks/gitleaks-action
because the Action requires a paid license for organization-owned repos,
while the CLI itself is MIT-licensed and free to use anywhere. See
docs/decisions/0002-enforcement-de-portabilidad.md.

The version is pinned explicitly (never "latest") and each archive's
sha256 is checked against a hash embedded in this file, so a compromised
or tampered release download fails closed instead of running unverified
code. The expected hashes were copied from gitleaks' own
gitleaks_<version>_checksums.txt at the time this script was written, not
fetched at install time -- downloading the checksum file from the same
release at run time would not catch a release that was compromised at
the source, since the attacker would replace both files together.
"""

from __future__ import annotations

import hashlib
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

GITLEAKS_VERSION = "8.30.1"
RELEASE_URL = f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}"

# (system, machine) -> (asset filename, sha256 of that asset, binary name inside it)
_ASSETS: dict[tuple[str, str], tuple[str, str, str]] = {
    ("Linux", "x86_64"): (
        f"gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz",
        "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
        "gitleaks",
    ),
    ("Linux", "aarch64"): (
        f"gitleaks_{GITLEAKS_VERSION}_linux_arm64.tar.gz",
        "e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080",
        "gitleaks",
    ),
    ("Darwin", "x86_64"): (
        f"gitleaks_{GITLEAKS_VERSION}_darwin_x64.tar.gz",
        "dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709",
        "gitleaks",
    ),
    ("Darwin", "arm64"): (
        f"gitleaks_{GITLEAKS_VERSION}_darwin_arm64.tar.gz",
        "b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5",
        "gitleaks",
    ),
    ("Windows", "AMD64"): (
        f"gitleaks_{GITLEAKS_VERSION}_windows_x64.zip",
        "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
        "gitleaks.exe",
    ),
}


def _current_platform_key() -> tuple[str, str]:
    return (platform.system(), platform.machine())


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url) as response, open(dest, "wb") as f:  # noqa: S310
        shutil.copyfileobj(response, f)


def _verify_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(
            f"checksum mismatch for {path.name}: expected {expected}, got {digest}. "
            "Refusing to use this binary."
        )


def _extract_binary(archive: Path, binary_name: str, dest_dir: Path) -> Path:
    dest = dest_dir / binary_name
    if archive.suffixes[-2:] == [".tar", ".gz"]:
        with tarfile.open(archive, "r:gz") as tar:
            member = tar.getmember(binary_name)
            with tar.extractfile(member) as src, open(dest, "wb") as out:  # type: ignore[union-attr]
                shutil.copyfileobj(src, out)
    elif archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf, zf.open(binary_name) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)
    else:
        raise SystemExit(f"unsupported archive type: {archive.name}")
    dest.chmod(0o755)
    return dest


def install(dest_dir: Path) -> Path:
    key = _current_platform_key()
    if key not in _ASSETS:
        raise SystemExit(f"no pinned gitleaks build for platform {key}")
    asset_name, expected_sha256, binary_name = _ASSETS[key]

    dest_dir.mkdir(parents=True, exist_ok=True)
    binary_path = dest_dir / binary_name
    if binary_path.exists():
        return binary_path

    archive_path = dest_dir / asset_name
    _download(f"{RELEASE_URL}/{asset_name}", archive_path)
    _verify_sha256(archive_path, expected_sha256)
    binary_path = _extract_binary(archive_path, binary_name, dest_dir)
    archive_path.unlink()
    return binary_path


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / ".bin"
    print(install(dest).resolve())
