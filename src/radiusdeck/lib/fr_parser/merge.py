from __future__ import annotations

from radiusdeck.lib.fr_parser.ast import Assignment, BlankLine, Block, CommentLine, Node
from radiusdeck.lib.fr_parser.utils import needs_quotes
from radiusdeck.schemas.client_edit_payload import (
    AssignmentEditPayload,
    BlockEditPayload,
    ClientEditTreePayload,
)

_RESERVED_ROOT_KEYS = frozenset({"ipaddr", "secret"})


# ── value / quoting helpers ──────────────────────────────


def _strip_outer_quotes(raw: str) -> tuple[str, str | None, bool]:
    """
    Returns (value, explicit_quote_char, was_explicit).
    """
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1], s[0], True
    return s, None, False


def _apply_value_update(existing: Assignment, raw_value: str) -> None:
    """
    Update value and quote_char:
    - explicit quotes from user  → use them
    - else preserve existing quote_char
    - else auto-quote if needs_quotes
    """
    value, explicit_q, was_explicit = _strip_outer_quotes(raw_value)
    existing.value = value

    if was_explicit:
        existing.quote_char = explicit_q
    elif existing.quote_char is not None:
        pass  # preserve
    elif needs_quotes(value):
        existing.quote_char = '"'
    else:
        existing.quote_char = None


def _new_assignment(a: AssignmentEditPayload) -> Assignment:
    value, explicit_q, was_explicit = _strip_outer_quotes(a.value)
    if was_explicit:
        quote_char = explicit_q
    else:
        quote_char = '"' if needs_quotes(value) else None
    return Assignment(key=a.key, value=value, quote_char=quote_char)


# ── index helpers ────────────────────────────────────────


def _indexed_assignments(
    children: list[Node],
    *,
    skip_keys: frozenset[str] = frozenset(),
) -> list[tuple[int, int, Assignment]]:
    """
    Returns [(position_in_children, managed_index, Assignment), ...].
    managed_index counts only non-skipped assignments (0, 1, 2, ...).
    """
    result: list[tuple[int, int, Assignment]] = []
    managed_idx = 0
    for pos, n in enumerate(children):
        if isinstance(n, Assignment):
            if n.key in skip_keys:
                continue
            result.append((pos, managed_idx, n))
            managed_idx += 1
    return result


def _indexed_blocks(children: list[Node]) -> list[tuple[int, int, Block]]:
    """
    Returns [(position_in_children, block_index, Block), ...].
    """
    result: list[tuple[int, int, Block]] = []
    block_idx = 0
    for pos, n in enumerate(children):
        if isinstance(n, Block):
            result.append((pos, block_idx, n))
            block_idx += 1
    return result


# ── insertion point helpers ──────────────────────────────


def _last_assignment_pos(children: list[Node]) -> int:
    """Index of last Assignment in children, or -1."""
    last = -1
    for i, n in enumerate(children):
        if isinstance(n, Assignment):
            last = i
    return last


def _last_block_pos(children: list[Node]) -> int:
    """Index of last Block in children, or -1."""
    last = -1
    for i, n in enumerate(children):
        if isinstance(n, Block):
            last = i
    return last


# ── duplicate key validation ─────────────────────────────


def _validate_no_duplicate_keys(block: Block) -> None:
    seen: set[str] = set()
    for n in block.children:
        if isinstance(n, Assignment):
            if n.key in seen:
                raise ValueError(
                    f"Duplicate assignment key in block '{block.kind}': {n.key}"
                )
            seen.add(n.key)


# ── required assignment helper ───────────────────────────


def _update_required(block: Block, key: str, raw_value: str) -> None:
    """Update required assignment in-place, or insert if missing."""
    if not raw_value.strip():
        raise ValueError(f"'{key}' must not be empty")

    for n in block.children:
        if isinstance(n, Assignment) and n.key == key:
            _apply_value_update(n, raw_value)
            return

    # Not found — insert after leading comments/blank lines
    insert_at = 0
    for i, n in enumerate(block.children):
        if isinstance(n, (CommentLine, BlankLine)):
            insert_at = i + 1
        else:
            break

    value, _, was_explicit = _strip_outer_quotes(raw_value)
    qc = '"' if needs_quotes(value) else None
    block.children.insert(insert_at, Assignment(key=key, value=value, quote_char=qc))


# ── merge assignments (shared logic) ────────────────────


