"""Browser test: address errors and warnings are visible in the forms."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.conftest import LiveServer


def _add(page: Page, live_server: LiveServer, ipaddr: str) -> None:
    page.goto(live_server.url + "/ui/clients")
    form = page.locator("#add-form")
    form.locator("input[name=name]").fill("office-ap-01")
    form.locator("input[name=ip_addr]").fill(ipaddr)
    form.locator("input[name=secret]").fill("example-secret-change-me")
    form.get_by_role("button", name="Add Client", exact=True).click()


def test_add_invalid_address_error_is_shown(
    page: Page, live_server: LiveServer
) -> None:
    _add(page, live_server, "300.1.1.1")

    expect(page.locator("#add-form #form-errors")).to_have_text(
        'IP address "300.1.1.1" is not a valid IPv4 address or network.'
    )
    expect(page.locator("#client-block-office-ap-01")).to_have_count(0)


def test_add_host_name_warning_is_shown(page: Page, live_server: LiveServer) -> None:
    _add(page, live_server, "nas.example.com")

    expect(page.locator("#client-block-office-ap-01")).to_have_count(1)
    expect(page.locator("#reload-alerts")).to_contain_text(
        "FreeRADIUS resolves nas.example.com once at startup"
    )


def test_edit_invalid_address_error_is_shown(
    page: Page, live_server: LiveServer
) -> None:
    page.goto(live_server.url + "/ui/clients")
    page.locator("#client-block-LOCAL").get_by_role(
        "button", name="Edit", exact=True
    ).click()
    form = page.locator("#edit-form")
    form.locator("input[name=ip_addr]").fill("999.1.1.1")
    form.get_by_role("button", name="Save Changes", exact=True).click()

    expect(page.locator("#edit-form #form-errors")).to_have_text(
        'IP address "999.1.1.1" is not a valid IPv4 address or network.'
    )
    assert "ipaddr = 127.0.0.1" in live_server.config_path.read_text(encoding="utf-8")
