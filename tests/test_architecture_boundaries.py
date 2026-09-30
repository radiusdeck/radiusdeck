from __future__ import annotations

import ast
import re
from pathlib import Path


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def test_services_do_not_import_fastapi() -> None:
    violations: list[str] = []

    for path in _python_files(Path("src/radiusdeck/services")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue

            if any(
                module == "fastapi" or module.startswith("fastapi.")
                for module in modules
            ):
                violations.append(f"{path}:{node.lineno}")

    assert violations == []


def test_web_template_responses_use_request_first_argument() -> None:
    violations: list[str] = []

    for path in _python_files(Path("src/radiusdeck/web")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "TemplateResponse" or not node.args:
                continue
            if isinstance(node.args[0], ast.Constant) and isinstance(
                node.args[0].value, str
            ):
                violations.append(f"{path}:{node.lineno}")

    assert violations == []


def test_makefile_health_target_uses_actual_health_route() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "http://localhost:8000/health" in makefile
    assert "http://localhost:8000/api/health" not in makefile


def test_edition_decisions_are_centralized() -> None:
    comparison = re.compile(r"\bedition\s*(?:==|!=|\bis\b|\bis\s+not\b)")
    violations: list[str] = []

    for path in _python_files(Path("src/radiusdeck")):
        if Path("src/radiusdeck/entitlements") in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        if comparison.search(text) or "is_pro" in text or "pro_enabled" in text:
            violations.append(str(path))

    assert violations == []


def test_community_source_does_not_import_private_package() -> None:
    violations: list[str] = []

    for path in _python_files(Path("src/radiusdeck")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            if any(
                module == "radiusdeck_pro" or module.startswith("radiusdeck_pro.")
                for module in modules
            ):
                violations.append(f"{path}:{node.lineno}")

    assert violations == []


def test_old_production_import_namespace_is_absent() -> None:
    violations: list[str] = []

    for path in _python_files(Path("src/radiusdeck")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            if any(module == "app" or module.startswith("app.") for module in modules):
                violations.append(f"{path}:{node.lineno}")

    assert violations == []


def test_root_metadata_does_not_register_private_extension() -> None:
    metadata = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'entry-points."radiusdeck.extensions"' not in metadata
    assert "radiusdeck_pro" not in metadata


def test_base_auth_and_settings_are_provider_neutral() -> None:
    from radiusdeck.core.config import Settings

    base = Path("src/radiusdeck")
    assert not (base / "auth/oidc").exists()
    assert not (base / "entitlements").exists()
    assert not any(name.startswith("oidc_") for name in Settings.model_fields)
    assert {"edition", "license_file", "pro_dev_mode"}.isdisjoint(Settings.model_fields)
    for path in _python_files(base):
        content = path.read_text()
        assert "radiusdeck_pro" not in content, str(path)
        assert "OIDC" not in content and "oidc" not in content, str(path)
