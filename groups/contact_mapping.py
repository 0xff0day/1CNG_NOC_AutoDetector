"""
Contact Group Mapping

Maps device groups to contact groups for alert routing.
Defines who should be notified for different types of alerts.
"""

from __future__ import annotations

from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ContactMethod(Enum):
    """Available contact methods."""
    TELEGRAM = "telegram"
    EMAIL = "email"
    SMS = "sms"
    VOICE = "voice"
    PAGER = "pager"
    SLACK = "slack"
    WEBHOOK = "webhook"


@dataclass
class Contact:
    """Contact person definition."""
    id: str
    name: str
    methods: Dict[ContactMethod, str]  # method -> address
    role: str = ""
    timezone: str = "UTC"
    on_call: bool = True
    escalation_level: int = 1
    metadata: Dict = field(default_factory=dict)


@dataclass
class ContactGroup:
    """Group of contacts for notification."""
    name: str
    description: str = ""
    contacts: List[str] = field(default_factory=list)  # contact IDs
    methods: List[ContactMethod] = field(default_factory=list)
    schedule: Optional[str] = None  # on-call schedule name
    escalation_delay_minutes: int = 15


class ContactGroupManager:
    """
    Manages contact groups and device-to-contact mappings.
    
    Routes alerts to appropriate contacts based on:
    - Device group membership
    - Alert severity
    - Time of day
    - Escalation policies
    """
    
    def __init__(self):
        self.contacts: Dict[str, Contact] = {}
        self.contact_groups: Dict[str, ContactGroup] = {}
        self.device_group_mappings: Dict[str, List[str]] = {}  # device_group -> contact_groups
        self.severity_mappings: Dict[str, List[str]] = {}  # severity -> contact_groups
    
    def add_contact(self, contact: Contact) -> None:
        """Add a contact person."""
        self.contacts[contact.id] = contact
        logger.info(f"Added contact: {contact.name}")
    
    def create_contact_group(
        self,
        name: str,
        description: str = "",
        methods: Optional[List[ContactMethod]] = None
    ) -> ContactGroup:
        """Create a contact group."""
        group = ContactGroup(
            name=name,
            description=description,
            methods=methods or [ContactMethod.TELEGRAM]
        )
        self.contact_groups[name] = group
        return group
    
    def add_contact_to_group(self, contact_id: str, group_name: str) -> bool:
        """Add contact to a group."""
        if group_name not in self.contact_groups:
            return False
        if contact_id not in self.contacts:
            return False
        
        group = self.contact_groups[group_name]
        if contact_id not in group.contacts:
            group.contacts.append(contact_id)
        
        return True
    
    def map_device_group_to_contacts(
        self,
        device_group: str,
        contact_groups: List[str]
    ) -> None:
        """
        Map device group to contact groups.
        
        When devices in this group have alerts,
        these contact groups will be notified.
        """
        self.device_group_mappings[device_group] = contact_groups
        logger.info(f"Mapped device group '{device_group}' to contacts: {contact_groups}")
    
    def map_severity_to_contacts(
        self,
        severity: str,
        contact_groups: List[str]
    ) -> None:
        """
        Map severity level to contact groups.
        
        Alerts of this severity will notify these groups
        regardless of device group.
        """
        self.severity_mappings[severity] = contact_groups
        logger.info(f"Mapped severity '{severity}' to contacts: {contact_groups}")
    
    def get_contacts_for_alert(
        self,
        device_id: str,
        device_groups: List[str],
        severity: str,
        alert_type: Optional[str] = None
    ) -> Dict[ContactMethod, List[str]]:
        """
        Determine which contacts to notify for an alert.
        
        Args:
            device_id: Device with issue
            device_groups: Groups the device belongs to
            severity: Alert severity
            alert_type: Type of alert
        
        Returns:
            Dict mapping method to list of addresses
        """
        contact_groups_to_notify: Set[str] = set()
        
        # Add from device group mappings
        for dg in device_groups:
            if dg in self.device_group_mappings:
                contact_groups_to_notify.update(self.device_group_mappings[dg])
        
        # Add from severity mappings
        if severity in self.severity_mappings:
            contact_groups_to_notify.update(self.severity_mappings[severity])
        
        # Collect contacts
        method_addresses: Dict[ContactMethod, Set[str]] = {
            m: set() for m in ContactMethod
        }
        
        for cg_name in contact_groups_to_notify:
            if cg_name not in self.contact_groups:
                continue
            
            cg = self.contact_groups[cg_name]
            
            for contact_id in cg.contacts:
                if contact_id not in self.contacts:
                    continue
                
                contact = self.contacts[contact_id]
                
                # Check if contact is on-call
                if not contact.on_call:
                    continue
                
                # Add addresses for preferred methods
                for method in cg.methods:
                    if method in contact.methods:
                        method_addresses[method].add(contact.methods[method])
        
        return {
            method: list(addresses)
            for method, addresses in method_addresses.items()
            if addresses
        }
    
    def get_escalation_contacts(
        self,
        original_contacts: Dict[ContactMethod, List[str]],
        escalation_level: int
    ) -> Dict[ContactMethod, List[str]]:
        """
        Get next level escalation contacts.
        
        Args:
            original_contacts: Current notification targets
            escalation_level: Escalation level (2, 3, etc.)
        
        Returns:
            Contacts for this escalation level
        """
        result: Dict[ContactMethod, List[str]] = {}
        
        for contact in self.contacts.values():
            if contact.escalation_level == escalation_level and contact.on_call:
                for method, address in contact.methods.items():
                    # Only add if not already notified
                    if method not in original_contacts or address not in original_contacts[method]:
                        if method not in result:
                            result[method] = []
                        result[method].append(address)
        
        return result
    
    def create_default_mappings(self) -> None:
        """Create sensible default contact mappings."""
        # Create default contact groups
        self.create_contact_group(
            "noc_team",
            "Primary NOC operators",
            [ContactMethod.TELEGRAM, ContactMethod.EMAIL]
        )
        
        self.create_contact_group(
            "network_admins",
            "Network administrators",
            [ContactMethod.TELEGRAM, ContactMethod.SMS, ContactMethod.VOICE]
        )
        
        self.create_contact_group(
            "managers",
            "IT Management",
            [ContactMethod.EMAIL, ContactMethod.SMS]
        )
        
        self.create_contact_group(
            "on_call",
            "On-call engineer",
            [ContactMethod.VOICE, ContactMethod.SMS, ContactMethod.TELEGRAM]
        )
        
        # Map severities
        self.map_severity_to_contacts("info", ["noc_team"])
        self.map_severity_to_contacts("low", ["noc_team"])
        self.map_severity_to_contacts("medium", ["noc_team"])
        self.map_severity_to_contacts("high", ["noc_team", "network_admins"])
        self.map_severity_to_contacts("critical", ["noc_team", "network_admins", "on_call"])
        self.map_severity_to_contacts("emergency", ["noc_team", "network_admins", "on_call", "managers"])
    
    def should_notify_now(
        self,
        contact_id: str,
        current_time: Optional[Any] = None
    ) -> bool:
        """
        Check if contact should be notified at current time.
        
        Considers:
        - On-call schedule
        - Do-not-disturb settings
        - Timezone
        """
        if contact_id not in self.contacts:
            return False
        
        contact = self.contacts[contact_id]
        
        if not contact.on_call:
            return False
        
        # TODO: Check schedule and timezone
        
        return True
