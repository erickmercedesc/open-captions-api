from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from capservice.errors import SsrfError

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.google.internal.",
}

_BLOCKED_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
)

_BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".lan", ".home", ".corp")


def validate_public_https_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise SsrfError("A valid HTTPS URL is required.")

    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise SsrfError("Only HTTPS URLs are allowed.")
    if parsed.username or parsed.password:
        raise SsrfError("URLs with credentials are not allowed.")
    if not parsed.hostname:
        raise SsrfError("The URL host is missing.")
    if parsed.fragment:
        raise SsrfError("The URL is not allowed.")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in _BLOCKED_HOSTS:
        raise SsrfError("The URL host is not allowed.")
    if any(hostname.endswith(suffix) for suffix in _BLOCKED_SUFFIXES):
        raise SsrfError("The URL host is not allowed.")

    _assert_public_hostname(hostname)
    return url.strip()


def _assert_public_hostname(hostname: str) -> None:
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ips = _resolve_hostname(hostname)
    else:
        ips = [ip]

    if not ips:
        raise SsrfError("The URL could not be resolved.")
    for ip in ips:
        if _is_blocked_ip(ip):
            raise SsrfError("The URL host is not allowed.")


def _resolve_hostname(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SsrfError("The URL could not be resolved.") from exc

    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        ips.append(ipaddress.ip_address(info[4][0]))
    return ips


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_blocked_ip(ip.ipv4_mapped)
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_reserved or ip.is_unspecified or getattr(ip, "is_site_local", False):
        return True
    return any(ip in network for network in _BLOCKED_NETWORKS)
