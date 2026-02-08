"""
OS Detection Module

Detects operating system type from various device responses.
"""

from __future__ import annotations

import re
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class OSDetector:
    """Detect OS type from device fingerprints."""
    
    # OS detection patterns
    OS_PATTERNS = {
        "cisco_ios": {
            "banner": [r"Cisco IOS", r"Cisco Internetwork Operating System"],
            "prompt": [r"[Rr]outer[>#]", r"[Ss]witch[>#]", r"[Rr]\w+[>#]"],
            "command": "show version",
            "response": [r"Cisco IOS Software", r"IOS-XE"],
        },
        "cisco_nxos": {
            "banner": [r"Cisco Nexus", r"NX-OS"],
            "prompt": [r"\w+\(.*?\)#"],
            "command": "show version",
            "response": [r"NX-OS", r"Nexus"],
        },
        "junos": {
            "banner": [r"Juniper", r"Junos"],
            "prompt": [r"\w+@\w+[>#]"],
            "command": "show version",
            "response": [r"JUNOS", r"Junos"],
        },
        "arista_eos": {
            "banner": [r"Arista"],
            "prompt": [r"\w+>[#$]"],
            "command": "show version",
            "response": [r"Arista Networks", r"EOS"],
        },
        "fortios": {
            "banner": [r"FortiNet", r"FortiGate"],
            "prompt": [r"\w+ #"],
            "command": "get system status",
            "response": [r"FortiOS", r"FortiGate"],
        },
        "panos": {
            "banner": [r"Palo Alto"],
            "prompt": [r">"],
            "command": "show system info",
            "response": [r"Palo Alto Networks", r"PAN-OS"],
        },
        "ubuntu": {
            "banner": [r"Ubuntu"],
            "prompt": [r"\$", r"#"],
            "command": "cat /etc/os-release",
            "response": [r"Ubuntu", r"ubuntu"],
        },
        "centos": {
            "banner": [r"CentOS"],
            "prompt": [r"\$", r"#"],
            "command": "cat /etc/redhat-release",
            "response": [r"CentOS"],
        },
        "rhel": {
            "banner": [r"Red Hat"],
            "prompt": [r"\$", r"#"],
            "command": "cat /etc/redhat-release",
            "response": [r"Red Hat Enterprise Linux"],
        },
        "windows_server": {
            "banner": [r"Windows"],
            "prompt": [r">", r"PS>"],
            "command": "systeminfo | findstr /B /C:\"OS Name\"",
            "response": [r"Windows Server"],
        },
        "vmware_esxi": {
            "banner": [r"VMware"],
            "prompt": [r"~ #"],
            "command": "vmware -v",
            "response": [r"VMware ESXi"],
        },
    }
    
    @classmethod
    def detect_from_banner(cls, banner: str) -> Optional[str]:
        """Detect OS from SSH/telnet banner."""
        banner_lower = banner.lower()
        
        for os_type, patterns in cls.OS_PATTERNS.items():
            for pattern in patterns.get("banner", []):
                if re.search(pattern, banner, re.IGNORECASE):
                    return os_type
        
        return None
    
    @classmethod
    def detect_from_prompt(cls, prompt: str) -> Optional[str]:
        """Detect OS from CLI prompt."""
        for os_type, patterns in cls.OS_PATTERNS.items():
            for pattern in patterns.get("prompt", []):
                if re.search(pattern, prompt):
                    return os_type
        
        return None
    
    @classmethod
    def detect_from_response(cls, command: str, response: str) -> Optional[str]:
        """Detect OS from command response."""
        for os_type, patterns in cls.OS_PATTERNS.items():
            expected_cmd = patterns.get("command", "")
            if expected_cmd.lower() in command.lower():
                for pattern in patterns.get("response", []):
                    if re.search(pattern, response, re.IGNORECASE):
                        return os_type
        
        return None
    
    @classmethod
    def get_detection_command(cls, os_type: str) -> str:
        """Get the version/command used for OS detection."""
        patterns = cls.OS_PATTERNS.get(os_type, {})
        return patterns.get("command", "show version")


class VendorDetector:
    """Detect vendor from device fingerprints."""
    
    VENDOR_OUIS = {
        "00:1B:2F": "Cisco",
        "00:1E:C1": "Cisco",
        "00:23:5E": "Cisco",
        "00:25:45": "Cisco",
        "00:26:0B": "Cisco",
        "00:50:56": "VMware",
        "00:0C:29": "VMware",
        "00:05:69": "VMware",
        "00:16:3E": "Xen",
        "00:1E:67": "H3C",
        "00:24:AC": "H3C",
        "00:0F:E2": "H3C",
        "00:19:BB": "Huawei",
        "00:1A:2B": "Huawei",
        "00:E0:FC": "Huawei",
        "00:0F:12": "Juniper",
        "00:21:59": "Juniper",
        "00:22:83": "Juniper",
        "00:05:85": "Juniper",
        "00:1D:BA": "Dell",
        "00:23:AE": "Dell",
        "00:26:5F": "Dell",
        "00:21:9B": "Dell",
        "00:50:43": "Dell",
        "00:18:B9": "HP",
        "00:1F:29": "HP",
        "00:22:64": "HP",
        "00:25:B3": "HP",
        "00:10:83": "HP",
        "00:04:38": "Nortel",
        "00:0A:B8": "Nortel",
        "00:11:1A": "Nortel",
    }
    
    @classmethod
    def from_mac_address(cls, mac: str) -> Optional[str]:
        """Get vendor from MAC address OUI."""
        if not mac:
            return None
        
        # Normalize MAC
        mac_clean = mac.replace(":", "").replace("-", "").replace(".", "").upper()
        
        if len(mac_clean) < 6:
            return None
        
        oui = mac_clean[:6]
        oui_formatted = f"{oui[:2]}:{oui[2:4]}:{oui[4:6]}".upper()
        
        return cls.VENDOR_OUIS.get(oui_formatted)
    
    @classmethod
    def from_snmp_sysdescr(cls, sysdescr: str) -> Optional[str]:
        """Extract vendor from SNMP system description."""
        vendors = {
            "cisco": "Cisco",
            "juniper": "Juniper",
            "arista": "Arista",
            "hp": "HP",
            "hewlett": "HP",
            "h3c": "H3C",
            "huawei": "Huawei",
            "fortinet": "Fortinet",
            "palo": "Palo Alto",
            "checkpoint": "Check Point",
            "f5": "F5",
            "brocade": "Brocade",
            "extreme": "Extreme Networks",
            "dell": "Dell",
            "avaya": "Avaya",
            "nortel": "Nortel",
            "alcatel": "Alcatel-Lucent",
            "vmware": "VMware",
            "linux": "Linux",
            "microsoft": "Microsoft",
        }
        
        sys_lower = sysdescr.lower()
        for key, vendor in vendors.items():
            if key in sys_lower:
                return vendor
        
        return None
    
    @classmethod
    def from_ssh_banner(cls, banner: str) -> Optional[str]:
        """Extract vendor from SSH banner."""
        return cls.from_snmp_sysdescr(banner)
