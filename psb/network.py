"""Alamat lokal untuk mode uji Wi-Fi yang dipilih melalui konfigurasi auto."""

import ipaddress
import socket


def local_address():
    try:
        addresses = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        return "127.0.0.1"
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private and not ip.is_loopback and not ip.is_link_local:
            return address
    return "127.0.0.1"


def resolve_base_url(value, port):
    return f"http://{local_address()}:{port}" if value == "auto" else value.rstrip("/")


def resolve_listen(value, port):
    if value != "auto":
        return value or f"127.0.0.1:{port}"
    address = local_address()
    loopback = f"127.0.0.1:{port}"
    return loopback if address == "127.0.0.1" else f"{loopback} {address}:{port}"