def _merge_assignments(
    children: list[Node],
    payload_assignments: list[AssignmentEditPayload],
    *,
    prefix: str,
    skip_keys: frozenset[str] = frozenset(),
    reserved_keys: frozenset[str] = frozenset(),
) -> list[Node]:
    """
    Merge assignment payloads into children list.
    Returns new children list.

    - skip_keys: existing assignments to ignore (e.g. ipaddr/secret at root)
    - reserved_keys: keys that new/renamed assignments cannot use
    """
    # Build id → Assignment mapping (only managed assignments)
    managed = _indexed_assignments(children, skip_keys=skip_keys)
    id_to_node: dict[str, Assignment] = {}
    obj_id_to_node_id: dict[int, str] = {}
    for _pos, managed_idx, a in managed:
        node_id = f"{prefix}a:{managed_idx}"
        id_to_node[node_id] = a
        obj_id_to_node_id[id(a)] = node_id

    # Process payload
    keep_ids: set[str] = set()
    new_assignments: list[Assignment] = []

    for ap in payload_assignments:
        if ap.id is None:
            # New assignment
            if ap.key in reserved_keys:
                raise ValueError(f"'{ap.key}' is reserved; edit it via the main fields")
            new_assignments.append(_new_assignment(ap))
            continue

        # Existing assignment
        if ap.id not in id_to_node:
            raise ValueError(f"Unknown node id: {ap.id}")

        a_node = id_to_node[ap.id]
        a_node.key = ap.key
        if a_node.key in reserved_keys:
            raise ValueError(f"'{a_node.key}' is reserved; edit it via the main fields")
        _apply_value_update(a_node, ap.value)
        keep_ids.add(ap.id)

    # Remove deleted assignments (managed ones not in keep_ids)
    result: list[Node] = []
    for n in children:
        if isinstance(n, Assignment) and n.key not in skip_keys:
            nid = obj_id_to_node_id.get(id(n))
            if nid is not None and nid not in keep_ids:
                continue  # deleted
        result.append(n)

    # Insert new assignments after last Assignment, before first Block
    if new_assignments:
        insert_at = _last_assignment_pos(result) + 1
        for i, a in enumerate(new_assignments):
            result.insert(insert_at + i, a)

    return result


# ── merge blocks (shared logic) ─────────────────────────


def _merge_blocks(
    children: list[Node],
    payload_blocks: list[BlockEditPayload],
    *,
    prefix: str,
) -> list[Node]:
    """
    Merge block payloads into children list.
    Returns new children list.
    """
    # Build id → Block mapping
    existing = _indexed_blocks(children)
    id_to_node: dict[str, Block] = {}
    obj_id_to_node_id: dict[int, str] = {}
    for _pos, block_idx, b in existing:
        node_id = f"{prefix}b:{block_idx}"
        id_to_node[node_id] = b
        obj_id_to_node_id[id(b)] = node_id

    # Process payload
    keep_ids: set[str] = set()
    new_blocks: list[Block] = []

    for bp in payload_blocks:
        if bp.id is None:
            new_blocks.append(_new_block_from_payload(bp))
            continue

        if bp.id not in id_to_node:
            raise ValueError(f"Unknown node id: {bp.id}")

        b_node = id_to_node[bp.id]
        keep_ids.add(bp.id)

        # Recurse into existing block
        _merge_block_recursive(b_node, bp, prefix=f"{bp.id}/")

    # Remove deleted blocks
    result: list[Node] = []
    for n in children:
        if isinstance(n, Block):
            nid = obj_id_to_node_id.get(id(n))
            if nid is not None and nid not in keep_ids:
                continue  # deleted
        result.append(n)

    # Insert new blocks at end
    if new_blocks:
        insert_at = _last_block_pos(result) + 1
        if insert_at == 0:
            # No blocks yet — insert after last assignment
            insert_at = _last_assignment_pos(result) + 1
        for i, b in enumerate(new_blocks):
            result.insert(insert_at + i, b)

    return result


# ── recursive merge for nested blocks ───────────────────


def _merge_block_recursive(
    existing: Block,
    payload: BlockEditPayload,
    *,
    prefix: str,
) -> None:
    """Merge payload into existing block in-place (recursive, no reserved keys)."""
    existing.kind = payload.kind
    existing.name = (payload.name or "").strip() or None

    # Merge assignments (no skip, no reserved)
    existing.children = _merge_assignments(
        existing.children,
        payload.assignments,
        prefix=prefix,
    )

    # Merge sub-blocks
    existing.children = _merge_blocks(
        existing.children,
        payload.blocks,
        prefix=prefix,
    )

    _validate_no_duplicate_keys(existing)


# ── new block from payload (for id=null) ─────────────────


def _new_block_from_payload(bp: BlockEditPayload) -> Block:
    blk = Block(kind=bp.kind, name=(bp.name or "").strip() or None)

    for a in bp.assignments:
        blk.children.append(_new_assignment(a))

    for sub_bp in bp.blocks:
        blk.children.append(_new_block_from_payload(sub_bp))

    _validate_no_duplicate_keys(blk)
    return blk


# ── public API ───────────────────────────────────────────


def merge_client_block(
    existing: Block,
    payload: ClientEditTreePayload,
) -> Block:
    """
    Merge edit payload into existing ``client <name> {}`` block **in-place**.

    Preserves CommentLine / BlankLine.  Inline comments survive on kept
    assignments and are removed together with deleted assignments.

    Root rules
    ----------
    * ``ipaddr`` and ``secret`` are updated via dedicated payload fields
      and can never be deleted.
    * ``payload.assignments`` are *extra* only; using ``ipaddr``/``secret``
      as key there raises ``ValueError``.
    """
    if existing.kind != "client":
        raise ValueError("existing block must be kind='client'")
    if existing.name != payload.name:
        raise ValueError("payload.name must match existing client name")

    # 1. Update required fields
    _update_required(existing, "ipaddr", payload.ipaddr)
    if payload.secret is not None:
        _update_required(existing, "secret", payload.secret)

    # 2. Merge extra assignments (skip ipaddr/secret in id-mapping)
    existing.children = _merge_assignments(
        existing.children,
        payload.assignments,
        prefix="",
        skip_keys=_RESERVED_ROOT_KEYS,
        reserved_keys=_RESERVED_ROOT_KEYS,
    )

    # 3. Merge nested blocks
    existing.children = _merge_blocks(
        existing.children,
        payload.blocks,
        prefix="",
    )

    _validate_no_duplicate_keys(existing)
    return existing
