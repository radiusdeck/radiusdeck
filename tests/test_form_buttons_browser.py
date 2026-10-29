"""Browser test: "+ Add field" and "+ Add block" insert rows and the rows are saved.

Runs the app with uvicorn and drives it with Playwright (Chromium). Skipped when
Chromium is not installed: `python -m playwright install chromium`.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import uvicorn
from playwright.sync_api import Page, expect, sync_playwright

from radiusdeck.main import app
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.reload_models import ReloadResult
from radiusdeck.web.deps import get_radius_service


def _chromium_installed() -> bool:
    try:
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _chromium_installed(),
    reason="Chromium for Playwright is not installed",
)


@pytest.fixture()
def page() -> Generator[Page, None, None]:
    # Not pytest-playwright's session-scoped fixtures: they keep an event loop
    # running in the main thread, which breaks the asyncio tests that run after.
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            yield browser.new_page()
        finally:
            browser.close()


@dataclass(frozen=True)
class LiveServer:
    url: str
    config_path: Path


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture()
def live_server(tmp_path: Path) -> Generator[LiveServer, None, None]:
    config_file = tmp_path / "clients.conf"
    config_file.write_text(
        "client LOCAL {\n    ipaddr = 127.0.0.1\n    secret = testing123\n}\n",
        encoding="utf-8",
    )
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.skipped()
    service = RadiusService(ClientsConfStore(config_file), reloader=reloader)
    app.dependency_overrides[get_radius_service] = lambda: service

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.05)

    yield LiveServer(url=f"http://127.0.0.1:{port}", config_path=config_file)

    server.should_exit = True
    thread.join(timeout=10)
    app.dependency_overrides.pop(get_radius_service, None)


def _wait_for_file(path: Path, text: str) -> str:
    deadline = time.monotonic() + 5
    while True:
        content = path.read_text(encoding="utf-8")
        if text in content or time.monotonic() > deadline:
            return content
        time.sleep(0.1)


def test_create_form_adds_field_and_block(page: Page, live_server: LiveServer) -> None:
    page.goto(live_server.url + "/ui/clients")
    form = page.locator("#add-form")

    form.get_by_role("button", name="+ Add field", exact=True).click()
    row = form.locator("#extra-params .assignment-row")
    expect(row).to_have_count(1)
    row.locator(".assignment-key").fill("shortname")
    row.locator(".assignment-value").fill("office")

    form.get_by_role("button", name="+ Add block", exact=True).click()
    block = form.locator("#nested-blocks > .client-block")
    expect(block).to_have_count(1)
    block.locator(".block-kind").fill("limit")

    # Buttons of the inserted block are inside the form too.
    block.get_by_role("button", name="Add param", exact=True).click()
    block_row = block.locator(".block-assignments .assignment-row")
    expect(block_row).to_have_count(1)
    block_row.locator(".assignment-key").fill("max_connections")
    block_row.locator(".assignment-value").fill("16")

    form.locator("input[name=name]").fill("office-ap-01")
    form.locator("input[name=ip_addr]").fill("192.0.2.10")
    form.locator("input[name=secret]").fill("example-secret-change-me")
    form.get_by_role("button", name="Add Client", exact=True).click()
    expect(page.locator("#client-block-office-ap-01")).to_have_count(1)

    content = _wait_for_file(live_server.config_path, "max_connections")
    assert "client office-ap-01 {" in content
    assert "shortname = office" in content
    assert "limit {" in content
    assert "max_connections = 16" in content


def test_edit_form_adds_field_and_block(page: Page, live_server: LiveServer) -> None:
    page.goto(live_server.url + "/ui/clients")
    page.locator("#client-block-LOCAL").get_by_role(
        "button", name="Edit", exact=True
    ).click()
    form = page.locator("#edit-form")
    expect(form).to_have_count(1)

    form.get_by_role("button", name="+ Add field", exact=True).click()
    row = form.locator("#extra-params .assignment-row")
    expect(row).to_have_count(1)
    row.locator(".assignment-key").fill("shortname")
    row.locator(".assignment-value").fill("local")

    form.get_by_role("button", name="+ Add block", exact=True).click()
    block = form.locator("#nested-blocks > .client-block")
    expect(block).to_have_count(1)
    block.locator(".block-kind").fill("limit")
    block.get_by_role("button", name="Add param", exact=True).click()
    block_row = block.locator(".block-assignments .assignment-row")
    expect(block_row).to_have_count(1)
    block_row.locator(".assignment-key").fill("lifetime")
    block_row.locator(".assignment-value").fill("0")

    form.get_by_role("button", name="Save Changes", exact=True).click()

    content = _wait_for_file(live_server.config_path, "lifetime")
    assert "shortname = local" in content
    assert "limit {" in content
    assert "lifetime = 0" in content
