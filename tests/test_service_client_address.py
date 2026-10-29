"""Address checks when a client is created or updated (RadiusService)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.schemas.client_edit_payload import (
    AssignmentEditPayload,
    ClientEditTreePayload,
)
from radiusdeck.schemas.client_payload_tree import ClientCreateTreePayload
from radiusdeck.services.errors import (
    DuplicateClientAddressError,
    InvalidClientAddressError,
)
from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.reload_models import ReloadResult

CONFIG = """client localhost {
    ipaddr = 127.0.0.1
    secret = testing123
}
client office-net {
    ipaddr = 198.51.100.0/24
    secret = example-secret
}
client legacy {
    ipaddr = 192.0.2 # written by hand
    secret = example-secret
}
client by-name {
    ipaddr = nas.example.com
    secret = example-secret
}
"""


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    p = tmp_path / "clients.conf"
    p.write_text(CONFIG, encoding="utf-8")
    return p


@pytest.fixture()
def reloader() -> AsyncMock:
    mock = AsyncMock(spec=ReloadPort)
    mock.reload.return_value = ReloadResult.skipped()
    return mock


@pytest.fixture()
def service(config_path: Path, reloader: AsyncMock) -> RadiusService:
    return RadiusService(ClientsConfStore(str(config_path)), reloader=reloader)


def _create(name: str, ipaddr: str) -> ClientCreateTreePayload:
    return ClientCreateTreePayload(name=name, ipaddr=ipaddr, secret="example-secret")


# ── create ───────────────────────────────────────────


@pytest.mark.parametrize("ipaddr", ["300.1.1.1", "192.0.2.010", "192.0.2.10/24"])
def test_create_rejects_invalid_address(
    service: RadiusService, config_path: Path, reloader: AsyncMock, ipaddr: str
) -> None:
    with pytest.raises(InvalidClientAddressError):
        _run(service.create_client_tree(_create("new-ap", ipaddr)))

    assert config_path.read_text(encoding="utf-8") == CONFIG
    reloader.reload.assert_not_awaited()


@pytest.mark.parametrize(
    ("ipaddr", "owner"),
    [
        ("127.0.0.1", "localhost"),
        ("127.0.0.1/32", "localhost"),
        ("198.51.100.0/24", "office-net"),
    ],
)
def test_create_rejects_duplicate_address(
    service: RadiusService,
    config_path: Path,
    reloader: AsyncMock,
    ipaddr: str,
    owner: str,
) -> None:
    with pytest.raises(DuplicateClientAddressError) as exc_info:
        _run(service.create_client_tree(_create("new-ap", ipaddr)))

    assert owner in str(exc_info.value)
    assert config_path.read_text(encoding="utf-8") == CONFIG
    reloader.reload.assert_not_awaited()


def test_create_accepts_address_inside_existing_network(
    service: RadiusService, config_path: Path
) -> None:
    result = _run(service.create_client_tree(_create("new-ap", "198.51.100.10")))

    assert result.warnings == ()
    assert "ipaddr = 198.51.100.10" in config_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("ipaddr", "warning"),
    [("radius.example.com", "startup"), ("*", "any"), ("0.0.0.0", "any")],
)
def test_create_accepts_with_warning(
    service: RadiusService, config_path: Path, ipaddr: str, warning: str
) -> None:
    result = _run(service.create_client_tree(_create("new-ap", ipaddr)))

    assert len(result.warnings) == 1
    assert warning in result.warnings[0]
    assert f"ipaddr = {ipaddr}" in config_path.read_text(encoding="utf-8")


# ── update ───────────────────────────────────────────


def test_update_keeps_unchanged_hand_written_address(
    service: RadiusService, config_path: Path
) -> None:
    payload = ClientEditTreePayload(
        name="legacy",
        ipaddr="192.0.2",
        assignments=[AssignmentEditPayload(key="shortname", value="legacy")],
    )

    result = _run(service.update_client_tree("legacy", payload))

    assert result.warnings == ()
    content = config_path.read_text(encoding="utf-8")
    assert "ipaddr = 192.0.2 # written by hand" in content
    assert "shortname = legacy" in content


def test_update_rejects_changed_invalid_address(
    service: RadiusService, config_path: Path, reloader: AsyncMock
) -> None:
    payload = ClientEditTreePayload(name="localhost", ipaddr="999.1.1.1")

    with pytest.raises(InvalidClientAddressError):
        _run(service.update_client_tree("localhost", payload))

    assert config_path.read_text(encoding="utf-8") == CONFIG
    reloader.reload.assert_not_awaited()


def test_update_rejects_address_of_another_client(
    service: RadiusService, config_path: Path
) -> None:
    payload = ClientEditTreePayload(name="localhost", ipaddr="198.51.100.0/24")

    with pytest.raises(DuplicateClientAddressError) as exc_info:
        _run(service.update_client_tree("localhost", payload))

    assert "office-net" in str(exc_info.value)
    assert config_path.read_text(encoding="utf-8") == CONFIG


def test_update_does_not_count_the_client_itself_as_duplicate(
    service: RadiusService, config_path: Path
) -> None:
    payload = ClientEditTreePayload(name="localhost", ipaddr="127.0.0.1/32")

    _run(service.update_client_tree("localhost", payload))

    assert "ipaddr = 127.0.0.1/32" in config_path.read_text(encoding="utf-8")
