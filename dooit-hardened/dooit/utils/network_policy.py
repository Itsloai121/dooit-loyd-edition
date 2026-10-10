"""Hardcoded Python IP-network deny policy. Not an OS security sandbox."""
import socket
import sys

_installed = False
_IP_FAMILIES = {socket.AF_INET, socket.AF_INET6}
_DNS_EVENTS = {
    "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
    "socket.getnameinfo",
}


def _deny_ip_network(event, args):
    if event == "socket.__new__" and args[1] in _IP_FAMILIES:
        raise PermissionError("Dooit offline edition: IPv4/IPv6 sockets are disabled")
    if event in {"socket.bind", "socket.connect"}:
        if args[0].family in _IP_FAMILIES:
            raise PermissionError("Dooit offline edition: IP networking is disabled")
    if event in _DNS_EVENTS:
        raise PermissionError("Dooit offline edition: DNS lookups are disabled")


def install_network_policy():
    """Install once, with no CLI switch or environment-variable override."""
    global _installed
    if not _installed:
        sys.addaudithook(_deny_ip_network)
        _installed = True
