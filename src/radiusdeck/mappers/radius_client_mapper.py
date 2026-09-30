from typing import Any

from radiusdeck.lib.fr_parser.ast import Assignment, Block, CommentLine

ClientFull = dict[str, Any]
ClientDict = dict[str, str]


def block_to_flat(block: Block) -> ClientDict:
    data = {ch.key: ch.value for ch in block.children if isinstance(ch, Assignment)}
    data["name"] = block.name or ""
    return data


def block_to_ui_summary(block: Block) -> ClientDict:
    data = block_to_flat(block)
    return {
        "name": data.get("name", ""),
        "ipaddr": data.get("ipaddr", ""),
    }


def block_to_ui_full(block: Block, *, is_root: bool = True) -> ClientFull:
    assignments: list[dict[str, Any]] = []
    blocks = []
    comments = []

    for child in block.children:
        if isinstance(child, Assignment):
            is_secret = child.key.lower() == "secret"
            assignment: dict[str, Any] = {
                "key": child.key,
                "comment": None if is_secret else child.inline_comment,
                "is_secret": is_secret,
                "is_client_secret": is_root and is_secret,
            }
            if not is_secret:
                assignment["value"] = child.value
            assignments.append(assignment)
        elif isinstance(child, Block):
            sub = block_to_ui_full(child, is_root=False)
            sub["kind"] = child.kind
            blocks.append(sub)
        elif isinstance(child, CommentLine):
            comments.append(child.text)

    return {
        "name": block.name,
        "assignments": assignments,
        "blocks": blocks,
        "comments": comments,
    }


def block_to_full(block: Block) -> ClientFull:
    assignments = []
    blocks = []
    comments = []

    for child in block.children:
        if isinstance(child, Assignment):
            assignments.append(
                {
                    "key": child.key,
                    "value": child.value,
                    "comment": child.inline_comment,
                }
            )
        elif isinstance(child, Block):
            sub = block_to_full(child)
            sub["kind"] = child.kind
            blocks.append(sub)
        elif isinstance(child, CommentLine):
            comments.append(child.text)

    return {
        "name": block.name,
        "assignments": assignments,
        "blocks": blocks,
        "comments": comments,
    }
