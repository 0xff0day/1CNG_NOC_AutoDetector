from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class HealthCheckManager:
    """Manage system health checks and status reporting."""
    
    def __init__(self):
        self.checks: Dict[str, callable] = {}
        self.last_results: Dict[str, Dict[str, Any]] = {}
    
    def register_check(self, name: str, check_func: callable):
        """Register a health check function."""
        self.checks[name] = check_func
    
    def run_check(self, name: str) -> Dict[str, Any]:
        """Run a single health check."""
        if name not in self.checks:
            return {
                "name": name,
                "status": "unknown",
                "error": "Check not registered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        
        try:
            start = datetime.now(timezone.utc)
            result = self.checks[name]()
            end = datetime.now(timezone.utc)
            
            check_result = {
                "name": name,
                "status": "healthy" if result else "unhealthy",
                "response_time_ms": (end - start).total_seconds() * 1000,
                "timestamp": end.isoformat(),
            }
            
            self.last_results[name] = check_result
            return check_result
            
        except Exception as e:
            result = {
                "name": name,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.last_results[name] = result
            return result
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = []
        
        for name in self.checks:
            results.append(self.run_check(name))
        
        healthy_count = sum(1 for r in results if r["status"] == "healthy")
        
        return {
            "overall_status": "healthy" if healthy_count == len(results) else "degraded",
            "healthy_count": healthy_count,
            "total_checks": len(results),
            "checks": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current health status."""
        if not self.last_results:
            return {
                "status": "unknown",
                "message": "No health checks run yet",
            }
        
        statuses = [r["status"] for r in self.last_results.values()]
        
        if all(s == "healthy" for s in statuses):
            return {"status": "healthy", "message": "All systems operational"}
        elif any(s == "error" for s in statuses):
            return {"status": "critical", "message": "One or more checks failed with errors"}
        else:
            return {"status": "degraded", "message": "Some checks reporting unhealthy"}


# Pre-built health checks
def create_database_health_check(storage) -> callable:
    """Create health check for database connectivity."""
    def check() -> bool:
        try:
            # Try to execute a simple query
            storage.execute("SELECT 1")
            return True
        except Exception:
            return False
    return check


def create_collector_health_check(collector) -> callable:
    """Create health check for collector."""
    def check() -> bool:
        try:
            # Check if collector is responsive
            return hasattr(collector, 'run_commands')
        except Exception:
            return False
    return check


def create_disk_space_health_check(min_free_mb: int = 100) -> callable:
    """Create health check for disk space."""
    import shutil
    
    def check() -> bool:
        try:
            stat = shutil.disk_usage(".")
            free_mb = stat.free / (1024 * 1024)
            return free_mb >= min_free_mb
        except Exception:
            return False
    return check


def create_memory_health_check(max_usage_pct: float = 90.0) -> callable:
    """Create health check for memory usage."""
    import psutil
    
    def check() -> bool:
        try:
            mem = psutil.virtual_memory()
            return mem.percent < max_usage_pct
        except Exception:
            return False
    return check


class ReadinessProbe:
    """Kubernetes-style readiness probe."""
    
    def __init__(self):
        self.ready = False
        self.dependencies: Dict[str, bool] = {}
    
    def mark_dependency_ready(self, name: str):
        """Mark a dependency as ready."""
        self.dependencies[name] = True
        self._update_readiness()
    
    def mark_dependency_not_ready(self, name: str):
        """Mark a dependency as not ready."""
        self.dependencies[name] = False
        self._update_readiness()
    
    def _update_readiness(self):
        """Update overall readiness status."""
        self.ready = all(self.dependencies.values())
    
    def is_ready(self) -> bool:
        """Check if system is ready."""
        return self.ready
    
    def get_probe_response(self) -> Dict[str, Any]:
        """Get probe response for health endpoint."""
        return {
            "ready": self.ready,
            "dependencies": self.dependencies,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class LivenessProbe:
    """Kubernetes-style liveness probe."""
    
    def __init__(self, max_staleness_sec: float = 60.0):
        self.last_ping = datetime.now(timezone.utc)
        self.max_staleness_sec = max_staleness_sec
    
    def ping(self):
        """Update liveness timestamp."""
        self.last_ping = datetime.now(timezone.utc)
    
    def is_alive(self) -> bool:
        """Check if system is alive."""
        now = datetime.now(timezone.utc)
        staleness = (now - self.last_ping).total_seconds()
        return staleness < self.max_staleness_sec
    
    def get_probe_response(self) -> Dict[str, Any]:
        """Get probe response for liveness endpoint."""
        alive = self.is_alive()
        now = datetime.now(timezone.utc)
        staleness = (now - self.last_ping).total_seconds()
        
        return {
            "alive": alive,
            "staleness_sec": staleness,
            "timestamp": now.isoformat(),
        }
