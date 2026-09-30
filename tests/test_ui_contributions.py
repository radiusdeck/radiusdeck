from collections.abc import Mapping
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from radiusdeck.core.config import settings
from radiusdeck.extensions import (
    RADIUSDECK_EXTENSION_API,
    ExtensionDefinition,
    StructuralContributions,
)
from radiusdeck.extensions.contributions import UIContribution
from radiusdeck.extensions.errors import (
    ExtensionConfigurationError,
    ExtensionConflictError,
)
from radiusdeck.main import create_app


async def available(request: Request) -> bool:
    return request.query_params.get("show") == "yes"


async def context(request: Request) -> Mapping[str, object]:
    return {"label": "<script>opaque extension text</script>"}


def definition(path: Path, *items: UIContribution) -> ExtensionDefinition:
    return ExtensionDefinition(
        name="ui-test",
        extension_api_version=RADIUSDECK_EXTENSION_API,
        structural_contributions=lambda _: StructuralContributions(
            template_search_paths=(path,), ui_contributions=items
        ),
    )


@pytest.mark.parametrize(
    "slot,page",
    [
        ("backups.sections", "/ui/backups"),
        ("backups.toolbar", "/ui/backups"),
        ("logs.sections", "/ui/logs"),
        ("logs.toolbar", "/ui/logs"),
    ],
)
def test_ui_availability_context_and_application_template_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, slot: str, page: str
) -> None:
    monkeypatch.setattr(settings, "auth_method", "none")
    monkeypatch.setattr(settings, "backup_enabled", False)
    log = tmp_path / "radius.log"
    log.write_text("Info ready\n")
    monkeypatch.setattr(settings, "freeradius_log_viewer_enabled", True)
    monkeypatch.setattr(settings, "freeradius_log_path", log)
    (tmp_path / "extra.html").write_text(
        '<p id="extension">{{ contribution.context.label }}</p>'
    )
    item = UIContribution("extra", slot, "extra.html", available, context)
    application = create_app(extensions=(definition(tmp_path, item),))
    plain = create_app(extensions=())
    with TestClient(application) as client, TestClient(plain) as community:
        assert 'id="extension"' not in client.get(page).text
        response = client.get(page + "?show=yes")
        assert 'id="extension"' in response.text
        assert "&lt;script&gt;opaque extension text&lt;/script&gt;" in response.text
        assert 'id="extension"' not in community.get(page + "?show=yes").text


@pytest.mark.parametrize("broken", ["missing", "syntax", "include"])
def test_broken_contributed_template_fails_creation(
    tmp_path: Path, broken: str
) -> None:
    if broken == "syntax":
        (tmp_path / "extra.html").write_text("{% if %}")
    elif broken == "include":
        (tmp_path / "extra.html").write_text('{% include "missing-nested.html" %}')
    item = UIContribution("extra", "logs.sections", "extra.html", available, context)
    with pytest.raises(ExtensionConfigurationError, match="Invalid UI template"):
        create_app(extensions=(definition(tmp_path, item),))


def test_duplicate_ui_identifiers_fail_creation(tmp_path: Path) -> None:
    item = UIContribution("same", "logs.sections", "extra.html", available, context)
    with pytest.raises(ExtensionConflictError, match="Duplicate UI contribution"):
        create_app(extensions=(definition(tmp_path, item, item),))


def test_community_templates_have_no_advanced_feature_knowledge() -> None:
    for path in Path("src/radiusdeck/templates").rglob("*.html"):
        source = path.read_text()
        assert "features." not in source, path
        assert "requires Pro" not in source, path
        assert "/ui/logs/download" not in source, path
        assert "/backups/create" not in source, path
