"""Request-time template slots. Extensions provide templates, never raw HTML."""

from collections.abc import Mapping
from dataclasses import dataclass

from starlette.requests import Request


@dataclass(frozen=True)
class UIFragment:
    template: str
    context: Mapping[str, object]


async def ui_slots(request: Request, *slots: str) -> dict[str, tuple[UIFragment, ...]]:
    contributions = getattr(request.app.state, "extension_contributions", None)
    result: dict[str, list[UIFragment]] = {slot: [] for slot in slots}
    for item in getattr(contributions, "ui_contributions", ()):
        if item.slot in result and await item.available(request):
            result[item.slot].append(
                UIFragment(item.template, await item.context(request))
            )
    return {slot: tuple(items) for slot, items in result.items()}
