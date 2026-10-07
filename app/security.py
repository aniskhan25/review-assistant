"""Defense in depth; OS/container network isolation remains the production boundary."""

import ipaddress
import socket
import sys

from app.decision import offline_environment


def install_network_guard():
    offline_environment()

    def guard(event, args):
        if event == "socket.getaddrinfo":
            host = args[0]
            if host not in {"127.0.0.1", "::1", None}:
                raise PermissionError("External DNS disabled")
        if event in {"socket.connect", "socket.sendto"}:
            sock, address = args[0], args[-1]
            if sock.family in {socket.AF_INET, socket.AF_INET6}:
                try:
                    allowed = ipaddress.ip_address(address[0]).is_loopback
                except ValueError:
                    allowed = False
                if not allowed:
                    raise PermissionError("External network disabled")
    sys.addaudithook(guard)
