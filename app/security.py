"""Defense in depth; OS/container network isolation remains the production boundary."""

import ipaddress
import socket
import sys
from contextlib import contextmanager
from contextvars import ContextVar

from app.decision import offline_environment

_aitta_access = ContextVar('aitta_network_access', default=None)


@contextmanager
def aitta_network_access():
    """Permit only verified HTTPS to Aitta during an explicit drafting request."""
    access = {'addresses': set()}
    token = _aitta_access.set(access)
    try:
        results = socket.getaddrinfo('aitta-api.csc.fi', 443, type=socket.SOCK_STREAM)
        access['addresses'] = {item[4][0] for item in results
                               if ipaddress.ip_address(item[4][0]).is_global}
        if not access['addresses']:
            raise PermissionError('Aitta has no permitted address')
        yield
    finally:
        _aitta_access.reset(token)


def install_network_guard():
    offline_environment()

    def guard(event, args):
        if event == "socket.getaddrinfo":
            host = args[0]
            aitta = _aitta_access.get() is not None and host == 'aitta-api.csc.fi' and args[1] == 443
            if host not in {"127.0.0.1", "::1", None} and not aitta:
                raise PermissionError("External DNS disabled")
        if event in {"socket.connect", "socket.sendto"}:
            sock, address = args[0], args[-1]
            if sock.family in {socket.AF_INET, socket.AF_INET6}:
                try:
                    allowed = ipaddress.ip_address(address[0]).is_loopback
                except ValueError:
                    allowed = False
                access = _aitta_access.get()
                allowed = allowed or bool(access and address[0] in access['addresses'] and address[1] == 443)
                if not allowed:
                    raise PermissionError("External network disabled")
    sys.addaudithook(guard)
