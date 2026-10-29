from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.schemas.client_payload_tree import ClientCreateTreePayload
from radiusdeck.services.errors import ClientAlreadyExistsError
from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.reload_models import ReloadResult

CONFIG = """client localhost {
    ipaddr = 127.0.0.1 # stock client
    secret = testing123
    shortname = localhost
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


def test_create_client_tree_adds_new_client(
    service: RadiusService, config_path: Path, reloader: AsyncMock
) -> None:
    payload = ClientCreateTreePayload(
        name="office-ap-01", ipaddr="192.0.2.10", secret="example-secret"
    )

    result = _run(service.create_client_tree(payload))

    assert result.changed is True
    content = config_path.read_text(encoding="utf-8")
    assert content.startswith(CONFIG)
    assert "client office-ap-01 {" in content
    reloader.reload.assert_awaited_once()


def test_create_client_tree_rejects_existing_name(
    service: RadiusService, config_path: Path, reloader: AsyncMock
) -> None:
    payload = ClientCreateTreePayload(
        name="localhost", ipaddr="198.51.100.31", secret="example-secret"
    )

    with pytest.raises(ClientAlreadyExistsError) as exc_info:
        _run(service.create_client_tree(payload))

    assert exc_info.value.name == "localhost"
    assert config_path.read_text(encoding="utf-8") == CONFIG
    reloader.reload.assert_not_awaited()
