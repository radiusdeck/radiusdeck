#!/usr/bin/env python3

from __future__ import annotations

import re
from collections import deque
from pathlib import Path

TEMPLATES_DIR = Path("src/radiusdeck/templates")

PY_TEMPLATE_RE = re.compile(r'TemplateResponse\(\s*["\']([^"\']+)["\']')
JINJA_RE = re.compile(r'{%\s*(?:include|extends)\s+["\']([^"\']+)["\']\s*%}')


def iter_files(root: Path, suffix: str) -> list[Path]:
    return [p for p in root.rglob(f"*{suffix}") if p.is_file()]


def extract_python_template_refs(py_file: Path) -> set[str]:
    text = py_file.read_text(encoding="utf-8")
    return set(PY_TEMPLATE_RE.findall(text))


def extract_jinja_refs(template_file: Path) -> set[str]:
    text = template_file.read_text(encoding="utf-8")
    return set(JINJA_RE.findall(text))


def main() -> None:
    all_templates = {
        str(p.relative_to(TEMPLATES_DIR)).replace("\\", "/")
        for p in iter_files(TEMPLATES_DIR, ".html")
    }

    # seed templates = everything rendered from Python via TemplateResponse
    seeds: set[str] = set()
    for py_file in iter_files(Path("app"), ".py"):
        seeds |= extract_python_template_refs(py_file)

    # traverse includes/extends, starting from seeds
    reachable: set[str] = set()
    q: deque[str] = deque(sorted(seeds))

    while q:
        name = q.popleft()
        if name in reachable:
            continue
        reachable.add(name)

        path = TEMPLATES_DIR / name
        if not path.exists():
            # happens if name is formed dynamically or typo
            continue

        for ref in extract_jinja_refs(path):
            if ref not in reachable:
                q.append(ref)

    unused = sorted(all_templates - reachable)
    missing = sorted(seeds - all_templates)

    print("== Seeds from Python (TemplateResponse) ==")
    for s in sorted(seeds):
        print("  ", s)

    print("\n== Missing templates referenced by Python (not found on disk) ==")
    for m in missing:
        print("  ", m)

    print("\n== Unused templates (not reachable from any TemplateResponse seed) ==")
    for u in unused:
        print("  ", u)


if __name__ == "__main__":
    main()
