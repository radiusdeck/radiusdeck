from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from importlib import metadata
from pathlib import Path

COMMUNITY_FORBIDDEN_PATH_PARTS = (
    "radiusdeck_pro",
    "radiusdeck/api/",
    "templates/pro/",
    "auth/oidc/",
    "entitlements/",
)
COMMUNITY_FORBIDDEN_TEXT = (
    "radiusdeck_pro",
    "APP_PRO_DEV_MODE",
    "APP_LICENSE_FILE",
    "APP_OIDC_",
    "Edition.PRO",
    "/api/v1",
    "features.",
)
TEXT_SUFFIXES = {".py", ".html", ".js", ".json", ".toml", ".md"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_community_wheel(wheel: Path) -> None:
    violations: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for name in names:
            lowered = name.lower()
            if any(part.lower() in lowered for part in COMMUNITY_FORBIDDEN_PATH_PARTS):
                violations.append(f"forbidden path: {name}")
            if Path(name).suffix in TEXT_SUFFIXES:
                text = archive.read(name).decode("utf-8", errors="replace")
                for token in COMMUNITY_FORBIDDEN_TEXT:
                    if token.lower() in text.lower():
                        violations.append(f"forbidden token {token!r}: {name}")
        required = {
            "radiusdeck/main.py",
            "radiusdeck/cli/main.py",
            "radiusdeck/templates/clients.html",
            "radiusdeck/extensions/api.py",
        }
        missing = required - set(names)
        violations.extend(f"missing required path: {name}" for name in sorted(missing))
    if violations:
        raise SystemExit("Community wheel purity failed:\n" + "\n".join(violations))
    print(f"Community wheel purity passed: {wheel.name} sha256={sha256(wheel)}")


def installed_manifest(output: Path) -> None:
    import radiusdeck

    package_root = Path(radiusdeck.__file__).resolve().parent
    files = {
        str(path.relative_to(package_root)): sha256(path)
        for path in sorted(package_root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }
    payload = {
        "distribution": "radiusdeck",
        "version": metadata.version("radiusdeck"),
        "files": files,
    }
    output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def verify_manifest(expected: Path) -> None:
    temporary = expected.with_suffix(".actual.json")
    installed_manifest(temporary)
    try:
        if json.loads(expected.read_text()) != json.loads(temporary.read_text()):
            raise SystemExit("Installed Community package differs from tested manifest")
    finally:
        temporary.unlink(missing_ok=True)
    print("Installed Community version and package-file hashes are unchanged")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    subparsers = result.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser("inspect-community-wheel")
    inspect.add_argument("wheel", type=Path)
    manifest = subparsers.add_parser("installed-manifest")
    manifest.add_argument("output", type=Path)
    verify = subparsers.add_parser("verify-manifest")
    verify.add_argument("expected", type=Path)
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "inspect-community-wheel":
        inspect_community_wheel(args.wheel)
    elif args.command == "installed-manifest":
        installed_manifest(args.output)
    elif args.command == "verify-manifest":
        verify_manifest(args.expected)


if __name__ == "__main__":
    main()
