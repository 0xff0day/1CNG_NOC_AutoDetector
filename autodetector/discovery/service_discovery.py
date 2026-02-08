from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from autodetector.collector.ssh_collector import SshCollector
from autodetector.collector.telnet_collector import TelnetCollector


@dataclass(frozen=True)
class DiscoveredService:
    name: str
    port: int
    protocol: str  # tcp/udp
    version: str
    banner: str


@dataclass(frozen=True)
class ServiceEndpoint:
    device_id: str
    service_name: str
    address: str
    port: int
    health_status: str  # 'up', 'down', 'degraded'
    last_seen: str


class ServiceDiscoveryEngine:
    """Discover services running on devices and map dependencies."""
    
    COMMON_PORTS = {
        22: "ssh",
        23: "telnet",
        53: "dns",
        80: "http",
        443: "https",
        161: "snmp",
        3389: "rdp",
        445: "smb",
        21: "ftp",
        25: "smtp",
        110: "pop3",
        143: "imap",
        993: "imaps",
        995: "pop3s",
        587: "submission",
        3306: "mysql",
        5432: "postgresql",
        1433: "mssql",
        27017: "mongodb",
        6379: "redis",
        9200: "elasticsearch",
        5601: "kibana",
        5044: "logstash",
        9090: "prometheus",
        3000: "grafana",
        6443: "kubernetes-api",
        10250: "kubelet",
        2379: "etcd",
        2380: "etcd-peer",
    }
    
    def __init__(self):
        self.discovered_services: Dict[str, List[DiscoveredService]] = {}
        self.endpoints: List[ServiceEndpoint] = []
    
    async def discover_services(
        self,
        host: str,
        transport: str = "ssh",
        username: str = "",
        password: str = ""
    ) -> List[DiscoveredService]:
        """Discover services on a host via CLI commands."""
        services = []
        
        # Try to get listening ports
        commands = {
            "linux_ports": "netstat -tlnp 2>/dev/null || ss -tlnp",
            "windows_ports": "powershell -Command \"Get-NetTCPConnection -State Listen | Select-Object LocalPort,OwningProcess,LocalAddress\"",
            "processes": "ps aux 2>/dev/null || ps -ef",
        }
        
        try:
            if transport == "telnet":
                collector = TelnetCollector()
                outputs, _ = collector.run_commands(host, username, password, commands)
            else:
                collector = SshCollector()
                outputs, _ = collector.run_commands(host, username, password, commands)
            
            # Parse discovered services from outputs
            services = self._parse_services(outputs)
            
        except Exception as e:
            print(f"Service discovery failed for {host}: {e}")
        
        self.discovered_services[host] = services
        return services
    
    def _parse_services(self, outputs: Dict[str, str]) -> List[DiscoveredService]:
        """Parse service information from command outputs."""
        services = []
        
        port_output = outputs.get("linux_ports", "") + outputs.get("windows_ports", "")
        
        # Parse listening ports (simplified parsing)
        import re
        
        # Look for common port patterns
        for port, service_name in self.COMMON_PORTS.items():
            if re.search(rf":{port}\s|:{port}$|:{port}/", port_output):
                services.append(DiscoveredService(
                    name=service_name,
                    port=port,
                    protocol="tcp",
                    version="unknown",
                    banner=""
                ))
        
        return services
    
    def map_dependencies(
        self,
        source_device: str,
        target_devices: List[str],
        service_ports: List[int]
    ) -> List[Dict[str, Any]]:
        """Map service dependencies between devices."""
        dependencies = []
        
        for target in target_devices:
            for service in self.discovered_services.get(target, []):
                if service.port in service_ports:
                    dependencies.append({
                        "source": source_device,
                        "target": target,
                        "service": service.name,
                        "port": service.port,
                        "mapped_at": datetime.now(timezone.utc).isoformat(),
                    })
        
        return dependencies
    
    def get_service_health(
        self,
        device_id: str,
        service_name: str
    ) -> str:
        """Get health status of a service on a device."""
        for endpoint in self.endpoints:
            if endpoint.device_id == device_id and endpoint.service_name == service_name:
                return endpoint.health_status
        return "unknown"
    
    def update_endpoint_health(
        self,
        device_id: str,
        service_name: str,
        address: str,
        port: int,
        status: str
    ):
        """Update health status of a service endpoint."""
        endpoint = ServiceEndpoint(
            device_id=device_id,
            service_name=service_name,
            address=address,
            port=port,
            health_status=status,
            last_seen=datetime.now(timezone.utc).isoformat()
        )
        
        # Remove old entry if exists
        self.endpoints = [
            e for e in self.endpoints 
            if not (e.device_id == device_id and e.service_name == service_name)
        ]
        
        self.endpoints.append(endpoint)


