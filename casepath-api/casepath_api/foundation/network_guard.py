from __future__ import annotations

import socket
from typing import Any


_INSTALLED = False
_DENIED_ATTEMPTS = 0
_ORIGINAL_CONNECT = socket.socket.connect
_ORIGINAL_CREATE_CONNECTION = socket.create_connection


def _loopback(address: Any) -> bool:
    if isinstance(address, str):
        return True  # Unix-domain socket path.
    if not isinstance(address, tuple) or not address:
        return False
    return str(address[0]).lower() in {"127.0.0.1", "::1", "localhost"}


def install_external_network_guard() -> None:
    """Deny outbound non-loopback sockets in the provider-free proof process."""

    global _INSTALLED
    if _INSTALLED:
        return

    def guarded_connect(sock: socket.socket, address: Any) -> Any:
        global _DENIED_ATTEMPTS
        if sock.family in {socket.AF_INET, socket.AF_INET6} and not _loopback(address):
            _DENIED_ATTEMPTS += 1
            raise RuntimeError(
                f"external network denied by CasePath foundation: {address!r}"
            )
        return _ORIGINAL_CONNECT(sock, address)

    def guarded_create_connection(
        address: Any, *args: Any, **kwargs: Any
    ) -> socket.socket:
        global _DENIED_ATTEMPTS
        if not _loopback(address):
            _DENIED_ATTEMPTS += 1
            raise RuntimeError(
                f"external network denied by CasePath foundation: {address!r}"
            )
        return _ORIGINAL_CREATE_CONNECTION(address, *args, **kwargs)

    setattr(socket.socket, "connect", guarded_connect)
    setattr(socket, "create_connection", guarded_create_connection)
    _INSTALLED = True


def network_guard_status() -> dict[str, int | bool]:
    return {
        "external_network_denied": _INSTALLED,
        "denied_attempts": _DENIED_ATTEMPTS,
    }
