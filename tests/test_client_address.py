"""Client address rules, checked against `freeradius -XC` (FreeRADIUS 3.2.10).

The cases come from docs/backlog/address-not-validated.md in the project workspace:
values FreeRADIUS rejects, and values it silently reads differently from what the
user typed (192.0.2.010 is 192.0.2.8, 192.0.2 is 192.0.0.2, 192.0.2.10/24 is the
whole network).
"""

from __future__ import annotations

import pytest

from radiusdeck.services.client_address import (
    address_network,
    parse_client_address,
)
from radiusdeck.services.errors import InvalidClientAddressError


@pytest.mark.parametrize(
    ("value", "network"),
    [
        ("192.0.2.10", "192.0.2.10/32"),
        (" 192.0.2.10 ", "192.0.2.10/32"),
        ("198.51.100.0/24", "198.51.100.0/24"),
        ("192.0.2.10/32", "192.0.2.10/32"),
        ("2001:db8::10", "2001:db8::10/128"),
        ("2001:0DB8:0:0::10", "2001:db8::10/128"),
        ("2001:db8::/32", "2001:db8::/32"),
    ],
)
def test_addresses_and_networks_are_accepted(value: str, network: str) -> None:
    address = parse_client_address(value)

    assert address.value == value.strip()
    assert str(address.network) == network
    assert address.warning is None


@pytest.mark.parametrize(
    ("value", "network"),
    [
        ("*", "0.0.0.0/0"),
        ("0.0.0.0", "0.0.0.0/0"),
        ("0.0.0.0/0", "0.0.0.0/0"),
        ("::", "::/0"),
        ("::/0", "::/0"),
    ],
)
def test_any_address_is_accepted_with_warning(value: str, network: str) -> None:
    address = parse_client_address(value)

    assert str(address.network) == network
    assert address.warning is not None
    assert "any" in address.warning


@pytest.mark.parametrize("value", ["localhost", "radius.example.com", "nas-01"])
def test_host_names_are_accepted_with_warning(value: str) -> None:
    address = parse_client_address(value)

    assert address.network is None
    assert address.warning is not None
    assert "startup" in address.warning


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("", "required"),
        ("300.1.1.1", "not a valid IPv4"),
        ("999.1.1.1", "not a valid IPv4"),
        ("192.0.2", "not a valid IPv4"),
        ("192.0.2.010", "not a valid IPv4"),
        ("192.0.2.0/33", "not a valid IPv4"),
        ("192.0.2.0/255.255.255.0", "not a valid IPv4"),
        ("2001:db8::zz", "not a valid IPv6"),
        ("2001:db8::/129", "not a valid IPv6"),
        ("fe80::1%eth0", "zone"),
        ("-nas.example.com", "not a valid IP address, network or host name"),
        ("nas_01", "not a valid IP address, network or host name"),
        ("a" * 64 + ".example.com", "not a valid IP address, network or host name"),
    ],
)
def test_invalid_values_are_rejected(value: str, reason: str) -> None:
    with pytest.raises(InvalidClientAddressError) as exc_info:
        parse_client_address(value)

    assert reason in str(exc_info.value)


@pytest.mark.parametrize(
    ("value", "hint"),
    [
        ("192.0.2.10/24", "192.0.2.0/24"),
        ("2001:db8::10/64", "2001:db8::/64"),
    ],
)
def test_host_bits_in_prefix_are_rejected_with_hint(value: str, hint: str) -> None:
    with pytest.raises(InvalidClientAddressError) as exc_info:
        parse_client_address(value)

    message = str(exc_info.value)
    assert value.split("/")[0] in message
    assert hint in message


@pytest.mark.parametrize(
    ("value", "network"),
    [
        ("192.0.2.10", "192.0.2.10/32"),
        ("192.0.2.10/24", "192.0.2.0/24"),
        ("*", "0.0.0.0/0"),
        ("0.0.0.0", "0.0.0.0/0"),
        ("localhost", None),
        ("192.0.2", None),
    ],
)
def test_address_network_reads_existing_values_leniently(
    value: str, network: str | None
) -> None:
    """Values already in the file are compared, never rejected."""
    result = address_network(value)

    assert (None if result is None else str(result)) == network
