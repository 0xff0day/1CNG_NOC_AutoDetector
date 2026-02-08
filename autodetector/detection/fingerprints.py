from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Fingerprint:
    name: str
    patterns: List[str]
    confidence_threshold: float = 0.7


@dataclass(frozen=True)
class FingerprintResult:
    os_guess: str
    confidence: float
    method: str


# Comprehensive OS fingerprints for CLI banner/command responses
FINGERPRINTS: Dict[str, Fingerprint] = {
    # Network devices
    "cisco_ios": Fingerprint(
        name="cisco_ios",
        patterns=[
            r"cisco ios",
            r"ios-xe",
            r"cisco internetwork operating system",
            r"\bIOS\b.*\bCisco\b",
            r"router#|switch#",
        ],
        confidence_threshold=0.8,
    ),
    "cisco_nxos": Fingerprint(
        name="cisco_nxos",
        patterns=[
            r"cisco nx-os",
            r"nx-os",
            r"nexus",
            r"\bNXOS\b",
        ],
        confidence_threshold=0.8,
    ),
    "junos": Fingerprint(
        name="junos",
        patterns=[
            r"junos",
            r"juniper",
            r"\bjunos\b",
            r"\bjuniper networks\b",
            r"%\s*\bjuniper\b",
        ],
        confidence_threshold=0.8,
    ),
    "panos": Fingerprint(
        name="panos",
        patterns=[
            r"palo alto",
            r"pan-os",
            r"panos",
            r"\bPA-\d+\b",
        ],
        confidence_threshold=0.8,
    ),
    "fortios": Fingerprint(
        name="fortios",
        patterns=[
            r"fortinet",
            r"fortios",
            r"fortigate",
            r"\bFGT\b",
        ],
        confidence_threshold=0.8,
    ),
    "mikrotik": Fingerprint(
        name="mikrotik",
        patterns=[
            r"mikrotik",
            r"routeros",
            r"\bRouterOS\b",
        ],
        confidence_threshold=0.8,
    ),
    "arista_eos": Fingerprint(
        name="arista_eos",
        patterns=[
            r"arista",
            r"eos",
            r"\bArista\b.*\bEOS\b",
        ],
        confidence_threshold=0.8,
    ),
    "huawei_vrp": Fingerprint(
        name="huawei_vrp",
        patterns=[
            r"huawei",
            r"vrp",
            r"\bVRP\b",
            r"\bCE\d+\b",
        ],
        confidence_threshold=0.7,
    ),
    "edgeos": Fingerprint(
        name="edgeos",
        patterns=[
            r"ubiquiti",
            r"edgeos",
            r"edgeswitch",
        ],
        confidence_threshold=0.7,
    ),
    "pfsense": Fingerprint(
        name="pfsense",
        patterns=[
            r"pfsense",
            r"\bpfSense\b",
            r"\bOPNsense\b",
        ],
        confidence_threshold=0.8,
    ),
    # Server OS
    "ubuntu": Fingerprint(
        name="ubuntu",
        patterns=[
            r"ubuntu",
            r"\bUbuntu\b",
            r"\.ubuntu\.",
        ],
        confidence_threshold=0.7,
    ),
    "debian": Fingerprint(
        name="debian",
        patterns=[
            r"debian",
            r"\bDebian\b",
        ],
        confidence_threshold=0.7,
    ),
    "rhel": Fingerprint(
        name="rhel",
        patterns=[
            r"red hat enterprise",
            r"\bRHEL\b",
            r"\bRed Hat\b",
        ],
        confidence_threshold=0.7,
    ),
    "centos": Fingerprint(
        name="centos",
        patterns=[
            r"centos",
            r"\bCentOS\b",
        ],
        confidence_threshold=0.7,
    ),
    "rocky": Fingerprint(
        name="rocky",
        patterns=[
            r"rocky linux",
            r"\bRocky\b",
        ],
        confidence_threshold=0.7,
    ),
    "alma": Fingerprint(
        name="alma",
        patterns=[
            r"almalinux",
            r"\bAlmaLinux\b",
        ],
        confidence_threshold=0.7,
    ),
    "suse": Fingerprint(
        name="suse",
        patterns=[
            r"suse",
            r"sles",
            r"opensuse",
        ],
        confidence_threshold=0.7,
    ),
    "amazon_linux": Fingerprint(
        name="amazon_linux",
        patterns=[
            r"amazon linux",
            r"\bamzn\b",
        ],
        confidence_threshold=0.7,
    ),
    "freebsd": Fingerprint(
        name="freebsd",
        patterns=[
            r"freebsd",
            r"\bFreeBSD\b",
        ],
        confidence_threshold=0.8,
    ),
    "windows_server": Fingerprint(
        name="windows_server",
        patterns=[
            r"windows server",
            r"\bWindows\b.*\bServer\b",
            r"\bWin\d+\b",
            r"microsoft windows",
        ],
        confidence_threshold=0.8,
    ),
    # Hypervisors
    "vmware_esxi": Fingerprint(
        name="vmware_esxi",
        patterns=[
            r"vmware",
            r"esxi",
            r"\bESXi\b",
            r"vsphere",
        ],
        confidence_threshold=0.8,
    ),
    "proxmox": Fingerprint(
        name="proxmox",
        patterns=[
            r"proxmox",
            r"pve",
            r"\bProxmox\b",
        ],
        confidence_threshold=0.8,
    ),
    "xcpng": Fingerprint(
        name="xcpng",
        patterns=[
            r"xcp-ng",
            r"xenserver",
            r"xcpng",
        ],
        confidence_threshold=0.7,
    ),
}


