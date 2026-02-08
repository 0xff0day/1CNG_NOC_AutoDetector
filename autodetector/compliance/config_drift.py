from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


@dataclass(frozen=True)
class ConfigSnapshot:
    device_id: str
    timestamp: str
    config_hash: str
    config_text: str
    source: str  # 'running', 'startup', 'backup'


@dataclass(frozen=True)
class ConfigDrift:
    device_id: str
    detected_at: str
    severity: str  # 'info', 'warning', 'critical'
    drift_type: str  # 'unauthorized_change', 'expected_change', 'backup_mismatch'
    previous_hash: str
    current_hash: str
    diff_summary: str


class ConfigDriftDetector:
    """Detect configuration changes and drifts across device configs."""
    
    def __init__(self, storage: Any = None):
        self.storage = storage
        self._baseline_cache: Dict[str, ConfigSnapshot] = {}
    
    def _compute_hash(self, config_text: str) -> str:
        """Compute SHA-256 hash of config."""
        return hashlib.sha256(config_text.encode('utf-8')).hexdigest()[:16]
    
    def capture_baseline(
        self,
        device_id: str,
        config_text: str,
        source: str = "running"
    ) -> ConfigSnapshot:
        """Capture a baseline config snapshot."""
        snapshot = ConfigSnapshot(
            device_id=device_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            config_hash=self._compute_hash(config_text),
            config_text=config_text,
            source=source
        )
        self._baseline_cache[device_id] = snapshot
        return snapshot
    
    def detect_drift(
        self,
        device_id: str,
        current_config: str,
        source: str = "running"
    ) -> Optional[ConfigDrift]:
        """Detect if current config differs from baseline."""
        baseline = self._baseline_cache.get(device_id)
        if not baseline:
            # No baseline, capture current and return None
            self.capture_baseline(device_id, current_config, source)
            return None
        
        current_hash = self._compute_hash(current_config)
        
        if current_hash == baseline.config_hash:
            return None  # No drift
        
        # Calculate simple diff summary
        diff = self._simple_diff(baseline.config_text, current_config)
        
        drift = ConfigDrift(
            device_id=device_id,
            detected_at=datetime.now(timezone.utc).isoformat(),
            severity="warning",
            drift_type="unauthorized_change",
            previous_hash=baseline.config_hash,
            current_hash=current_hash,
            diff_summary=diff
        )
        
        return drift
    
    def _simple_diff(self, old: str, new: str) -> str:
        """Generate simple line-based diff summary."""
        old_lines = set(old.splitlines())
        new_lines = set(new.splitlines())
        
        added = len(new_lines - old_lines)
        removed = len(old_lines - new_lines)
        
        return f"+{added} lines, -{removed} lines changed"
    
    def validate_against_golden(
        self,
        device_id: str,
        current_config: str,
        golden_config: str
    ) -> Dict[str, Any]:
        """Validate current config against golden/master config."""
        current_hash = self._compute_hash(current_config)
        golden_hash = self._compute_hash(golden_config)
        
        return {
            "device_id": device_id,
            "compliant": current_hash == golden_hash,
            "current_hash": current_hash,
            "golden_hash": golden_hash,
            "drift_detected": current_hash != golden_hash,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def get_drift_history(self, device_id: str, limit: int = 100) -> List[ConfigDrift]:
        """Get drift history for a device."""
        # This would typically query from storage
        # For now, return empty list - implementation depends on storage backend
        return []


class ConfigComplianceChecker:
    """Check config compliance against policy rules."""
    
    COMMON_POLICIES = {
        "no_default_passwords": {
            "pattern": r"password\s+\w+",
            "forbidden": ["password admin", "password cisco"],
        },
        "enable_nologin_for_services": {
            "pattern": r"service\s+\w+",
            "check": lambda cfg: "service nologin" in cfg.lower(),
        },
        "syslog_configured": {
            "pattern": r"logging\s+\d+\.\d+\.\d+\.\d+",
            "required": True,
        },
        "ntp_configured": {
            "pattern": r"ntp\s+server",
            "required": True,
        },
    }
    
    def __init__(self, policies: Optional[Dict[str, Any]] = None):
        self.policies = policies or self.COMMON_POLICIES
    
    def check_compliance(
        self,
        device_id: str,
        config_text: str
    ) -> Dict[str, Any]:
        """Check config against all policies."""
        results = {
            "device_id": device_id,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "overall_compliant": True,
            "violations": [],
            "passed": [],
        }
        
        for policy_name, policy in self.policies.items():
            passed = self._check_policy(config_text, policy)
            
            if not passed:
                results["overall_compliant"] = False
                results["violations"].append({
                    "policy": policy_name,
                    "severity": policy.get("severity", "warning"),
                    "description": policy.get("description", "Config policy violation"),
                })
            else:
                results["passed"].append(policy_name)
        
        return results
    
    def _check_policy(self, config_text: str, policy: Dict[str, Any]) -> bool:
        """Check a single policy against config."""
        import re
        
        # Check forbidden patterns
        if "forbidden" in policy:
            for forbidden in policy["forbidden"]:
                if forbidden.lower() in config_text.lower():
                    return False
        
        # Check required patterns
        if policy.get("required", False) and "pattern" in policy:
            if not re.search(policy["pattern"], config_text, re.IGNORECASE):
                return False
        
        # Check custom function
        if "check" in policy and callable(policy["check"]):
            return policy["check"](config_text)
        
        return True
