"""
The IP address of the client of a request, also behind a reverse proxy.

Only when the direct peer is a trusted proxy (`TRUSTED_PROXIES`) is X-Forwarded-For used: the
right-most address that isn't a trusted proxy is the client. Otherwise the header is ignored,
so a client can't pretend to be someone else by sending it.
"""

import ipaddress
from functools import cache

from starlette.requests import Request

from bracket.config import config

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


@cache
def parse_networks(value: str) -> tuple[IPNetwork, ...]:
    return tuple(
        ipaddress.ip_network(part.strip(), strict=False)
        for part in value.split(",")
        if part.strip()
    )


def is_trusted(address: str, networks: tuple[IPNetwork, ...]) -> bool:
    try:
        ip = ipaddress.ip_address(address.strip())
    except ValueError:
        return False
    return any(ip in network for network in networks)


def client_ip_from(peer: str | None, forwarded_for: str | None, trusted_proxies: str) -> str:
    networks = parse_networks(trusted_proxies)
    if peer is None:
        return "unknown"
    if forwarded_for is None or not is_trusted(peer, networks):
        return peer
    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    for hop in reversed(hops):
        if not is_trusted(hop, networks):
            return hop
    return hops[0] if hops else peer


def client_ip(request: Request) -> str:
    return client_ip_from(
        request.client.host if request.client is not None else None,
        request.headers.get("x-forwarded-for"),
        config.trusted_proxies,
    )
