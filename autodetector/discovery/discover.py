from __future__ import annotations

import ipaddress
import socket
from typing import Dict, List


def _tcp_open(host: str, port: int, timeout_sec: float) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_sec)
    try:
        r = s.connect_ex((host, int(port)))
        return r == 0
    except Exception:  # noqa: BLE001
        return False
    finally:
        try:
            s.close()
        except Exception:  # noqa: BLE001
            pass


def discover_hosts(cidr: str, ports: List[int], timeout_sec: float = 0.4, limit: int = 4096) -> List[Dict[str, object]]:
    net = ipaddress.ip_network(cidr, strict=False)
    found: List[Dict[str, object]] = []

    count = 0
    for ip in net.hosts():
        if count >= limit:
            break
        count += 1

        host = str(ip)
        for p in ports:
            if _tcp_open(host, int(p), timeout_sec=timeout_sec):
                found.append({"host": host, "port": int(p)})

    return found
