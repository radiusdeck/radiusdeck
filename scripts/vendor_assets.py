"""Copy browser libraries pinned in package-lock.json into the static directory.

    python scripts/vendor_assets.py          download, verify, and write the files
    python scripts/vendor_assets.py --check  verify the committed files offline

The package tarballs are verified against the lock file's SHA-512 integrity
before any file is written. The check mode compares the lock file with
static/vendor/manifest.json and the files with the hashes in the manifest, so
CI fails when a dependency update changed the lock file but not the copies.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parent.parent
LOCK_FILE = REPOSITORY / "package-lock.json"
VENDOR_DIR = REPOSITORY / "src" / "radiusdeck" / "static" / "vendor"
MANIFEST = VENDOR_DIR / "manifest.json"
REGISTRY = "https://registry.npmjs.org/"

# npm package -> (directory under static/vendor, files inside the package)
VENDOR_FILES: dict[str, tuple[str, tuple[str, ...]]] = {
    "bootstrap": (
        "bootstrap",
        ("dist/css/bootstrap.min.css", "dist/js/bootstrap.bundle.min.js", "LICENSE"),
    ),
    "htmx.org": ("htmx", ("dist/htmx.min.js", "LICENSE")),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def locked_packages() -> dict[str, dict[str, Any]]:
    lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    packages: dict[str, dict[str, Any]] = lock["packages"]
    result: dict[str, dict[str, Any]] = {}
    for name in VENDOR_FILES:
        entry = packages.get(f"node_modules/{name}")
        if entry is None:
            raise SystemExit(f"{name} is missing from {LOCK_FILE.name}")
        result[name] = entry
    return result


def download(name: str, entry: dict[str, Any]) -> bytes:
    url = str(entry["resolved"])
    if not url.startswith(REGISTRY):
        raise SystemExit(f"{name}: unexpected tarball URL {url}")
    with urllib.request.urlopen(url, timeout=60) as response:  # nosec B310
        data: bytes = response.read()
    algorithm, _, expected = str(entry["integrity"]).partition("-")
    if algorithm != "sha512":
        raise SystemExit(f"{name}: unsupported integrity algorithm {algorithm}")
    actual = base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")
    if actual != expected:
        raise SystemExit(f"{name}: tarball does not match the lock file integrity")
    return data


def extract(name: str, tarball: bytes, paths: tuple[str, ...]) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
        for path in paths:
            member = archive.getmember(f"package/{path}")
            stream = archive.extractfile(member) if member.isfile() else None
            if stream is None:
                raise SystemExit(f"{name}: {path} is not a regular file")
            files[Path(path).name] = stream.read()
    return files


def write() -> None:
    manifest: dict[str, Any] = {}
    for name, entry in locked_packages().items():
        directory, paths = VENDOR_FILES[name]
        files = extract(name, download(name, entry), paths)
        target = VENDOR_DIR / directory
        target.mkdir(parents=True, exist_ok=True)
        for stale in target.iterdir():
            if stale.name not in files:
                stale.unlink()
        for filename, data in files.items():
            (target / filename).write_bytes(data)
        manifest[name] = {
            "version": entry["version"],
            "integrity": entry["integrity"],
            "directory": directory,
            "files": {
                filename: sha256(data) for filename, data in sorted(files.items())
            },
        }
        print(f"{name} {entry['version']} -> {target.relative_to(REPOSITORY)}")
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def check() -> None:
    if not MANIFEST.is_file():
        raise SystemExit(
            f"{MANIFEST.relative_to(REPOSITORY)} is missing; run make vendor-assets"
        )
    manifest: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems: list[str] = []
    locked = locked_packages()
    for name in sorted(set(manifest) - set(locked)):
        problems.append(f"{name}: in the manifest but not vendored from the lock file")
    for name, entry in locked.items():
        recorded = manifest.get(name)
        if recorded is None:
            problems.append(f"{name}: missing from the manifest")
            continue
        if (recorded["version"], recorded["integrity"]) != (
            entry["version"],
            entry["integrity"],
        ):
            problems.append(
                f"{name}: lock file has {entry['version']}, vendored copy is {recorded['version']}"
            )
        target = VENDOR_DIR / recorded["directory"]
        present = {path.name for path in target.iterdir()} if target.is_dir() else set()
        for filename in sorted(present - set(recorded["files"])):
            problems.append(f"{name}: unexpected file {filename}")
        for filename, digest in recorded["files"].items():
            path = target / filename
            if not path.is_file():
                problems.append(f"{name}: missing {filename}")
            elif sha256(path.read_bytes()) != digest:
                problems.append(f"{name}: {filename} differs from the manifest")
    if problems:
        raise SystemExit(
            "Vendored browser libraries are out of date:\n"
            + "\n".join(f"- {problem}" for problem in problems)
            + "\nRun `make vendor-assets` and commit the result."
        )
    print("Vendored browser libraries match package-lock.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="verify without downloading"
    )
    if parser.parse_args().check:
        check()
    else:
        write()


if __name__ == "__main__":
    main()
