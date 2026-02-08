from __future__ import annotations

from typing import Dict

from autodetector.collector.ssh_collector import SshCollector
from autodetector.collector.telnet_collector import TelnetCollector


def detect_os(host: str, transport: str, username: str, password: str) -> Dict[str, str]:
    commands = {
        "uname": "uname -a",
        "osrelease": "cat /etc/os-release",
        "cisco": "show version",
        "juniper": "show version | no-more",
        "mikrotik": "/system resource print",
        "forti": "get system status",
        "palo": "show system info",
        "esxi": "vmware -v",
    }

    if transport == "telnet":
        collector = TelnetCollector(connect_timeout_sec=8, command_timeout_sec=12)
        out, err = collector.run_commands(host, username, password, commands)
    else:
        collector = SshCollector(connect_timeout_sec=8, command_timeout_sec=12)
        out, err = collector.run_commands(host, username, password, commands)

    blob = "\n".join((out.get(k) or "") for k in commands.keys()).lower()

    guess = "unknown"
    if "cisco ios" in blob or "ios xe" in blob or "cisco nx-os" in blob:
        guess = "cisco_ios"
    elif "junos" in blob or "juniper" in blob:
        guess = "junos"
    elif "mikrotik" in blob or "routeros" in blob:
        guess = "mikrotik"
    elif "fortigate" in blob or "fortios" in blob:
        guess = "fortios"
    elif "palo alto" in blob or "pan-os" in blob:
        guess = "panos"
    elif "vmware esxi" in blob or "esxi" in blob:
        guess = "esxi"
    elif "ubuntu" in blob:
        guess = "ubuntu"
    elif "debian" in blob:
        guess = "debian"
    elif "centos" in blob:
        guess = "centos"
    elif "red hat" in blob or "rhel" in blob:
        guess = "rhel"
    elif "freebsd" in blob:
        guess = "freebsd"

    return {"host": host, "transport": transport, "guess": guess, "errors": str(err)}