class ApplicationTopologyMapper:
    """Map application-level topology and dependencies."""
    
    def __init__(self):
        self.topology: Dict[str, Any] = {
            "nodes": [],
            "edges": [],
            "layers": {
                "network": [],
                "compute": [],
                "storage": [],
                "application": [],
            }
        }
    
    def add_node(
        self,
        node_id: str,
        node_type: str,  # 'router', 'switch', 'firewall', 'server', 'vm', 'container', 'app'
        layer: str,  # 'network', 'compute', 'storage', 'application'
        properties: Dict[str, Any] = None
    ):
        """Add a node to the topology."""
        node = {
            "id": node_id,
            "type": node_type,
            "layer": layer,
            "properties": properties or {},
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self.topology["nodes"].append(node)
        self.topology["layers"][layer].append(node_id)
    
    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,  # 'physical', 'logical', 'dependency', 'traffic'
        properties: Dict[str, Any] = None
    ):
        """Add an edge (connection) between nodes."""
        edge = {
            "source": source,
            "target": target,
            "type": edge_type,
            "properties": properties or {},
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self.topology["edges"].append(edge)
    
    def find_impact_scope(
        self,
        failed_node: str,
        max_hops: int = 3
    ) -> List[str]:
        """Find all nodes impacted by a failure (BFS traversal)."""
        impacted = set()
        visited = {failed_node}
        current_level = {failed_node}
        
        for hop in range(max_hops):
            next_level = set()
            for node in current_level:
                # Find all nodes connected to this one
                for edge in self.topology["edges"]:
                    if edge["source"] == node and edge["target"] not in visited:
                        next_level.add(edge["target"])
                        impacted.add(edge["target"])
                    elif edge["target"] == node and edge["source"] not in visited:
                        next_level.add(edge["source"])
                        impacted.add(edge["source"])
            
            visited.update(next_level)
            current_level = next_level
            
            if not current_level:
                break
        
        return sorted(list(impacted))
    
    def export_topology(self, format: str = "json") -> Any:
        """Export topology in various formats."""
        if format == "json":
            return self.topology
        elif format == "graphviz":
            return self._to_graphviz()
        elif format == "mermaid":
            return self._to_mermaid()
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def _to_graphviz(self) -> str:
        """Export as Graphviz DOT format."""
        dot = ["digraph topology {"]
        
        for node in self.topology["nodes"]:
            dot.append(f'  "{node["id"]}" [label="{node["id"]} ({node["type"]})"];')
        
        for edge in self.topology["edges"]:
            dot.append(f'  "{edge["source"]}" -> "{edge["target"]}" [label="{edge["type"]}"];')
        
        dot.append("}")
        return "\n".join(dot)
    
    def _to_mermaid(self) -> str:
        """Export as Mermaid flowchart format."""
        mmd = ["flowchart TB"]
        
        for node in self.topology["nodes"]:
            mmd.append(f'  {node["id"].replace("-", "_")}[{node["id"]}]')
        
        for edge in self.topology["edges"]:
            src = edge["source"].replace("-", "_")
            tgt = edge["target"].replace("-", "_")
            mmd.append(f'  {src} -->|{edge["type"]}| {tgt}')
        
        return "\n".join(mmd)
