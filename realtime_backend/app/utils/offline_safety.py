"""Offline safety and URL validation helpers."""

from __future__ import annotations

import ipaddress
import logging
from pathlib import Path
from urllib.parse import urlparse

LOGGER = logging.getLogger(__name__)

# Localhost and common private network ranges
PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # IPv4 localhost
    ipaddress.ip_network("10.0.0.0/8"),       # Class A private
    ipaddress.ip_network("172.16.0.0/12"),    # Class B private
    ipaddress.ip_network("192.168.0.0/16"),   # Class C private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local
    ipaddress.ip_network("::1/128"),          # IPv6 localhost
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]

LOCAL_HOSTNAMES = {"localhost", "0.0.0.0", "::1", "127.0.0.1"}


def is_http_url(url: str) -> bool:
    """Return whether an endpoint has an HTTP(S) scheme and hostname."""
    try:
        parsed = urlparse(url)
        return parsed.scheme.casefold() in {"http", "https"} and bool(parsed.hostname)
    except (TypeError, ValueError):
        return False


def is_local_url(url: str) -> bool:
    """Check if a URL points to a local or private network address."""
    try:
        parsed = urlparse(url)
        if parsed.scheme.casefold() not in {"http", "https"}:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname.lower() in LOCAL_HOSTNAMES:
            return True

        # Check if it's an IP address
        try:
            ip = ipaddress.ip_address(hostname)
            return any(ip in network for network in PRIVATE_NETWORKS)
        except ValueError:
            # Not an IP address, likely a hostname.
            # In a strict local-first environment, we should be cautious about hostnames
            # unless they are explicitly known local ones.
            return False
    except Exception as exc:
        LOGGER.debug("Failed to parse URL for local check: %s", exc)
        return False


def validate_local_endpoint(url: str, provider_name: str, allow_remote: bool = False) -> None:
    """Raise ValueError if the URL is not local and remote access is not allowed."""
    if not is_http_url(url):
        raise ValueError(f"The {provider_name} endpoint must use HTTP or HTTPS: '{url}'.")
    if allow_remote:
        return

    if not is_local_url(url):
        raise ValueError(
            f"The {provider_name} endpoint '{url}' is not a local/private address. "
            "To use public internet services, you must explicitly enable 'allow_remote_access' "
            "in your configuration, though this is discouraged for privacy-first sessions."
        )


def validate_local_model_path(path: str, provider_name: str, allow_remote: bool = False) -> None:
    """Verify that a model identifier looks like a local file path if remote download is disabled."""
    if allow_remote:
        return

    # If it's a Hugging Face model ID (e.g., 'username/model') rather than an absolute path
    # and doesn't exist on disk, it's likely a remote reference.
    path_obj = Path(path)
    if not path_obj.exists() and "/" in path and not path_obj.is_absolute():
        raise ValueError(
            f"The {provider_name} model identifier '{path}' is not found locally. "
            "Offline mode is active and remote downloads are disabled. "
            "Please provide an absolute path to a local model or enable 'allow_remote_download'."
        )
