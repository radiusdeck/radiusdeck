# src/radiusdeck/services/radius_service.py
import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, TypeAlias

from radiusdeck.lib.fr_parser import (
    iter_blocks,
    parse_clients_conf,
    render_clients_conf,
    upsert_client,
)
from radiusdeck.lib.fr_parser.ast import AstNodes, Block
from radiusdeck.lib.fr_parser.merge import merge_client_block
from radiusdeck.lib.fr_parser.ops import (
    find_client,
    get_assignment,
    upsert_client_block,
)
from radiusdeck.mappers.client_edit_mapper import client_block_to_edit_model
from radiusdeck.mappers.client_tree_mapper import client_block_from_payload
from radiusdeck.mappers.radius_client_mapper import (
    block_to_flat,
    block_to_full,
    block_to_ui_full,
    block_to_ui_summary,
)
from radiusdeck.repositories.clients_conf_store import (
    ClientsConfSnapshot,
    ClientsConfStore,
)
from radiusdeck.schemas.client import ClientCreate, ClientUpdate
from radiusdeck.schemas.client_edit_payload import ClientEditTreePayload
from radiusdeck.schemas.client_payload_tree import ClientCreateTreePayload
from radiusdeck.services.backup_models import BackupEntry
from radiusdeck.services.errors import (
    ClientNotFoundError,
    DuplicateKeyError,
    InvalidClientUpsertError,
    InvalidNodeIdError,
    MergeClientError,
)
from radiusdeck.services.ports import BackupPort, ReloadPort
from radiusdeck.services.reload_models import ReloadResult

logger = logging.getLogger(__name__)

ClientDict: TypeAlias = dict[str, str]
ClientList: TypeAlias = list[ClientDict]
ClientFull: TypeAlias = dict[str, Any]


@dataclass(frozen=True)
class UpsertResult:
    client: ClientDict
    reload_result: ReloadResult
    changed: bool
    backup: BackupEntry | None


@dataclass(frozen=True)
class DeleteResult:
    reload_result: ReloadResult
    changed: bool
    backup: BackupEntry | None


@dataclass(frozen=True)
class _PersistenceResult:
    reload_result: ReloadResult
    changed: bool
    backup: BackupEntry | None


