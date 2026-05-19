from __future__ import annotations

import ipaddress


def parse_allowed_domains(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def is_domain_allowed(host: str | None, allowed_domains: set[str]) -> bool:
    if not allowed_domains:
        return True
    if not host:
        return False
    normalized_host = host.lower().strip(".")
    for allowed_domain in allowed_domains:
        normalized_allowed = allowed_domain.lower().strip(".")
        if normalized_host == normalized_allowed or normalized_host.endswith(f".{normalized_allowed}"):
            return True
    return False


def blocked_ip_reason(host: str | None, *, resolved_ips: list[str] | None = None) -> str | None:
    candidates = list(resolved_ips or [])
    if host:
        candidates.append(host.strip("[]"))

    for candidate in candidates:
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue

        if address.is_loopback:
            return "loopback_blocked"
        if address.is_link_local:
            return "link_local_blocked"
        if address.is_multicast:
            return "multicast_blocked"
        if address.is_unspecified:
            return "unspecified_ip_blocked"
        if address.is_private:
            return "private_ip_blocked"
    return None
