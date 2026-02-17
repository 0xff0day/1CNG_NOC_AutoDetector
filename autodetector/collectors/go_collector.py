from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class GoProcessInfo:
    """Information about a running Go process."""
    pid: int
    cmdline: str
    goroutines: int = 0
    threads: int = 0
    heap_alloc: int = 0
    version: str = ""
    uptime_seconds: int = 0


@dataclass
class GoRuntimeMetrics:
    """Go runtime metrics from various sources."""
    goroutines: int = 0
    threads: int = 0
    heap_alloc_bytes: int = 0
    heap_sys_bytes: int = 0
    heap_inuse_bytes: int = 0
    gc_count: int = 0
    gc_pause_ns: int = 0
    version: str = ""


class GoCollector:
    """
    Collector for Go programming language runtime metrics.
    
    Collects metrics from:
    - go version command
    - gops tool (if available)
    - pprof endpoints (if exposed)
    - expvar /debug/vars
    - Prometheus /metrics endpoints
    - Process inspection via /proc
    """
    
    def __init__(self, ssh_client: Any, config: Optional[Dict[str, Any]] = None):
        self.ssh = ssh_client
        self.config = config or {}
        self.pprof_port = self.config.get("pprof_port", 6060)
        self.metrics_port = self.config.get("metrics_port", 9090)
        
    def collect_go_version(self) -> Optional[str]:
        """Collect Go version from system."""
        try:
            result = self.ssh.exec_command("go version")
            if result and "go version" in result:
                # Extract version like "go1.21.5"
                match = re.search(r'go version go([\d.]+)', result)
                return match.group(1) if match else result.strip()
        except Exception:
            pass
        return None
    
    def collect_process_list(self) -> List[GoProcessInfo]:
        """Collect list of running Go processes."""
        processes = []
        
        try:
            # Find Go processes
            result = self.ssh.exec_command(
                "ps aux | grep -E '(go |main\\.go|\\.go$|/go/)' | grep -v grep"
            )
            
            if not result:
                return processes
            
            lines = result.strip().split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 11:
                    try:
                        pid = int(parts[1])
                        cmdline = ' '.join(parts[10:])
                        processes.append(GoProcessInfo(
                            pid=pid,
                            cmdline=cmdline
                        ))
                    except (ValueError, IndexError):
                        continue
                        
        except Exception:
            pass
        
        return processes
    
    def collect_gops_stats(self, pid: int) -> Optional[GoRuntimeMetrics]:
        """Collect stats using gops tool."""
        try:
            result = self.ssh.exec_command(f"gops {pid} 2>/dev/null")
            if not result or "not available" in result.lower():
                return None
            
            metrics = GoRuntimeMetrics()
            
            # Parse gops output
            for line in result.split('\n'):
                line = line.strip()
                
                if line.startswith("goroutines:"):
                    match = re.search(r'(\d+)', line)
                    if match:
                        metrics.goroutines = int(match.group(1))
                        
                elif line.startswith("OS threads:"):
                    match = re.search(r'(\d+)', line)
                    if match:
                        metrics.threads = int(match.group(1))
                        
                elif line.startswith("Heap alloc:"):
                    match = re.search(r'(\d+)', line)
                    if match:
                        metrics.heap_alloc_bytes = int(match.group(1))
                        
                elif line.startswith("GC cycles:"):
                    match = re.search(r'(\d+)', line)
                    if match:
                        metrics.gc_count = int(match.group(1))
            
            return metrics
            
        except Exception:
            return None
    
    def collect_expvar_metrics(self, port: int = 6060) -> Optional[Dict[str, Any]]:
        """Collect metrics from /debug/vars endpoint."""
        try:
            result = self.ssh.exec_command(
                f"curl -s http://localhost:{port}/debug/vars 2>/dev/null"
            )
            
            if not result or "not accessible" in result.lower():
                return None
            
            return json.loads(result)
            
        except (json.JSONDecodeError, Exception):
            return None
    
    def collect_pprof_heap(self, port: int = 6060) -> Optional[str]:
        """Collect heap profile from pprof endpoint."""
        try:
            result = self.ssh.exec_command(
                f"curl -s http://localhost:{port}/debug/pprof/heap?debug=1 2>/dev/null"
            )
            
            if result and "not accessible" not in result.lower():
                return result
                
        except Exception:
            pass
        
        return None
    
    def collect_prometheus_metrics(self, port: Optional[int] = None) -> Optional[str]:
        """Collect Prometheus-format metrics."""
        ports_to_try = [port] if port else [9090, 8080, 3000]
        
        for p in ports_to_try:
            try:
                result = self.ssh.exec_command(
                    f"curl -s http://localhost:{p}/metrics 2>/dev/null"
                )
                
                if result and "go_" in result:
                    return result
                    
            except Exception:
                continue
        
        return None
    
    def collect_proc_stats(self, pid: int) -> Optional[Dict[str, Any]]:
        """Collect process stats from /proc filesystem."""
        stats = {}
        
        try:
            # Memory stats from status
            result = self.ssh.exec_command(f"cat /proc/{pid}/status 2>/dev/null")
            if result:
                for line in result.split('\n'):
                    if line.startswith('VmRSS:'):
                        match = re.search(r'(\d+)', line)
                        if match:
                            stats['vm_rss_kb'] = int(match.group(1))
                            
                    elif line.startswith('VmSize:'):
                        match = re.search(r'(\d+)', line)
                        if match:
                            stats['vm_size_kb'] = int(match.group(1))
                            
                    elif line.startswith('Threads:'):
                        match = re.search(r'(\d+)', line)
                        if match:
                            stats['threads'] = int(match.group(1))
            
            # Command line
            cmdline = self.ssh.exec_command(f"cat /proc/{pid}/cmdline 2>/dev/null | tr '\\0' ' '")
            if cmdline:
                stats['cmdline'] = cmdline.strip()
                
        except Exception:
            pass
        
        return stats if stats else None
    
    def collect_all(self) -> Dict[str, Any]:
        """Collect all available Go metrics."""
        results = {
            "go_version": self.collect_go_version(),
            "processes": [],
            "runtime_metrics": {},
            "expvar": None,
            "prometheus": None,
            "pprof_heap": None,
        }
        
        # Collect process list
        processes = self.collect_process_list()
        results["process_count"] = len(processes)
        
        # Collect detailed stats for first few processes
        for proc in processes[:5]:  # Limit to avoid overload
            proc_data = {
                "pid": proc.pid,
                "cmdline": proc.cmdline,
            }
            
            # Try gops
            gops_stats = self.collect_gops_stats(proc.pid)
            if gops_stats:
                proc_data["gops"] = {
                    "goroutines": gops_stats.goroutines,
                    "threads": gops_stats.threads,
                    "heap_alloc": gops_stats.heap_alloc_bytes,
                    "gc_count": gops_stats.gc_count,
                }
            
            # Try /proc
            proc_stats = self.collect_proc_stats(proc.pid)
            if proc_stats:
                proc_data["proc"] = proc_stats
            
            results["processes"].append(proc_data)
        
        # Try expvar endpoint
        results["expvar"] = self.collect_expvar_metrics()
        
        # Try prometheus metrics
        results["prometheus"] = self.collect_prometheus_metrics()
        
        # Try pprof heap
        results["pprof_heap"] = self.collect_pprof_heap()
        
        return results


