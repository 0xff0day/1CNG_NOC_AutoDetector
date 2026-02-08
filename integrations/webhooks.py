from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests


class WebhookDispatcher:
    """Dispatch events to external webhooks."""
    
    def __init__(self, timeout_sec: float = 10.0):
        self.timeout_sec = timeout_sec
        self.webhooks: Dict[str, Dict[str, Any]] = {}
        self.delivery_log: List[Dict[str, Any]] = []
    
    def register_webhook(
        self,
        name: str,
        url: str,
        events: List[str],
        headers: Optional[Dict[str, str]] = None,
        secret: Optional[str] = None,
        retry_count: int = 3
    ):
        """Register a webhook endpoint."""
        self.webhooks[name] = {
            "name": name,
            "url": url,
            "events": events,
            "headers": headers or {},
            "secret": secret,
            "retry_count": retry_count,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "deliveries": 0,
            "failures": 0,
        }
    
    def unregister_webhook(self, name: str) -> bool:
        """Unregister a webhook."""
        if name in self.webhooks:
            del self.webhooks[name]
            return True
        return False
    
    def dispatch(
        self,
        event_type: str,
        payload: Dict[str, Any],
        webhook_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Dispatch event to registered webhooks."""
        results = []
        
        # Determine which webhooks to call
        targets = []
        if webhook_name:
            if webhook_name in self.webhooks:
                targets = [self.webhooks[webhook_name]]
        else:
            targets = [
                w for w in self.webhooks.values()
                if event_type in w["events"] or "*" in w["events"]
            ]
        
        for webhook in targets:
            result = self._send_to_webhook(webhook, event_type, payload)
            results.append(result)
            
            # Log delivery
            self.delivery_log.append({
                "webhook": webhook["name"],
                "event": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": result["success"],
                "status_code": result.get("status_code"),
                "error": result.get("error"),
            })
            
            # Update stats
            webhook["deliveries"] += 1
            if not result["success"]:
                webhook["failures"] += 1
        
        return results
    
    def _send_to_webhook(
        self,
        webhook: Dict[str, Any],
        event_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send payload to a single webhook."""
        url = webhook["url"]
        headers = dict(webhook["headers"])
        
        # Add content-type if not set
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        
        # Sign payload if secret is configured
        if webhook.get("secret"):
            signature = self._sign_payload(payload, webhook["secret"])
            headers["X-Webhook-Signature"] = signature
        
        # Add event type header
        headers["X-Event-Type"] = event_type
        
        last_error = None
        
        for attempt in range(webhook["retry_count"]):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_sec
                )
                
                if response.status_code < 400:
                    return {
                        "success": True,
                        "webhook": webhook["name"],
                        "status_code": response.status_code,
                        "attempt": attempt + 1,
                    }
                else:
                    last_error = f"HTTP {response.status_code}"
                    
            except requests.exceptions.Timeout:
                last_error = "Timeout"
            except Exception as e:
                last_error = str(e)
        
        return {
            "success": False,
            "webhook": webhook["name"],
            "error": last_error,
            "attempts": webhook["retry_count"],
        }
    
    def _sign_payload(self, payload: Dict[str, Any], secret: str) -> str:
        """Sign payload with HMAC-SHA256."""
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    def get_webhook_stats(self) -> Dict[str, Any]:
        """Get webhook delivery statistics."""
        return {
            "webhooks": [
                {
                    "name": w["name"],
                    "url": w["url"],
                    "events": w["events"],
                    "deliveries": w["deliveries"],
                    "failures": w["failures"],
                    "success_rate": (
                        (w["deliveries"] - w["failures"]) / w["deliveries"]
                        if w["deliveries"] > 0 else 1.0
                    ),
                }
                for w in self.webhooks.values()
            ],
            "recent_deliveries": self.delivery_log[-100:],
        }


class WebhookEventBuilder:
    """Build standardized webhook event payloads."""
    
    EVENT_SCHEMAS = {
        "alert.created": {
            "title": "Alert Created",
            "payload_fields": [
                "alert_id", "device_id", "severity", "message",
                "variable", "value", "threshold", "timestamp"
            ],
        },
        "alert.acknowledged": {
            "title": "Alert Acknowledged",
            "payload_fields": [
                "alert_id", "acknowledged_by", "acknowledged_at", "notes"
            ],
        },
        "alert.resolved": {
            "title": "Alert Resolved",
            "payload_fields": [
                "alert_id", "resolved_at", "resolution_type"
            ],
        },
        "device.discovered": {
            "title": "Device Discovered",
            "payload_fields": [
                "device_id", "host", "os_detected", "confidence", "discovered_at"
            ],
        },
        "device.offline": {
            "title": "Device Offline",
            "payload_fields": [
                "device_id", "host", "last_seen", "offline_since"
            ],
        },
        "device.online": {
            "title": "Device Online",
            "payload_fields": [
                "device_id", "host", "offline_duration", "online_at"
            ],
        },
        "report.generated": {
            "title": "Report Generated",
            "payload_fields": [
                "report_id", "report_type", "format", "file_path", "generated_at"
            ],
        },
        "config.drift": {
            "title": "Configuration Drift Detected",
            "payload_fields": [
                "device_id", "previous_hash", "current_hash", "drift_type"
            ],
        },
    }
    
    def build_event(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a standardized event payload."""
        schema = self.EVENT_SCHEMAS.get(event_type, {})
        
        payload = {
            "event_type": event_type,
            "event_title": schema.get("title", event_type),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {k: v for k, v in data.items() if k in schema.get("payload_fields", [])},
        }
        
        return payload
    
    def get_available_events(self) -> List[Dict[str, str]]:
        """Get list of available event types."""
        return [
            {"type": k, "title": v["title"]}
            for k, v in self.EVENT_SCHEMAS.items()
        ]
