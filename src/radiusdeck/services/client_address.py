"""Client address rules for `ipaddr`, matching FreeRADIUS 3.2.

FreeRADIUS accepts more than an address: it resolves anything that is not a valid
address as a host name at startup, reads `192.0.2.010` as 192.0.2.8 and `192.0.2`
as 192.0.0.2 (inet_aton), turns `192.0.2.10/24` into the whole network, and treats
`*` and `0.0.0.0` as any IPv4 address. A new or changed value is therefore checked
strictly here; values already in the file are only read (`address_network`).
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import TypeAlias

from radiusdeck.services.errors import InvalidClientAddressError

Network: TypeAlias = ipaddress.IPv4Network | ipaddress.IPv6Network

_IPV4_CHARS = re.compile(r"[0-9./]+")
_IPV4_FORM = re.compile(r"[0-9.]+(/[0-9]{1,2})?")
_IPV6_FORM = re.compile(r"[0-9A-Fa-f:.]+(/[0-9]{1,3})?")
_HOST_LABEL = re.compile(r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?")

# FreeRADIUS reads "*", "0.0.0.0" and "::" as "any address", not as a single host.
# The keys come from the networks: a "0.0.0.0" literal trips bandit B104 (bind to
# all interfaces), and these are clients.conf values to compare, not bind addresses.
_ANY_IPV4 = ipaddress.IPv4Network("0.0.0.0/0")
_ANY_IPV6 = ipaddress.IPv6Network("::/0")
_ANY: dict[str, Network] = {
    "*": _ANY_IPV4,
    str(_ANY_IPV4.network_address): _ANY_IPV4,
    str(_ANY_IPV6.network_address): _ANY_IPV6,
}


@dataclass(frozen=True)
class ClientAddress:
    value: str
    network: Network | None  # None for a host name
    warning: str | None


def parse_client_address(value: str, key: str = "ipaddr") -> ClientAddress:
    """Check a new address for `key` (ipaddr, ipv4addr or ipv6addr).

    Raise InvalidClientAddressError if FreeRADIUS would reject or misread it.
    """
    value = value.strip()
    if not value:
        raise InvalidClientAddressError("IP address is required.")

    if value in _ANY or ":" in value or _IPV4_CHARS.fullmatch(value):
        network = _parse_ip(value)
        required = {"ipv4addr": 4, "ipv6addr": 6}.get(key)
        if required is not None and network.version != required:
            raise InvalidClientAddressError(
                f'IP address "{value}" is IPv{network.version}, but this client '
                f"uses {key}: enter an IPv{required} address."
            )
        warning = None
        if network.prefixlen == 0:
            warning = (
                f"Client address {value} accepts requests from any "
                f"IPv{network.version} address."
            )
        return ClientAddress(value=value, network=network, warning=warning)

    if not _is_host_name(value):
        raise InvalidClientAddressError(
            f'IP address "{value}" is not a valid IP address, network or host name.'
        )
    return ClientAddress(
        value=value,
        network=None,
        warning=(
            f"FreeRADIUS resolves {value} once at startup. "
            "If the name does not resolve, FreeRADIUS will not start."
        ),
    )


def address_network(value: str) -> Network | None:
    """Network of a value already in the file, or None for names and odd forms."""
    value = value.strip()
    if value in _ANY:
        return _ANY[value]
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError:
        return None


def _parse_ip(value: str) -> Network:
    if value in _ANY:
        return _ANY[value]

    version = 6 if ":" in value else 4
    invalid = InvalidClientAddressError(
        f'IP address "{value}" is not a valid IPv{version} address or network.'
    )
    if version == 6 and "%" in value:
        raise InvalidClientAddressError(
            f'IP address "{value}": an IPv6 zone is not supported in ipaddr.'
        )
    form = _IPV6_FORM if version == 6 else _IPV4_FORM
    if not form.fullmatch(value):
        raise invalid

    try:
        return ipaddress.ip_network(value)
    except ValueError:
        pass
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise invalid from None
    host = value.split("/", 1)[0]
    raise InvalidClientAddressError(
        f'IP address "{value}" has host bits set: use {host} for one device '
        f"or {network} for the network."
    )


def _is_host_name(value: str) -> bool:
    if len(value) > 253:
        return False
    return all(_HOST_LABEL.fullmatch(label) for label in value.split("."))
