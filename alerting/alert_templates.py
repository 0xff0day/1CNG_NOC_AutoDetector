from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AlertTemplate:
    name: str
    description: str
    format: str  # 'text', 'html', 'markdown', 'json'
    subject_template: str
    body_template: str
    variables: List[str]
    channels: List[str]  # 'email', 'telegram', 'slack', 'webhook', 'sms'


class AlertTemplateEngine:
    """Customizable alert notification templates."""
    
    DEFAULT_TEMPLATES = {
        "default": AlertTemplate(
            name="default",
            description="Default alert template",
            format="text",
            subject_template="[{severity}] {device_id}: {variable}",
            body_template="""Alert: {alert_id}
Device: {device_id} ({device_name})
Severity: {severity}
Variable: {variable}
Current Value: {value} {unit}
Threshold: {threshold}
Message: {message}
Time: {timestamp}

Recommended Actions:
{recommended_actions}
""",
            variables=["alert_id", "device_id", "device_name", "severity", "variable", 
                      "value", "unit", "threshold", "message", "timestamp", "recommended_actions"],
            channels=["email", "telegram"],
        ),
        "critical_exec": AlertTemplate(
            name="critical_exec",
            description="Critical alert for executive summary",
            format="text",
            subject_template="🚨 CRITICAL: {device_name} - {variable}",
            body_template="""CRITICAL ALERT
═══════════════════════════════════════

Service: {device_name}
Issue: {variable} is at {value}{unit} (threshold: {threshold})
Impact: {impact_assessment}
Time: {timestamp}

Immediate Action Required:
{immediate_action}

Contact: {escalation_contact}
═══════════════════════════════════════
""",
            variables=["device_name", "variable", "value", "unit", "threshold", 
                      "impact_assessment", "timestamp", "immediate_action", "escalation_contact"],
            channels=["email", "sms", "voice_call"],
        ),
        "compact_sms": AlertTemplate(
            name="compact_sms",
            description="Compact SMS-friendly format",
            format="text",
            subject_template="",
            body_template="{device_id}: {variable}={value}{unit} ({severity}) - {short_message}",
            variables=["device_id", "variable", "value", "unit", "severity", "short_message"],
            channels=["sms"],
        ),
        "slack_formatted": AlertTemplate(
            name="slack_formatted",
            description="Slack-compatible markdown format",
            format="markdown",
            subject_template="",
            body_template="""*[{severity}] Alert on {device_name}*

🔔 *{variable}* is at *{value}{unit}* (threshold: {threshold}{unit})

• Device: `{device_id}`
• Time: {timestamp}
• Status: {status}

*Recommended Actions:*
{recommended_actions}

<{dashboard_url}|View in Dashboard>
""",
            variables=["severity", "device_name", "variable", "value", "unit", 
                      "threshold", "device_id", "timestamp", "status", 
                      "recommended_actions", "dashboard_url"],
            channels=["slack", "webhook"],
        ),
        "html_email": AlertTemplate(
            name="html_email",
            description="Rich HTML email format",
            format="html",
            subject_template="[{severity}] Network Alert: {device_name}",
            body_template="""<!DOCTYPE html>
<html>
<head>
<style>
.critical {{ color: #d32f2f; }}
.warning {{ color: #f57c00; }}
.info {{ color: #1976d2; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #f5f5f5; }}
</style>
</head>
<body>
<h2 class="{severity.lower()}">{severity} Alert</h2>
<table>
<tr><th>Device</th><td>{device_name} ({device_id})</td></tr>
<tr><th>Variable</th><td>{variable}</td></tr>
<tr><th>Current Value</th><td><strong>{value} {unit}</strong></td></tr>
<tr><th>Threshold</th><td>{threshold} {unit}</td></tr>
<tr><th>Time</th><td>{timestamp}</td></tr>
<tr><th>Message</th><td>{message}</td></tr>
</table>
<p><strong>Recommended Actions:</strong></p>
<p>{recommended_actions}</p>
<p><a href="{dashboard_url}">View in NOC Dashboard</a></p>
</body>
</html>""",
            variables=["severity", "device_name", "device_id", "variable", "value", 
                      "unit", "threshold", "timestamp", "message", 
                      "recommended_actions", "dashboard_url"],
            channels=["email"],
        ),
        "json_api": AlertTemplate(
            name="json_api",
            description="JSON format for API/webhook consumption",
            format="json",
            subject_template="",
            body_template='''{
  "alert_id": "{alert_id}",
  "severity": "{severity}",
  "device": {
    "id": "{device_id}",
    "name": "{device_name}",
    "type": "{device_type}"
  },
  "metric": {
    "name": "{variable}",
    "value": {value},
    "unit": "{unit}",
    "threshold": {threshold}
  },
  "timestamp": "{timestamp}",
  "message": "{message}",
  "context": {
    "location": "{location}",
    "tags": {tags_json}
  }
}''',
            variables=["alert_id", "severity", "device_id", "device_name", "device_type",
                      "variable", "value", "unit", "threshold", "timestamp", 
                      "message", "location", "tags_json"],
            channels=["webhook", "api"],
        ),
    }
    
    def __init__(self):
        self.templates: Dict[str, AlertTemplate] = dict(self.DEFAULT_TEMPLATES)
        self.custom_templates: Dict[str, AlertTemplate] = {}
    
    def register_template(self, template: AlertTemplate):
        """Register a custom template."""
        self.custom_templates[template.name] = template
        self.templates[template.name] = template
    
    def get_template(self, name: str) -> Optional[AlertTemplate]:
        """Get a template by name."""
        return self.templates.get(name)
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "format": t.format,
                "channels": t.channels,
                "is_custom": t.name in self.custom_templates,
            }
            for t in self.templates.values()
        ]
    
    def render_alert(
        self,
        template_name: str,
        alert_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """Render an alert using a template."""
        template = self.get_template(template_name)
        if not template:
            template = self.templates["default"]
        
        # Prepare variables with defaults
        variables = {
            "alert_id": alert_data.get("id", "UNKNOWN"),
            "device_id": alert_data.get("device_id", "UNKNOWN"),
            "device_name": alert_data.get("device_name", alert_data.get("device_id", "UNKNOWN")),
            "device_type": alert_data.get("device_type", "unknown"),
            "severity": alert_data.get("severity", "info"),
            "variable": alert_data.get("variable", "unknown"),
            "value": alert_data.get("value", "N/A"),
            "unit": alert_data.get("unit", ""),
            "threshold": alert_data.get("threshold", "N/A"),
            "message": alert_data.get("message", ""),
            "timestamp": alert_data.get("ts", datetime.now(timezone.utc).isoformat()),
            "status": alert_data.get("status", "active"),
            "short_message": alert_data.get("message", "")[:100],
            "recommended_actions": "\n".join(alert_data.get("recommended_actions", ["Check device status"])),
            "immediate_action": alert_data.get("immediate_action", "Contact NOC team"),
            "escalation_contact": alert_data.get("escalation_contact", "oncall@noc.local"),
            "impact_assessment": alert_data.get("impact", "Unknown impact"),
            "dashboard_url": alert_data.get("dashboard_url", "https://noc.local/dashboard"),
            "location": alert_data.get("location", "Unknown"),
            "tags_json": json.dumps(alert_data.get("tags", [])),
        }
        
        # Render subject and body
        subject = self._render_template(template.subject_template, variables)
        body = self._render_template(template.body_template, variables)
        
        return {
            "template": template.name,
            "format": template.format,
            "subject": subject,
            "body": body,
            "channels": template.channels,
        }
    
    def _render_template(self, template_str: str, variables: Dict[str, Any]) -> str:
        """Render a template string with variables."""
        result = template_str
        
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        
        # Remove any remaining placeholders
        result = re.sub(r'\{[^}]+\}', 'N/A', result)
        
        return result
    
    def select_template_for_alert(
        self,
        alert_data: Dict[str, Any],
        channel: str
    ) -> str:
        """Auto-select best template for alert and channel."""
        severity = alert_data.get("severity", "info")
        
        # Critical alerts get executive template for high-priority channels
        if severity == "critical" and channel in ["email", "voice_call"]:
            return "critical_exec"
        
        # SMS gets compact format
        if channel == "sms":
            return "compact_sms"
        
        # Slack gets formatted template
        if channel == "slack":
            return "slack_formatted"
        
        # Webhook gets JSON
        if channel == "webhook":
            return "json_api"
        
        # Email gets HTML if supported
        if channel == "email":
            return "html_email"
        
        # Default fallback
        return "default"


class TemplateVariableValidator:
    """Validate template variables."""
    
    REQUIRED_VARIABLES = ["device_id", "severity", "variable"]
    
    @classmethod
    def validate_template(cls, template: AlertTemplate) -> List[str]:
        """Validate a template and return list of errors."""
        errors = []
        
        # Check required variables are defined
        for req in cls.REQUIRED_VARIABLES:
            if req not in template.variables:
                errors.append(f"Missing required variable: {req}")
        
        # Check for template syntax errors
        try:
            # Look for unmatched braces
            open_count = template.body_template.count("{")
            close_count = template.body_template.count("}")
            
            if open_count != close_count:
                errors.append(f"Mismatched braces: {open_count} open, {close_count} close")
            
            # Check all braces have matching pairs
            depth = 0
            for char in template.body_template:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth < 0:
                        errors.append("Unmatched closing brace")
                        break
            
            if depth > 0:
                errors.append("Unmatched opening brace")
                
        except Exception as e:
            errors.append(f"Template validation error: {str(e)}")
        
        return errors
