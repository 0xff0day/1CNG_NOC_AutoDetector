"""
NOC-Specific Training Data Builder

Generates high-quality training examples from NOC operations data,
including alert patterns, device outputs, and troubleshooting scenarios.
"""

from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from . import TrainingExample

logger = logging.getLogger(__name__)


@dataclass
class NOCTrainingTemplate:
    """Template for generating NOC training examples."""
    category: str
    instruction_template: str
    input_template: str
    output_template: str
    variables: List[str]


class NOCTrainingDataBuilder:
    """
    Builds training data specifically for NOC operations.
    
    Generates diverse examples covering:
    - Alert analysis and root cause identification
    - Device troubleshooting
    - Network diagnostics
    - Incident response
    - Capacity planning
    """
    
    # Device types for realistic scenarios
    DEVICE_TYPES = [
        "cisco_ios", "cisco_nxos", "junos", "arista_eos",
        "fortios", "paloalto", "mikrotik", "huawei_vrp",
        "arubaos", "dell_os10",
        "ubuntu", "centos", "rhel", "windows_server",
        "vmware_esxi", "proxmox", "hyperv", "kvm"
    ]
    
    # Common issues for training scenarios
    ISSUE_CATEGORIES = {
        "cpu_high": {
            "symptoms": ["High CPU utilization", "Process exhaustion", "Control plane overload"],
            "causes": ["Traffic surge", "Routing instability", "ACL processing", "Debug enabled"],
            "solutions": ["Enable CoPP", "Optimize ACLs", "Disable debug", "Upgrade hardware"]
        },
        "memory_high": {
            "symptoms": ["Memory utilization critical", "OOM warnings", "Buffer exhaustion"],
            "causes": ["Memory leak", "BGP table growth", "Large routing table", "Insufficient RAM"],
            "solutions": ["Restart process", "Increase memory", "Optimize routing", "Schedule maintenance"]
        },
        "interface_down": {
            "symptoms": ["Interface administratively down", "Link down", "No carrier"],
            "causes": ["Cable fault", "Port disabled", "Remote end down", "Transceiver failure"],
            "solutions": ["Check cable", "Enable port", "Replace SFP", "Check remote end"]
        },
        "bgp_flap": {
            "symptoms": ["BGP neighbor flapping", "Route instability", "Prefix churn"],
            "causes": ["Link instability", "MTU mismatch", "AS path issues", "Timer misconfig"],
            "solutions": ["Stabilize link", "Fix MTU", "Check AS path", "Adjust timers"]
        },
        "disk_full": {
            "symptoms": ["Disk space critical", "Log partition full", "Unable to write"],
            "causes": ["Log accumulation", "Core dumps", "Large files", "No rotation"],
            "solutions": ["Clear logs", "Enable rotation", "Add storage", "Delete old files"]
        },
        "power_issue": {
            "symptoms": ["Power supply failure", "Redundant power lost", "Voltage anomaly"],
            "causes": ["PSU failure", "Power outage", "Cable fault", "Overload"],
            "solutions": ["Replace PSU", "Check power feed", "Redistribute load", "Add capacity"]
        },
        "temperature": {
            "symptoms": ["High temperature alarm", "Thermal warning", "Fan failure"],
            "causes": ["Cooling failure", "Airflow blocked", "Ambient high", "Dust buildup"],
            "solutions": ["Clean fans", "Check airflow", "Lower ambient", "Replace fans"]
        }
    }
    
    def __init__(self):
        self.templates = self._build_templates()
        self.generated_examples: List[TrainingExample] = []
    
    def _build_templates(self) -> List[NOCTrainingTemplate]:
        """Build training templates for various NOC scenarios."""
        templates = []
        
        # Alert Analysis Template
        templates.append(NOCTrainingTemplate(
            category="alert_analysis",
            instruction_template="Analyze the following network alert and identify the root cause, impact, and recommended actions.",
            input_template="""Device: {device_name} ({device_type})
Time: {timestamp}
Alert: {alert_message}
Severity: {severity}
Metrics: {metrics}
Recent Changes: {changes}""",
            output_template="""## Root Cause Analysis

**Primary Issue**: {issue_type}
**Confidence**: {confidence}%

**Root Cause**: {root_cause}

**Impact Assessment**:
- Affected Services: {affected_services}
- User Impact: {user_impact}
- Duration: {duration}

**Recommended Actions**:
1. {action_1}
2. {action_2}
3. {action_3}

**Prevention**:
{prevention}

**Ticket Reference**: AUTO-{ticket_id}""",
            variables=["device_name", "device_type", "timestamp", "alert_message", "severity", 
                      "metrics", "changes", "issue_type", "confidence", "root_cause",
                      "affected_services", "user_impact", "duration", "action_1", "action_2",
                      "action_3", "prevention", "ticket_id"]
        ))
        
        # Troubleshooting Template
        templates.append(NOCTrainingTemplate(
            category="troubleshooting",
            instruction_template="Troubleshoot the following network issue. Provide diagnostic steps and resolution.",
            input_template="""Issue: {issue_description}
Device: {device_type} - {device_name}
Symptoms: {symptoms}
CLI Output:
```
{cli_output}
```""",
            output_template="""## Troubleshooting Steps

**Issue Classification**: {issue_category}

**Diagnostic Steps**:
1. {diag_1}
2. {diag_2}
3. {diag_3}

**Analysis**:
{analysis}

**Resolution**:
{resolution}

**Verification**:
{verification}

**Time to Resolution**: {ttc} minutes""",
            variables=["issue_description", "device_type", "device_name", "symptoms", 
                      "cli_output", "issue_category", "diag_1", "diag_2", "diag_3",
                      "analysis", "resolution", "verification", "ttc"]
        ))
        
        # Correlation Template
        templates.append(NOCTrainingTemplate(
            category="correlation",
            instruction_template="Analyze the correlated alerts across multiple devices and identify the common root cause.",
            input_template="""Correlated Incident ID: {incident_id}
Time Window: {time_window}

Alerts:
{alerts_list}

Network Topology:
{topology}""",
            output_template="""## Correlation Analysis

**Common Root Cause**: {root_cause}
**Correlation Confidence**: {confidence}%

**Impact Chain**:
{impact_chain}

**Primary Affected Device**: {primary_device}
**Secondary Impact**: {secondary_impact}

**Resolution Strategy**:
{resolution_strategy}

**Estimated Resolution Time**: {ert} minutes""",
            variables=["incident_id", "time_window", "alerts_list", "topology",
                      "root_cause", "confidence", "impact_chain", "primary_device",
                      "secondary_impact", "resolution_strategy", "ert"]
        ))
        
        # Capacity Planning Template
        templates.append(NOCTrainingTemplate(
            category="capacity_planning",
            instruction_template="Analyze resource utilization trends and predict when capacity limits will be reached.",
            input_template="""Resource: {resource_type}
Current Utilization: {current}%
Trend: {trend}% per {period}
Threshold: {threshold}%
Historical Data: {history}""",
            output_template="""## Capacity Forecast

**Current State**: {current}% utilization
**Growth Rate**: {trend}% per {period}

**Prediction**:
- Will reach {threshold}% in: {time_to_threshold}
- Critical threshold (90%) in: {time_to_critical}

**Recommendations**:
1. {rec_1}
2. {rec_2}
3. {rec_3}

**Planning Actions**:
{planning_actions}""",
            variables=["resource_type", "current", "trend", "period", "threshold",
                      "history", "time_to_threshold", "time_to_critical", "rec_1",
                      "rec_2", "rec_3", "planning_actions"]
        ))
        
        # Security Incident Template
        templates.append(NOCTrainingTemplate(
            category="security",
            instruction_template="Analyze the potential security incident and recommend immediate containment actions.",
            input_template="""Alert Type: {alert_type}
Source: {source_ip}
Target: {target_resource}
Pattern: {attack_pattern}
Logs: {log_excerpt}""",
            output_template="""## Security Analysis

**Threat Classification**: {threat_type}
**Severity**: {severity}
**Confidence**: {confidence}%

**Attack Details**:
{attack_details}

**Immediate Actions**:
1. {action_1} [URGENT]
2. {action_2} [HIGH]
3. {action_3} [MEDIUM]

**Investigation Steps**:
{investigation}

**Escalation**: {escalation}""",
            variables=["alert_type", "source_ip", "target_resource", "attack_pattern",
                      "log_excerpt", "threat_type", "severity", "confidence",
                      "attack_details", "action_1", "action_2", "action_3",
                      "investigation", "escalation"]
        ))
        
        return templates
    
    def generate_examples(self, count: int = 100) -> List[TrainingExample]:
        """Generate N training examples."""
        examples = []
        
        for _ in range(count):
            template = random.choice(self.templates)
            example = self._generate_from_template(template)
            examples.append(example)
        
        self.generated_examples.extend(examples)
        logger.info(f"Generated {len(examples)} training examples")
        return examples
    
    def _generate_from_template(self, template: NOCTrainingTemplate) -> TrainingExample:
        """Generate a single training example from a template."""
        variables = {}
        
        # Common variables
        device_type = random.choice(self.DEVICE_TYPES)
        device_name = f"{device_type}-{(random.randint(1, 99)):02d}"
        
        variables["device_name"] = device_name
        variables["device_type"] = device_type
        variables["timestamp"] = datetime.now().isoformat()
        variables["ticket_id"] = f"{random.randint(10000, 99999)}"
        variables["confidence"] = random.randint(75, 98)
        
        # Issue-specific variables
        issue_category = random.choice(list(self.ISSUE_CATEGORIES.keys()))
        issue_data = self.ISSUE_CATEGORIES[issue_category]
        
        variables["issue_type"] = issue_category.replace("_", " ").title()
        variables["root_cause"] = random.choice(issue_data["causes"])
        
        symptoms = random.sample(issue_data["symptoms"], k=min(2, len(issue_data["symptoms"])))
        variables["symptoms"] = ", ".join(symptoms)
        
        solutions = random.sample(issue_data["solutions"], k=min(3, len(issue_data["solutions"])))
        variables["action_1"] = solutions[0]
        variables["action_2"] = solutions[1] if len(solutions) > 1 else "Monitor for recurrence"
        variables["action_3"] = solutions[2] if len(solutions) > 2 else "Document in knowledge base"
        
        # Generate alert message
        severity = random.choice(["warning", "critical", "major"])
        metric_value = random.randint(85, 99)
        variables["severity"] = severity.upper()
        variables["alert_message"] = f"{issue_category.replace('_', ' ').title()} - {metric_value}% utilization"
        
        # Metrics
        variables["metrics"] = f"CPU: {random.randint(10, 95)}%, Memory: {random.randint(20, 90)}%, Disk: {random.randint(30, 85)}%"
        
        # Changes
        variables["changes"] = random.choice([
            "None in last 24h",
            "Config change 2h ago",
            "Software update yesterday",
            "New peer added 6h ago"
        ])
        
        # Impact
        variables["affected_services"] = random.choice([
            "Core routing",
            "Edge connectivity", 
            "Management access",
            "VPN services"
        ])
        variables["user_impact"] = random.choice(["Low", "Medium", "High", "Critical"])
        variables["duration"] = f"{random.randint(5, 120)} minutes"
        
        # Prevention
        variables["prevention"] = f"Implement monitoring for {issue_category.replace('_', ' ')} and set proactive thresholds at 80%"
        
        # CLI output (simplified)
        variables["cli_output"] = self._generate_cli_output(device_type, issue_category)
        
        # Other fields
        variables["issue_description"] = f"{issue_category.replace('_', ' ').title()} on {device_name}"
        variables["issue_category"] = issue_category
        
        variables["diag_1"] = f"Check current {issue_category.replace('_', ' ')} status"
        variables["diag_2"] = "Review recent configuration changes"
        variables["diag_3"] = "Analyze historical trends"
        
        variables["analysis"] = f"The {issue_category.replace('_', ' ')} issue is likely caused by {variables['root_cause']}. Pattern matches known issue #KB-{random.randint(1000, 9999)}."
        variables["resolution"] = f"Apply fix: {variables['action_1']}. This should resolve the issue within {random.randint(2, 10)} minutes."
        variables["verification"] = f"Monitor {issue_category.replace('_', ' ')} metrics for 15 minutes to confirm resolution."
        variables["ttc"] = str(random.randint(10, 45))
        
        # Capacity planning variables
        variables["resource_type"] = random.choice(["CPU", "Memory", "Disk", "Bandwidth"])
        variables["current"] = str(random.randint(60, 85))
        variables["trend"] = str(random.randint(2, 8))
        variables["period"] = random.choice(["day", "week", "month"])
        variables["threshold"] = "90"
        variables["history"] = f"Past 30 days: avg {int(variables['current'])-10}%, peak {int(variables['current'])+5}%"
        variables["time_to_threshold"] = f"{(90 - int(variables['current'])) // int(variables['trend'])} {variables['period']}s"
        variables["time_to_critical"] = f"{(95 - int(variables['current'])) // int(variables['trend'])} {variables['period']}s"
        variables["rec_1"] = f"Add capacity before reaching 90% {variables['resource_type']} utilization"
        variables["rec_2"] = "Implement predictive scaling"
        variables["rec_3"] = "Review resource allocation policies"
        variables["planning_actions"] = f"Schedule capacity addition within {variables['time_to_threshold']}"
        
        # Security variables
        variables["alert_type"] = random.choice(["Brute force", "DDoS", "Port scan", "Anomalous traffic"])
        variables["source_ip"] = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
        variables["target_resource"] = random.choice(["Web server", "SSH gateway", "VPN concentrator", "DNS server"])
        variables["attack_pattern"] = random.choice(["Multiple failed logins", "SYN flood", "Unusual port access", "Volume spike"])
        variables["log_excerpt"] = f"Failed auth from {variables['source_ip']}: {random.randint(50, 500)} attempts"
        variables["threat_type"] = variables["alert_type"]
        variables["severity"] = random.choice(["HIGH", "CRITICAL"])
        variables["attack_details"] = f"Detected {variables['attack_pattern']} targeting {variables['target_resource']}"
        variables["action_1"] = f"Block IP {variables['source_ip']} at firewall"
        variables["action_2"] = f"Enable enhanced logging on {variables['target_resource']}"
        variables["action_3"] = "Notify security team"
        variables["investigation"] = "Review access logs for compromise indicators"
        variables["escalation"] = "SOC team notified"
        
        # Build input and output
        instruction = template.instruction_template
        input_text = template.input_template.format(**{k: variables.get(k, "N/A") for k in template.variables})
        output_text = template.output_template.format(**{k: variables.get(k, "N/A") for k in template.variables})
        
        return TrainingExample(
            instruction=instruction,
            input_text=input_text,
            output_text=output_text,
            system_prompt="You are an expert NOC AI assistant with deep knowledge of network operations, troubleshooting, and incident response. Provide accurate, actionable analysis.",
            metadata={
                "category": template.category,
                "device_type": device_type,
                "issue_category": issue_category,
                "generated_at": datetime.now().isoformat(),
            }
        )
    
    def _generate_cli_output(self, device_type: str, issue: str) -> str:
        """Generate realistic CLI output based on device type and issue."""
        if "cisco" in device_type:
            if "cpu" in issue:
                return "CPU utilization for five seconds: 95%/92%; one minute: 89%; five minutes: 87%"
            elif "memory" in issue:
                return "Processor Pool Total:  876144 Used:  823456 Free:  52688"
            else:
                return "Interface Status: up/down, line protocol is down"
        elif "junos" in device_type:
            return "CPU utilization: 94%, Memory utilization: 78%"
        elif "linux" in device_type or device_type in ["ubuntu", "centos", "rhel"]:
            return "load average: 8.52, 7.83, 6.21"
        else:
            return f"Status: {issue.replace('_', ' ').title()} detected\nSeverity: HIGH"
    
    def export_to_jsonl(self, filepath: str) -> int:
        """Export generated examples to JSONL file."""
        count = 0
        with open(filepath, 'w') as f:
            for example in self.generated_examples:
                f.write(json.dumps(example.to_dict()) + '\n')
                count += 1
        logger.info(f"Exported {count} examples to {filepath}")
        return count
    
    def export_alpaca_format(self, filepath: str) -> int:
        """Export in Alpaca training format."""
        count = 0
        with open(filepath, 'w') as f:
            for example in self.generated_examples:
                alpaca_format = {
                    "instruction": example.instruction + "\n\n" + example.input_text,
                    "input": "",
                    "output": example.output_text,
                    "system": example.system_prompt,
                }
                f.write(json.dumps(alpaca_format) + '\n')
                count += 1
        logger.info(f"Exported {count} examples in Alpaca format to {filepath}")
        return count
    
    def export_sharegpt_format(self, filepath: str) -> int:
        """Export in ShareGPT format."""
        count = 0
        with open(filepath, 'w') as f:
            for example in self.generated_examples:
                sharegpt_format = {
                    "conversations": [
                        {"from": "system", "value": example.system_prompt},
                        {"from": "human", "value": example.instruction + "\n\n" + example.input_text},
                        {"from": "gpt", "value": example.output_text}
                    ]
                }
                f.write(json.dumps(sharegpt_format) + '\n')
                count += 1
        logger.info(f"Exported {count} examples in ShareGPT format to {filepath}")
        return count
    
    @classmethod
    def create_dataset(
        cls,
        output_dir: str,
        train_count: int = 1000,
        eval_count: int = 200,
        formats: List[str] = None
    ) -> Dict[str, str]:
        """
        Create a complete NOC training dataset.
        
        Returns paths to generated files.
        """
        if formats is None:
            formats = ["jsonl", "alpaca"]
        
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        builder = cls()
        
        # Generate training data
        train_examples = builder.generate_examples(train_count)
        
        paths = {}
        
        # Export in requested formats
        if "jsonl" in formats:
            paths["train_jsonl"] = os.path.join(output_dir, "train.jsonl")
            builder.export_to_jsonl(paths["train_jsonl"])
        
        if "alpaca" in formats:
            paths["train_alpaca"] = os.path.join(output_dir, "train_alpaca.jsonl")
            builder.export_alpaca_format(paths["train_alpaca"])
        
        if "sharegpt" in formats:
            paths["train_sharegpt"] = os.path.join(output_dir, "train_sharegpt.jsonl")
            builder.export_sharegpt_format(paths["train_sharegpt"])
        
        # Generate eval data
        builder.generated_examples = []  # Clear for eval
        eval_examples = builder.generate_examples(eval_count)
        
        if "jsonl" in formats:
            paths["eval_jsonl"] = os.path.join(output_dir, "eval.jsonl")
            builder.export_to_jsonl(paths["eval_jsonl"])
        
        # Create dataset info
        info = {
            "name": "NOC Operations Training Dataset",
            "description": "Synthetic training data for NOC AI assistant",
            "version": "1.0",
            "train_examples": train_count,
            "eval_examples": eval_count,
            "categories": list(builder.ISSUE_CATEGORIES.keys()),
            "device_types": builder.DEVICE_TYPES,
            "generated_at": datetime.now().isoformat(),
            "files": paths,
        }
        
        info_path = os.path.join(output_dir, "dataset_info.json")
        with open(info_path, 'w') as f:
            json.dump(info, f, indent=2)
        
        paths["info"] = info_path
        
        logger.info(f"Dataset created at {output_dir}")
        return paths
