"""The web interface serves its browser libraries itself."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

ASSET_REFERENCE = re.compile(r"<(?:script|link)\b[^>]*\b(?:src|href)=\"([^\"]+)\"")
VENDOR_ASSETS = {
    "/static/vendor/bootstrap/bootstrap.min.css": "text/css",
    "/static/vendor/bootstrap/bootstrap.bundle.min.js": "javascript",
    "/static/vendor/htmx/htmx.min.js": "javascript",
}


@pytest.mark.parametrize("path", ["/ui/clients", "/ui/backups", "/ui/status"])
def test_pages_load_scripts_and_styles_only_from_the_application(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    references = ASSET_REFERENCE.findall(response.text)
    assert set(VENDOR_ASSETS) <= set(references)
    assert [ref for ref in references if not ref.startswith("/static/")] == []


@pytest.mark.parametrize("path,content_type", VENDOR_ASSETS.items())
def test_vendored_assets_are_served(
    client: TestClient, path: str, content_type: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert len(response.content) > 10_000


def test_page_title_names_the_product(client: TestClient) -> None:
    response = client.get("/ui/clients")

    assert "<title>RadiusDeck</title>" in response.text
