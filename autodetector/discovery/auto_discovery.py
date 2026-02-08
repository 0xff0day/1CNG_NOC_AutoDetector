"""
Device Auto Discovery Module

Automatically discovers network devices using various methods:
- SNMP network scanning
- Ping sweeps
- ARP table inspection
- CDP/LLDP neighbor discovery
- Route table analysis
"""

from __future__ import annotations

import socket
import subprocess
import ipaddress
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredDevice:
    """Discovered device information."""
    ip_address: str
    hostname: Optional[str] = None
    mac_address: Optional[str] = None
    vendor: Optional[str] = None
    device_type: Optional[str] = None  # router, switch, server, etc.
    discovery_method: str = ""
    open_ports: List[int] = None
    snmp_available: bool = False
    ssh_available: bool = False
    telnet_available: bool = False
    
    def __post_init__(self):
        if self.open_ports is None:
            self.open_ports = []


class DeviceAutoDiscovery:
    """
    Automatic device discovery engine.
    
    Supports multiple discovery methods that can be combined
    for comprehensive network mapping.
    """
    
    COMMON_PORTS = {
        22: "SSH",
        23: "Telnet",
        80: "HTTP",
        443: "HTTPS",
        161: "SNMP",
        162: "SNMP Trap",
        443: "HTTPS",
        830: "NETCONF",
        8080: "HTTP Alt",
    }
    
    def __init__(self, max_workers: int = 50, timeout: int = 2):
        self.max_workers = max_workers
        self.timeout = timeout
        self._discovered: Dict[str, DiscoveredDevice] = {}
    
    def discover_by_ping(
        self,
        network: str,
        exclude_ips: Optional[List[str]] = None
    ) -> List[DiscoveredDevice]:
        """
        Discover devices by ping sweep.
        
        Args:
            network: CIDR notation (e.g., "192.168.1.0/24")
            exclude_ips: IPs to skip
        
        Returns:
            List of discovered devices
        """
        exclude = set(exclude_ips or [])
        discovered = []
        
        try:
            net = ipaddress.ip_network(network, strict=False)
            hosts = [str(ip) for ip in net.hosts() if str(ip) not in exclude]
            
            logger.info(f"Starting ping sweep on {network} ({len(hosts)} hosts)")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self._ping_host, ip): ip for ip in hosts}
                
                for future in as_completed(futures):
                    ip = futures[future]
                    try:
                        if future.result():
                            device = DiscoveredDevice(
                                ip_address=ip,
                                discovery_method="ping"
                            )
                            discovered.append(device)
                            logger.debug(f"Host up: {ip}")
                    except Exception as e:
                        logger.debug(f"Ping failed for {ip}: {e}")
            
            logger.info(f"Ping sweep complete: {len(discovered)} hosts found")
            
        except Exception as e:
            logger.error(f"Ping sweep error: {e}")
        
        return discovered
    
    def _ping_host(self, ip: str) -> bool:
        """Ping a single host."""
        try:
            # Use system ping command
            if subprocess.sys.platform == "win32":
                cmd = ["ping", "-n", "1", "-w", str(self.timeout * 1000), ip]
            else:
                cmd = ["ping", "-c", "1", "-W", str(self.timeout), ip]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.timeout + 1
            )
            return result.returncode == 0
            
        except Exception:
            return False
    
    def discover_by_port_scan(
        self,
        network: str,
        ports: Optional[List[int]] = None,
        exclude_ips: Optional[List[str]] = None
    ) -> List[DiscoveredDevice]:
        """
        Discover devices by port scanning.
        
        Args:
            network: CIDR notation
            ports: Ports to check (default: COMMON_PORTS)
            exclude_ips: IPs to skip
        
        Returns:
            List of discovered devices with open ports
        """
        ports = ports or list(self.COMMON_PORTS.keys())
        exclude = set(exclude_ips or [])
        discovered: Dict[str, DiscoveredDevice] = {}
        
        try:
            net = ipaddress.ip_network(network, strict=False)
            hosts = [str(ip) for ip in net.hosts() if str(ip) not in exclude]
            
            logger.info(f"Starting port scan on {network} ({len(hosts)} hosts, {len(ports)} ports)")
            
            # Create scan tasks
            scan_tasks = [(ip, port) for ip in hosts for port in ports]
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._check_port, ip, port): (ip, port)
                    for ip, port in scan_tasks
                }
                
                for future in as_completed(futures):
                    ip, port = futures[future]
                    try:
                        if future.result():
                            if ip not in discovered:
                                discovered[ip] = DiscoveredDevice(
                                    ip_address=ip,
                                    discovery_method="port_scan",
                                    open_ports=[]
                                )
                            discovered[ip].open_ports.append(port)
                            
                            # Mark protocol availability
                            if port == 22:
                                discovered[ip].ssh_available = True
                            elif port == 23:
                                discovered[ip].telnet_available = True
                            elif port == 161:
                                discovered[ip].snmp_available = True
                            
                    except Exception as e:
                        logger.debug(f"Port check failed for {ip}:{port}: {e}")
            
            # Filter to hosts with open ports
            devices = [d for d in discovered.values() if d.open_ports]
            logger.info(f"Port scan complete: {len(devices)} devices found")
            
            return devices
            
        except Exception as e:
            logger.error(f"Port scan error: {e}")
            return []
    
    def _check_port(self, ip: str, port: int) -> bool:
        """Check if a port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def discover_by_snmp(
        self,
        network: str,
        community: str = "public",
        exclude_ips: Optional[List[str]] = None
    ) -> List[DiscoveredDevice]:
        """
        Discover devices using SNMP scanning.
        
        Attempts to retrieve device info via SNMPv1/v2c.
        """
        try:
            from pysnmp.hlapi import (
                getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
                ContextData, ObjectType, ObjectIdentity
            )
        except ImportError:
            logger.error("pysnmp not available for SNMP discovery")
            return []
        
        exclude = set(exclude_ips or [])
        discovered = []
        
        try:
            net = ipaddress.ip_network(network, strict=False)
            hosts = [str(ip) for ip in net.hosts() if str(ip) not in exclude]
            
            logger.info(f"Starting SNMP discovery on {network}")
            
            for ip in hosts:
                try:
                    # Query system description
                    iterator = getCmd(
                        SnmpEngine(),
                        CommunityData(community),
                        UdpTransportTarget((ip, 161), timeout=self.timeout, retries=0),
                        ContextData(),
                        ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0')),  # sysDescr
                        ObjectType(ObjectIdentity('1.3.6.1.2.1.1.5.0')),  # sysName
                    )
                    
                    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
                    
                    if errorIndication or errorStatus:
                        continue
                    
                    # Parse results
                    sys_descr = str(varBinds[0][1]) if varBinds else ""
                    sys_name = str(varBinds[1][1]) if len(varBinds) > 1 else None
                    
                    # Extract vendor from description
                    vendor = self._extract_vendor(sys_descr)
                    device_type = self._classify_device_type(sys_descr)
                    
                    device = DiscoveredDevice(
                        ip_address=ip,
                        hostname=sys_name,
                        vendor=vendor,
                        device_type=device_type,
                        discovery_method="snmp",
                        snmp_available=True
                    )
                    discovered.append(device)
                    logger.debug(f"SNMP response from {ip}: {vendor} {device_type}")
                    
                except Exception as e:
                    logger.debug(f"SNMP failed for {ip}: {e}")
            
            logger.info(f"SNMP discovery complete: {len(discovered)} devices found")
            
        except Exception as e:
            logger.error(f"SNMP discovery error: {e}")
        
        return discovered
    
    def _extract_vendor(self, sys_descr: str) -> Optional[str]:
        """Extract vendor from system description."""
        vendors = {
            "cisco": "Cisco",
            "juniper": "Juniper",
            "arista": "Arista",
            "hp": "HP/H3C",
            "h3c": "H3C",
            "huawei": "Huawei",
            "fortinet": "Fortinet",
            "palo": "Palo Alto",
            "checkpoint": "Check Point",
            "f5": "F5",
            "brocade": "Brocade",
            "extreme": "Extreme",
            "dell": "Dell",
        }
        
        sys_lower = sys_descr.lower()
        for key, vendor in vendors.items():
            if key in sys_lower:
                return vendor
        return None
    
    def _classify_device_type(self, sys_descr: str) -> Optional[str]:
        """Classify device type from description."""
        desc_lower = sys_descr.lower()
        
        if any(x in desc_lower for x in ["router", "routing"]):
            return "router"
        elif any(x in desc_lower for x in ["switch", "switching"]):
            return "switch"
        elif any(x in desc_lower for x in ["firewall", "security"]):
            return "firewall"
        elif any(x in desc_lower for x in ["server", "linux", "windows"]):
            return "server"
        elif "access point" in desc_lower or "ap" in desc_lower:
            return "access_point"
        elif "ups" in desc_lower or "power" in desc_lower:
            return "ups"
        
        return "unknown"
    
    def comprehensive_discovery(
        self,
        networks: List[str],
        snmp_community: str = "public",
        use_snmp: bool = True,
        use_ping: bool = True,
        use_port_scan: bool = True,
    ) -> List[DiscoveredDevice]:
        """
        Run comprehensive discovery using multiple methods.
        
        Combines results from all discovery methods and merges
        duplicates to provide complete device inventory.
        """
        all_discovered: Dict[str, DiscoveredDevice] = {}
        
        for network in networks:
            logger.info(f"Discovering network: {network}")
            
            # Track IPs to exclude in subsequent methods
            discovered_ips: Set[str] = set()
            
            # SNMP discovery (most informative)
            if use_snmp:
                snmp_devices = self.discover_by_snmp(network, snmp_community, list(discovered_ips))
                for device in snmp_devices:
                    all_discovered[device.ip_address] = device
                    discovered_ips.add(device.ip_address)
            
            # Ping sweep
            if use_ping:
                ping_devices = self.discover_by_ping(network, list(discovered_ips))
                for device in ping_devices:
                    if device.ip_address not in all_discovered:
                        all_discovered[device.ip_address] = device
                    discovered_ips.add(device.ip_address)
            
            # Port scan for remaining IPs
            if use_port_scan:
                port_devices = self.discover_by_port_scan(network, exclude_ips=list(discovered_ips))
                for device in port_devices:
                    if device.ip_address not in all_discovered:
                        all_discovered[device.ip_address] = device
        
        # Additional enrichment for discovered devices
        self._enrich_devices(list(all_discovered.values()))
        
        logger.info(f"Discovery complete: {len(all_discovered)} unique devices found")
        return list(all_discovered.values())
    
    def _enrich_devices(self, devices: List[DiscoveredDevice]) -> None:
        """Enrich device information with reverse DNS and other data."""
        for device in devices:
            try:
                # Reverse DNS lookup
                if not device.hostname:
                    hostname, _, _ = socket.gethostbyaddr(device.ip_address)
                    device.hostname = hostname
            except Exception:
                pass
    
    def export_to_csv(self, devices: List[DiscoveredDevice], filepath: str) -> None:
        """Export discovered devices to CSV."""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'IP Address', 'Hostname', 'MAC Address', 'Vendor',
                'Device Type', 'Discovery Method', 'SSH', 'Telnet', 'SNMP',
                'Open Ports'
            ])
            
            for d in devices:
                writer.writerow([
                    d.ip_address,
                    d.hostname or '',
                    d.mac_address or '',
                    d.vendor or '',
                    d.device_type or '',
                    d.discovery_method,
                    d.ssh_available,
                    d.telnet_available,
                    d.snmp_available,
                    ','.join(map(str, d.open_ports))
                ])
        
        logger.info(f"Exported {len(devices)} devices to {filepath}")
