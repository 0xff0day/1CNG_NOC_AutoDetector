from __future__ import annotations

import json
import re
from typing import Any, Dict, List


def _parse_go_version(version_output: str) -> Dict[str, Any]:
    """Parse Go version from output."""
    metrics: List[Dict[str, Any]] = []
    
    # Try to extract version like "go version go1.21.5 linux/amd64"
    version_match = re.search(r'go version go([\d.]+)', version_output)
    if version_match:
        metrics.append({
            "name": "GO_VERSION",
            "value": version_match.group(1),
            "type": "text",
            "unit": "version"
        })
    
    return {"metrics": metrics}


def _parse_gops_stats(gops_output: str) -> Dict[str, Any]:
    """Parse gops (Go process stats) output."""
    metrics: List[Dict[str, Any]] = []
    
    lines = gops_output.strip().split('\n')
    for line in lines:
        # Parse lines like "goroutines:\t42"
        match = re.match(r'(\w+):\s*(\d+(?:\.\d+)?)', line)
        if match:
            name, value = match.group(1), float(match.group(2))
            
            if name == "goroutines":
                metrics.append({
                    "name": "GO_GOROUTINES",
                    "value": int(value),
                    "type": "gauge",
                    "unit": "count"
                })
            elif name == "OS threads":
                metrics.append({
                    "name": "GO_THREADS",
                    "value": int(value),
                    "type": "gauge",
                    "unit": "count"
                })
            elif name == "GC cycles":
                metrics.append({
                    "name": "GO_GC_CYCLES",
                    "value": int(value),
                    "type": "counter",
                    "unit": "count"
                })
            elif name == "Heap alloc":
                metrics.append({
                    "name": "GO_HEAP_ALLOC",
                    "value": value,
                    "type": "gauge",
                    "unit": "bytes"
                })
            elif name == "Heap sys":
                metrics.append({
                    "name": "GO_HEAP_SYS",
                    "value": value,
                    "type": "gauge",
                    "unit": "bytes"
                })
    
    return {"metrics": metrics}


def _parse_pprof_heap(heap_output: str) -> Dict[str, Any]:
    """Parse pprof heap profile output."""
    metrics: List[Dict[str, Any]] = []
    
    # Look for heap alloc and sys in text format
    alloc_match = re.search(r'heap alloc:\s*(\d+)', heap_output, re.IGNORECASE)
    if alloc_match:
        metrics.append({
            "name": "GO_HEAP_ALLOC_BYTES",
            "value": int(alloc_match.group(1)),
            "type": "gauge",
            "unit": "bytes"
        })
    
    sys_match = re.search(r'heap sys:\s*(\d+)', heap_output, re.IGNORECASE)
    if sys_match:
        metrics.append({
            "name": "GO_HEAP_SYS_BYTES",
            "value": int(sys_match.group(1)),
            "type": "gauge",
            "unit": "bytes"
        })
    
    # Look for in-use objects
    inuse_match = re.search(r'inuse objects:\s*(\d+)', heap_output, re.IGNORECASE)
    if inuse_match:
        metrics.append({
            "name": "GO_HEAP_INUSE_OBJECTS",
            "value": int(inuse_match.group(1)),
            "type": "gauge",
            "unit": "count"
        })
    
    return {"metrics": metrics}


def _parse_expvar_metrics(expvar_output: str) -> Dict[str, Any]:
    """Parse /debug/vars (expvar) JSON output."""
    metrics: List[Dict[str, Any]] = []
    
    try:
        data = json.loads(expvar_output)
        
        # Extract memstats if present
        if "memstats" in data:
            memstats = data["memstats"]
            metrics.append({
                "name": "GO_HEAP_ALLOC_BYTES",
                "value": memstats.get("Alloc", 0),
                "type": "gauge",
                "unit": "bytes"
            })
            metrics.append({
                "name": "GO_HEAP_SYS_BYTES",
                "value": memstats.get("Sys", 0),
                "type": "gauge",
                "unit": "bytes"
            })
            metrics.append({
                "name": "GO_HEAP_INUSE_BYTES",
                "value": memstats.get("HeapInuse", 0),
                "type": "gauge",
                "unit": "bytes"
            })
            metrics.append({
                "name": "GO_GC_COUNT",
                "value": memstats.get("NumGC", 0),
                "type": "counter",
                "unit": "count"
            })
            metrics.append({
                "name": "GO_GC_PAUSE_NS",
                "value": memstats.get("PauseNs", [0])[-1] if memstats.get("PauseNs") else 0,
                "type": "gauge",
                "unit": "nanoseconds"
            })
        
        # Extract custom counters
        for key, value in data.items():
            if key != "memstats" and isinstance(value, (int, float)):
                metrics.append({
                    "name": f"GO_EXPVAR_{key.upper()}",
                    "value": value,
                    "type": "gauge" if isinstance(value, float) else "counter",
                    "unit": "count"
                })
    
    except json.JSONDecodeError:
        pass
    
    return {"metrics": metrics}


