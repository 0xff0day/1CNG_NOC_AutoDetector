from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DetectedIssue:
    issue_type: str
    severity: str
    summary: str
    evidence: List[str]
    recommended_actions: List[str]


def _flatten_errors(scan_results: Dict[str, Any]) -> List[str]:
    msgs: List[str] = []
    for d in scan_results.get("devices", []) or []:
        errs = d.get("errors") or {}
        for k, v in (errs or {}).items():
            if v:
                msgs.append(f"{d.get('device_id')}:{k}: {v}")
    return msgs


def detect_issues_from_scan(scan_results: Dict[str, Any]) -> List[DetectedIssue]:
    issues: List[DetectedIssue] = []
    errors = _flatten_errors(scan_results)
    if not errors:
        return issues

    timeouts = [e for e in errors if "timed out" in str(e).lower()]
    auth = [e for e in errors if "auth" in str(e).lower() or "authentication" in str(e).lower()]
    refused = [e for e in errors if "refused" in str(e).lower()]

    if timeouts:
        issues.append(
            DetectedIssue(
                issue_type="collection_timeout",
                severity="critical",
                summary="SSH/Telnet collection timed out; device likely unreachable or blocked by firewall/ACL.",
                evidence=timeouts[:10],
                recommended_actions=[
                    "Verify IP/host is reachable from the NOC runner (ping/route).",
                    "Verify port is reachable (22 for SSH / 23 for Telnet).",
                    "Increase collector connect_timeout_sec/command_timeout_sec if links are slow.",
                ],
            )
        )

    if auth:
        issues.append(
            DetectedIssue(
                issue_type="auth_failure",
                severity="critical",
                summary="Authentication failures detected; credentials/enable secrets may be wrong.",
                evidence=auth[:10],
                recommended_actions=[
                    "Verify username/password or SSH key for the device.",
                    "If using credential_ref/vault_file, confirm the reference exists and is correct.",
                ],
            )
        )

    if refused:
        issues.append(
            DetectedIssue(
                issue_type="connection_refused",
                severity="critical",
                summary="TCP connection refused; SSH/Telnet service may be down or port incorrect.",
                evidence=refused[:10],
                recommended_actions=[
                    "Confirm SSH/Telnet is enabled on the device.",
                    "Confirm the transport port is open and not blocked by host firewall.",
                ],
            )
        )

    return issues


def summarize_scan_for_prompt(scan_results: Dict[str, Any], max_devices: int = 20) -> Dict[str, Any]:
    devices = []
    for d in (scan_results.get("devices") or [])[:max_devices]:
        devices.append(
            {
                "device_id": d.get("device_id"),
                "os": d.get("os"),
                "transport": d.get("transport"),
                "health_score": d.get("health_score"),
                "errors": d.get("errors"),
                "alerts": d.get("alerts"),
            }
        )

    return {
        "ts": scan_results.get("ts"),
        "device_count": len(scan_results.get("devices") or []),
        "devices": devices,
        "correlations": scan_results.get("correlations") or [],
    }
