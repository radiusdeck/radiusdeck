"""htmx attribute inheritance for the "+ Add field" / "+ Add block" buttons.

htmx 1.x lets a child element inherit hx-select from its ancestors. The create and
edit forms set hx-select for their own submit response; a button inside the form
that inherits it selects nothing from the /ui/clients/assignment-row or
/ui/clients/block-form fragment, so no row is inserted.
"""

from __future__ import annotations

from html.parser import HTMLParser

from fastapi.testclient import TestClient

from tests.conftest import UiEnv

_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta"}
    | {"source", "track", "wbr"}
)


def _disinherits(attrs: dict[str, str | None], name: str) -> bool:
    value = attrs.get("hx-disinherit") or ""
    return "*" in value.split() or name in value.split()


def _effective(
    own: dict[str, str | None], ancestors: list[dict[str, str | None]], name: str
) -> str | None:
    """Value htmx uses for attribute `name` on an element (own value or inherited)."""
    if name in own:
        return own[name]
    for ancestor in reversed(ancestors):
        if name in ancestor:
            return None if _disinherits(ancestor, name) else ancestor[name]
    return None


class _HxGetCollector(HTMLParser):
    """Collects hx-get elements with their effective hx-select.

    `context` holds the attributes of the elements the parsed HTML is inserted into,
    outermost first, for fragments that htmx swaps into a form.
    """

    def __init__(self, context: list[dict[str, str | None]] | None = None) -> None:
        super().__init__()
        self._stack: list[tuple[str, dict[str, str | None]]] = []
        self._context = context or []
        self.forms: dict[str, dict[str, str | None]] = {}
        self.buttons: list[tuple[str | None, str | None, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        own = dict(attrs)
        if tag == "form" and own.get("id"):
            self.forms[str(own["id"])] = own
        if "hx-get" in own:
            ancestors = self._context + [a for _, a in self._stack]
            form_id = next(
                (str(a["id"]) for t, a in reversed(self._stack) if t == "form"), None
            )
            self.buttons.append(
                (form_id, own["hx-get"], _effective(own, ancestors, "hx-select"))
            )
        if tag not in _VOID_TAGS:
            self._stack.append((tag, own))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break


def _collect(
    html: str, context: list[dict[str, str | None]] | None = None
) -> _HxGetCollector:
    parser = _HxGetCollector(context)
    parser.feed(html)
    return parser


def _assert_buttons_insert_whole_fragment(
    buttons: list[tuple[str | None, str | None, str | None]],
) -> None:
    assert buttons, "expected hx-get buttons in the form"
    for form_id, url, hx_select in buttons:
        assert hx_select is None, (
            f"{url} in #{form_id} inherits hx-select={hx_select!r}; "
            "the fragment would be filtered out and nothing inserted"
        )


def test_create_form_buttons_do_not_inherit_hx_select(client: TestClient) -> None:
    page = _collect(client.get("/ui/clients").text)
    in_form = [b for b in page.buttons if b[0] == "add-form"]

    assert {url for _, url, _ in in_form} >= {
        "/ui/clients/assignment-row",
        "/ui/clients/block-form?depth=0",
    }
    _assert_buttons_insert_whole_fragment(in_form)


def test_edit_form_buttons_do_not_inherit_hx_select(env_complex: UiEnv) -> None:
    # LOCAL has a nested `limit` block, so the filled block buttons are rendered too.
    form = _collect(env_complex.client.get("/ui/clients/LOCAL/edit-form").text)
    in_form = [b for b in form.buttons if b[0] == "edit-form"]

    assert {url for _, url, _ in in_form} >= {
        "/ui/clients/assignment-row",
        "/ui/clients/block-form?depth=0",
        "/ui/clients/block-form?depth=1",
    }
    _assert_buttons_insert_whole_fragment(in_form)


def test_inserted_block_buttons_do_not_inherit_hx_select(env_complex: UiEnv) -> None:
    """Buttons of a block added at runtime live inside the form as well."""
    c = env_complex.client
    forms = {
        **_collect(c.get("/ui/clients").text).forms,
        **_collect(c.get("/ui/clients/LOCAL/edit-form").text).forms,
    }
    fragment = c.get("/ui/clients/block-form?depth=0").text

    for form_id in ("add-form", "edit-form"):
        inserted = _collect(fragment, context=[forms[form_id]])
        _assert_buttons_insert_whole_fragment(
            [(form_id, url, sel) for _, url, sel in inserted.buttons]
        )
