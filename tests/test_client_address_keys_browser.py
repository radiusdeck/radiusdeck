"""Browser test: the stock ipv6addr client is listed with its address and editable."""

from __future__ import annotations

import time

from playwright.sync_api import Page, expect

from tests.conftest import LiveServer

CONFIG = """client localhost_ipv6 {
    ipv6addr = ::1
    secret = testing123
}
"""


def test_ipv6addr_client_is_listed_and_editable(
    page: Page, live_server: LiveServer
) -> None:
    live_server.config_path.write_text(CONFIG, encoding="utf-8")
    page.goto(live_server.url + "/ui/clients")
    row = page.locator("#client-block-localhost_ipv6 > tr").first
    expect(row.locator("td").nth(1)).to_have_text("::1")

    row.get_by_role("button", name="Edit", exact=True).click()
    form = page.locator("#edit-form")
    expect(form.locator("input[name=ip_addr]")).to_have_value("::1")
    form.locator("input[name=ip_addr]").fill("::2")
    form.get_by_role("button", name="Save Changes", exact=True).click()

    expect(row.locator("td").nth(1)).to_have_text("::2")
    deadline = time.monotonic() + 5
    while "ipv6addr = ::2" not in live_server.config_path.read_text(encoding="utf-8"):
        assert time.monotonic() < deadline, "clients.conf was not updated"
        time.sleep(0.1)
    assert "ipaddr =" not in live_server.config_path.read_text(encoding="utf-8")