class RadiusService:
    def __init__(
        self,
        store: ClientsConfStore,
        reloader: ReloadPort,
        backup: BackupPort | None = None,
    ) -> None:
        self._store = store
        self._reloader = reloader
        self._backup = backup

    async def _notify_reload(self) -> ReloadResult:
        """Trigger config reload via sidecar. Never raises."""
        return await self._reloader.reload()

    def _log_audit(
        self,
        *,
        actor_username: str | None,
        action: str,
        client_name: str,
    ) -> None:
        actor = actor_username or "unknown"
        logger.info(
            "Audit clients.conf mutation: actor=%s action=%s client=%s",
            actor,
            action,
            client_name,
        )

    async def _load_nodes(self) -> AstNodes:
        return await self._store.load()

    async def _persist_mutation(
        self,
        *,
        snapshot: ClientsConfSnapshot,
        original_nodes: AstNodes,
        proposed_nodes: AstNodes,
        actor_username: str | None,
        reason: str,
        action: str,
        client_name: str,
    ) -> _PersistenceResult:
        if proposed_nodes == original_nodes:
            return _PersistenceResult(
                reload_result=ReloadResult.skipped("configuration unchanged"),
                changed=False,
                backup=None,
            )

        proposed_content = render_clients_conf(proposed_nodes)
        parse_clients_conf(proposed_content)
        backup_result = None
        if self._backup is not None:
            backup_result = await self._backup.create_pre_change_backup(
                actor=actor_username or "unknown",
                reason=reason,
                client_name=client_name,
                current_content=snapshot.content,
                proposed_content=proposed_content,
            )

        await self._store.save_content(proposed_content)
        reload_result = await self._notify_reload()
        self._log_audit(
            actor_username=actor_username,
            action=action,
            client_name=client_name,
        )
        return _PersistenceResult(
            reload_result=reload_result,
            changed=True,
            backup=backup_result.backup if backup_result is not None else None,
        )

    async def get_all_clients(self) -> ClientList:
        logger.info("get_all_clients")
        async with self._store.locked():
            nodes = await self._load_nodes()
            return [block_to_flat(b) for b in iter_blocks(nodes, "client")]

    async def get_all_clients_for_ui(self) -> ClientList:
        async with self._store.locked():
            nodes = await self._load_nodes()
            return [block_to_ui_summary(b) for b in iter_blocks(nodes, "client")]

    async def get_client(self, name: str) -> ClientDict:
        logger.info("get_client, name: %s", name)
        async with self._store.locked():
            nodes = await self._load_nodes()
            block = find_client(nodes, name)
            if not block:
                raise ClientNotFoundError(name)
            return block_to_flat(block)

    async def get_client_full_for_ui(self, name: str) -> ClientFull:
        async with self._store.locked():
            nodes = await self._load_nodes()
            block = find_client(nodes, name)
            if not block:
                raise ClientNotFoundError(name)

            full = block_to_ui_full(block)
            full["kind"] = block.kind  # "client"
            return full

    async def get_client_full(self, name: str) -> ClientFull:
        async with self._store.locked():
            nodes = await self._load_nodes()
            block = find_client(nodes, name)
            if block is None:
                raise ClientNotFoundError(name)

            full = block_to_full(block)
            full["kind"] = block.kind
            return full

    async def get_client_secret(
        self, name: str, *, actor_username: str | None = None
    ) -> str:
        async with self._store.locked():
            nodes = await self._load_nodes()
            block = find_client(nodes, name)
            if block is None:
                raise ClientNotFoundError(name)
            secret = get_assignment(block, "secret")
            if secret is None:
                raise ValueError("Client must have a secret assignment")

            logger.info(
                "Audit client secret access: actor=%s "
                "action=reveal_client_secret client=%s",
                actor_username or "unknown",
                name,
            )
            return secret.value

    async def create_or_update_client(
        self,
        name: str,
        data: ClientCreate | ClientUpdate,
        *,
        actor_username: str | None = None,
    ) -> UpsertResult:
        params = data.model_dump(exclude={"name", "extra_params"}, exclude_unset=True)
        if data.extra_params:
            params.update(data.extra_params)

        async with self._store.locked():
            snapshot = await self._store.load_snapshot()
            nodes = snapshot.nodes
            original_nodes = deepcopy(nodes)
            existing_block = find_client(nodes, name)
            action = "update" if existing_block is not None else "create"
            if existing_block is None and (
                params.get("ipaddr") is None or params.get("secret") is None
            ):
                raise InvalidClientUpsertError(
                    "Creating a client with PUT requires ipaddr and secret"
                )

            updated_block = upsert_client(nodes, name, params)
            persisted = await self._persist_mutation(
                snapshot=snapshot,
                original_nodes=original_nodes,
                proposed_nodes=nodes,
                actor_username=actor_username,
                reason=f"{action}_client",
                action=action,
                client_name=name,
            )
            return UpsertResult(
                client=block_to_flat(updated_block),
                reload_result=persisted.reload_result,
                changed=persisted.changed,
                backup=persisted.backup,
            )

    async def create_or_update_client_tree(
        self,
        payload: ClientCreateTreePayload,
        *,
        actor_username: str | None = None,
    ) -> UpsertResult:
        client_block = client_block_from_payload(payload)

        async with self._store.locked():
            snapshot = await self._store.load_snapshot()
            nodes = snapshot.nodes
            original_nodes = deepcopy(nodes)
            action = (
                "update" if find_client(nodes, payload.name) is not None else "create"
            )
            updated_block = upsert_client_block(nodes, client_block)
            persisted = await self._persist_mutation(
                snapshot=snapshot,
                original_nodes=original_nodes,
                proposed_nodes=nodes,
                actor_username=actor_username,
                reason=f"{action}_client",
                action=action,
                client_name=payload.name,
            )
            return UpsertResult(
                client=block_to_flat(updated_block),
                reload_result=persisted.reload_result,
                changed=persisted.changed,
                backup=persisted.backup,
            )

    @staticmethod
    def _remove_client_blocks(nodes: AstNodes, name: str) -> int:
        removed = 0
        i = 0
        while i < len(nodes):
            n = nodes[i]

            if isinstance(n, Block) and n.kind == "client" and n.name == name:
                del nodes[i]
                removed += 1
                continue

            if isinstance(n, Block) and n.children:
                removed += RadiusService._remove_client_blocks(n.children, name)

            i += 1

        return removed

    async def delete_client(
        self, name: str, *, actor_username: str | None = None
    ) -> DeleteResult:
        logger.info("delete_client, name: %s", name)
        async with self._store.locked():
            snapshot = await self._store.load_snapshot()
            nodes = snapshot.nodes
            original_nodes = deepcopy(nodes)
            removed = self._remove_client_blocks(nodes, name)
            if removed == 0:
                raise ClientNotFoundError(name)

            persisted = await self._persist_mutation(
                snapshot=snapshot,
                original_nodes=original_nodes,
                proposed_nodes=nodes,
                actor_username=actor_username,
                reason="delete_client",
                action="delete",
                client_name=name,
            )
            return DeleteResult(
                reload_result=persisted.reload_result,
                changed=persisted.changed,
                backup=persisted.backup,
            )

    async def update_client_tree(
        self,
        name: str,
        payload: ClientEditTreePayload,
        *,
        actor_username: str | None = None,
    ) -> UpsertResult:
        if payload.name != name:
            raise MergeClientError("Payload name does not match URL client name")

        async with self._store.locked():
            snapshot = await self._store.load_snapshot()
            nodes = snapshot.nodes
            original_nodes = deepcopy(nodes)
            block = find_client(nodes, name)
            if block is None:
                raise ClientNotFoundError(name)

            try:
                merge_client_block(block, payload)
            except ValueError as e:
                msg = str(e)
                if msg.startswith("Unknown node id:"):
                    raise InvalidNodeIdError(msg) from e
                if msg.startswith("Duplicate assignment key"):
                    raise DuplicateKeyError(msg) from e
                raise MergeClientError(msg) from e

            persisted = await self._persist_mutation(
                snapshot=snapshot,
                original_nodes=original_nodes,
                proposed_nodes=nodes,
                actor_username=actor_username,
                reason="update_client",
                action="update",
                client_name=name,
            )
            return UpsertResult(
                client=block_to_flat(block),
                reload_result=persisted.reload_result,
                changed=persisted.changed,
                backup=persisted.backup,
            )

    async def get_client_edit_model(self, name: str) -> dict[str, Any]:
        async with self._store.locked():
            nodes = await self._store.load()
            block = find_client(nodes, name)
            if block is None:
                raise ClientNotFoundError(name)
            return client_block_to_edit_model(block)
