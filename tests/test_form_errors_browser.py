"""Browser test: an Add Client error is shown as text under the form.

The endpoint sends the message in HX-Trigger as {"clientAddError": "<text>"};
htmx passes a string value to the listener as evt.detail.value.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.conftest import LiveServer


def _submit(page: Page, live_server: LiveServer, name: str) -> None:
    page.goto(live_server.url + "/ui/clients")
    form = page.locator("#add-form")
    form.locator("input[name=name]").fill(name)
    form.locator("input[name=ip_addr]").fill("192.0.2.10")
    form.locator("input[name=secret]").fill("example-secret-change-me")
    form.get_by_role("button", name="Add Client", exact=True).click()


def test_existing_name_error_is_shown(page: Page, live_server: LiveServer) -> None:
    _submit(page, live_server, "LOCAL")

    expect(page.locator("#form-errors")).to_have_text(
        "Client LOCAL already exists. Use Edit to change it."
    )


def test_invalid_payload_error_is_shown(page: Page, live_server: LiveServer) -> None:
    _submit(page, live_server, "my ap")

    expect(page.locator("#form-errors")).to_have_text(
        "Unable to add client. Check form values."
    )
