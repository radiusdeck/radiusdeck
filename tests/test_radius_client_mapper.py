from __future__ import annotations

from radiusdeck.lib.fr_parser import parse_clients_conf
from radiusdeck.lib.fr_parser.ops import find_client
from radiusdeck.mappers.radius_client_mapper import (
    block_to_ui_full,
    block_to_ui_summary,
)


def test_ui_mappers_omit_root_and_nested_secret_values() -> None:
    nodes = parse_clients_conf("""client nas {
    ipaddr = 192.0.2.10
    secret = root-sensitive # sensitive comment
    shortname = office
    nested {
        secret = nested-sensitive
        visible = yes
    }
}
""")
    block = find_client(nodes, "nas")
    assert block is not None

    summary = block_to_ui_summary(block)
    details = block_to_ui_full(block)
    rendered_data = repr({"summary": summary, "details": details})

    assert summary == {"name": "nas", "ipaddr": "192.0.2.10"}
    assert "root-sensitive" not in rendered_data
    assert "nested-sensitive" not in rendered_data
    assert "sensitive comment" not in rendered_data
    assert "office" in rendered_data
    assert "yes" in rendered_data