class GoHTTPCollector:
    """
    Collector for Go metrics via HTTP endpoints.
    For use when SSH is not available but metrics endpoints are exposed.
    """
    
    def __init__(self, base_url: str, config: Optional[Dict[str, Any]] = None):
        self.base_url = base_url.rstrip('/')
        self.config = config or {}
        self.timeout = self.config.get("timeout", 10)
        
    def collect_expvar(self) -> Optional[Dict[str, Any]]:
        """Collect from /debug/vars."""
        import urllib.request
        
        try:
            url = f"{self.base_url}/debug/vars"
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except Exception:
            return None
    
    def collect_prometheus(self) -> Optional[str]:
        """Collect from /metrics."""
        import urllib.request
        
        try:
            url = f"{self.base_url}/metrics"
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                return response.read().decode()
        except Exception:
            return None
    
    def collect_pprof(self, profile_type: str = "heap") -> Optional[str]:
        """Collect pprof profile."""
        import urllib.request
        
        try:
            url = f"{self.base_url}/debug/pprof/{profile_type}"
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                return response.read().decode()
        except Exception:
            return None
    
    def collect_all(self) -> Dict[str, Any]:
        """Collect all available metrics via HTTP."""
        return {
            "expvar": self.collect_expvar(),
            "prometheus": self.collect_prometheus(),
            "pprof_heap": self.collect_pprof("heap"),
            "pprof_goroutine": self.collect_pprof("goroutine"),
            "pprof_allocs": self.collect_pprof("allocs"),
        }