def classify_os(text: str) -> List[FingerprintResult]:
    """Classify OS from banner/command output text."""
    text_lower = text.lower()
    results: List[FingerprintResult] = []
    
    for os_name, fp in FINGERPRINTS.items():
        matches = 0
        for pattern in fp.patterns:
            if re.search(pattern, text, re.IGNORECASE) or re.search(pattern, text_lower, re.IGNORECASE):
                matches += 1
        
        if matches > 0:
            confidence = min(1.0, matches / len(fp.patterns))
            if confidence >= fp.confidence_threshold:
                results.append(FingerprintResult(
                    os_guess=fp.name,
                    confidence=round(confidence, 2),
                    method="banner_fingerprint"
                ))
    
    # Sort by confidence descending
    results.sort(key=lambda x: x.confidence, reverse=True)
    return results


def auto_classify_device(
    host: str,
    banner: str = "",
    ssh_version: str = "",
    command_outputs: Dict[str, str] = None
) -> Tuple[str, float, str]:
    """
    Auto-classify a device based on all available fingerprinting data.
    Returns: (os_name, confidence, method)
    """
    command_outputs = command_outputs or {}
    
    # Combine all text sources
    combined_text = f"{banner}\n{ssh_version}\n"
    for cmd, output in command_outputs.items():
        combined_text += f"\n{output}\n"
    
    results = classify_os(combined_text)
    
    if results:
        top = results[0]
        return top.os_guess, top.confidence, top.method
    
    return "unknown", 0.0, "none"


# Device type classification
DEVICE_TYPE_PATTERNS = {
    "firewall": [
        r"firewall",
        r"security policy",
        r"threat",
        r"utm",
        r"ids/ips",
    ],
    "switch": [
        r"switch",
        r"vlan",
        r"trunk",
        r"spanning tree",
        r"\bl2\b",
    ],
    "router": [
        r"router",
        r"routing table",
        r"bgp",
        r"ospf",
        r"mpls",
        r"\bl3\b",
    ],
    "server": [
        r"server",
        r"systemctl",
        r"service",
        r"\bvm\b",
    ],
    "hypervisor": [
        r"esxi",
        r"proxmox",
        r"hypervisor",
        r"\bhost\b.*\bvm\b",
    ],
}


def classify_device_type(text: str) -> str:
    """Classify device type from text."""
    text_lower = text.lower()
    scores: Dict[str, int] = {}
    
    for dtype, patterns in DEVICE_TYPE_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE) or re.search(pattern, text_lower, re.IGNORECASE):
                score += 1
        if score > 0:
            scores[dtype] = score
    
    if not scores:
        return "unknown"
    
    return max(scores, key=scores.get)
