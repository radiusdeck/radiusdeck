"""Browser test: "+ Add field" and "+ Add block" insert rows and the rows are saved.

Runs the app with uvicorn and drives it with Playwright (Chromium); the
`live_server` and `page` fixtures are in conftest.py.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page, expect

from tests.conftest import LiveServer


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