def _parse_prometheus_metrics(prom_output: str) -> Dict[str, Any]:
    """Parse Prometheus format metrics from Go apps."""
    metrics: List[Dict[str, Any]] = []
    
    lines = prom_output.strip().split('\n')
    for line in lines:
        # Skip comments
        if line.startswith('#') or not line.strip():
            continue
        
        # Parse metric line like: go_goroutines 42
        # or: go_memstats_heap_alloc_bytes 1234567
        match = re.match(r'^(\w+)\s+([\d.]+)(?:\s+\S+)?$', line)
        if match:
            name, value = match.group(1), float(match.group(2))
            
            # Map common Go metrics
            if name == "go_goroutines":
                metrics.append({
                    "name": "GO_GOROUTINES",
                    "value": int(value),
                    "type": "gauge",
                    "unit": "count"
                })
            elif name == "go_threads":
                metrics.append({
                    "name": "GO_THREADS",
                    "value": int(value),
                    "type": "gauge",
                    "unit": "count"
                })
            elif name == "go_gc_duration_seconds":
                metrics.append({
                    "name": "GO_GC_DURATION_SECONDS",
                    "value": value,
                    "type": "gauge",
                    "unit": "seconds"
                })
            elif name == "go_memstats_heap_alloc_bytes":
                metrics.append({
                    "name": "GO_HEAP_ALLOC_BYTES",
                    "value": int(value),
                    "type": "gauge",
                    "unit": "bytes"
                })
            elif name == "go_memstats_heap_sys_bytes":
                metrics.append({
                    "name": "GO_HEAP_SYS_BYTES",
                    "value": int(value),
                    "type": "gauge",
                    "unit": "bytes"
                })
            elif name == "go_memstats_heap_inuse_bytes":
                metrics.append({
                    "name": "GO_HEAP_INUSE_BYTES",
                    "value": int(value),
                    "type": "gauge",
                    "unit": "bytes"
                })
            elif name == "go_memstats_heap_idle_bytes":
                metrics.append({
                    "name": "GO_HEAP_IDLE_BYTES",
                    "value": int(value),
                    "type": "gauge",
                    "unit": "bytes"
                })
    
    return {"metrics": metrics}


def _parse_process_list(ps_output: str) -> Dict[str, Any]:
    """Parse process list to find Go processes."""
    metrics: List[Dict[str, Any]] = []
    
    go_processes = []
    lines = ps_output.strip().split('\n')
    
    for line in lines:
        # Look for go processes (binaries containing "/go" or ending in app names)
        if re.search(r'\b(go\s+(run|build|test|mod)|main\.go|\./\w+)$', line):
            go_processes.append(line.strip())
    
    metrics.append({
        "name": "GO_PROCESS_COUNT",
        "value": len(go_processes),
        "type": "gauge",
        "unit": "count"
    })
    
    return {"metrics": metrics, "go_processes": go_processes}


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse Go programming language metrics from various sources.
    
    Supports:
    - Go version detection
    - Runtime metrics via gops
    - pprof heap profiles
    - expvar /debug/vars endpoint
    - Prometheus format metrics
    - Process list scanning
    """
    all_metrics: List[Dict[str, Any]] = []
    raw_data: Dict[str, Any] = {"outputs": outputs, "errors": errors}
    
    # Parse each command output
    if "go_version" in outputs:
        result = _parse_go_version(outputs["go_version"])
        all_metrics.extend(result.get("metrics", []))
    
    if "gops_stats" in outputs:
        result = _parse_gops_stats(outputs["gops_stats"])
        all_metrics.extend(result.get("metrics", []))
    
    if "pprof_heap" in outputs:
        result = _parse_pprof_heap(outputs["pprof_heap"])
        all_metrics.extend(result.get("metrics", []))
    
    if "expvar_metrics" in outputs:
        result = _parse_expvar_metrics(outputs["expvar_metrics"])
        all_metrics.extend(result.get("metrics", []))
    
    if "prometheus_metrics" in outputs:
        result = _parse_prometheus_metrics(outputs["prometheus_metrics"])
        all_metrics.extend(result.get("metrics", []))
    
    if "process_list" in outputs:
        result = _parse_process_list(outputs["process_list"])
        all_metrics.extend(result.get("metrics", []))
        raw_data["go_processes"] = result.get("go_processes", [])
    
    return {"metrics": all_metrics, "raw": raw_data}
