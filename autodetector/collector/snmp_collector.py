from __future__ import annotations

from pysnmp.hlapi.v3arch.asyncio import *
from pysnmp.smi.rfc1902 import ObjectIdentity
from typing import Any, Dict, List, Optional
import asyncio


class SNMPCollector:
    """SNMP collector for device discovery and monitoring."""
    
    COMMON_OIDS = {
        "sysDescr": "1.3.6.1.2.1.1.1.0",
        "sysObjectID": "1.3.6.1.2.1.1.2.0",
        "sysUpTime": "1.3.6.1.2.1.1.3.0",
        "sysContact": "1.3.6.1.2.1.1.4.0",
        "sysName": "1.3.6.1.2.1.1.5.0",
        "sysLocation": "1.3.6.1.2.1.1.6.0",
        "ifNumber": "1.3.6.1.2.1.2.1.0",
    }
    
    def __init__(self, community: str = "public", version: int = 2):
        self.community = community
        self.version = version
    
    async def get_device_info(self, host: str, port: int = 161) -> Dict[str, Any]:
        """Get basic device info via SNMP."""
        result = {}
        
        for name, oid in self.COMMON_OIDS.items():
            try:
                iterator = getCmd(
                    SnmpEngine(),
                    CommunityData(self.community),
                    await UdpTransportTarget.create((host, port)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid))
                )
                
                errorIndication, errorStatus, errorIndex, varBinds = await iterator
                
                if errorIndication:
                    result[name] = None
                elif errorStatus:
                    result[name] = None
                else:
                    for varBind in varBinds:
                        result[name] = str(varBind[1])
            except Exception as e:
                result[name] = None
                result[f"{name}_error"] = str(e)
        
        return result
    
    async def get_interface_table(self, host: str, port: int = 161) -> List[Dict[str, Any]]:
        """Get interface table via SNMP."""
        interfaces = []
        
        # IF-MIB::ifTable
        oid_prefix = "1.3.6.1.2.1.2.2.1"
        
        try:
            iterator = nextCmd(
                SnmpEngine(),
                CommunityData(self.community),
                await UdpTransportTarget.create((host, port)),
                ContextData(),
                ObjectType(ObjectIdentity(oid_prefix)),
                lexicographicMode=False
            )
            
            async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
                if errorIndication or errorStatus:
                    break
                
                iface_data = {}
                for varBind in varBinds:
                    oid_str = str(varBind[0])
                    value = str(varBind[1])
                    
                    if "2.1" in oid_str:
                        iface_data["ifIndex"] = value
                    elif "2.2" in oid_str:
                        iface_data["ifDescr"] = value
                    elif "2.3" in oid_str:
                        iface_data["ifType"] = value
                    elif "2.5" in oid_str:
                        iface_data["ifSpeed"] = value
                    elif "2.8" in oid_str:
                        iface_data["ifOperStatus"] = value
                
                if iface_data:
                    interfaces.append(iface_data)
                    
        except Exception as e:
            return [{"error": str(e)}]
        
        return interfaces
    
    async def discover_via_snmp(self, host: str, port: int = 161) -> Dict[str, Any]:
        """Full SNMP discovery of a device."""
        info = await self.get_device_info(host, port)
        interfaces = await self.get_interface_table(host, port)
        
        return {
            "host": host,
            "snmp_community": self.community,
            "device_info": info,
            "interfaces": interfaces,
            "discovered_at": asyncio.get_event_loop().time(),
        }


class SNMPDiscoveryScanner:
    """Scan network ranges via SNMP for device discovery."""
    
    def __init__(self, community: str = "public", timeout_sec: float = 2.0):
        self.collector = SNMPCollector(community=community)
        self.timeout_sec = timeout_sec
    
    async def scan_host(self, host: str) -> Optional[Dict[str, Any]]:
        """Scan a single host via SNMP."""
        try:
            result = await asyncio.wait_for(
                self.collector.discover_via_snmp(host),
                timeout=self.timeout_sec
            )
            
            # Check if we got valid data
            if result["device_info"].get("sysDescr"):
                return result
            return None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            return {"host": host, "error": str(e)}
    
    async def scan_range(self, hosts: List[str], max_concurrent: int = 50) -> List[Dict[str, Any]]:
        """Scan a list of hosts concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scan_with_limit(host: str) -> Optional[Dict[str, Any]]:
            async with semaphore:
                return await self.scan_host(host)
        
        tasks = [scan_with_limit(h) for h in hosts]
        results = await asyncio.gather(*tasks)
        
        return [r for r in results if r is not None]
