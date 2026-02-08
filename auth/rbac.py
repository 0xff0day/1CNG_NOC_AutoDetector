from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


class Permission(str, Enum):
    """Permission types for RBAC."""
    # Device permissions
    DEVICE_READ = "device:read"
    DEVICE_WRITE = "device:write"
    DEVICE_DELETE = "device:delete"
    DEVICE_SCAN = "device:scan"
    
    # Alert permissions
    ALERT_READ = "alert:read"
    ALERT_ACK = "alert:ack"
    ALERT_SUPPRESS = "alert:suppress"
    ALERT_CONFIGURE = "alert:configure"
    
    # Report permissions
    REPORT_READ = "report:read"
    REPORT_GENERATE = "report:generate"
    REPORT_EXPORT = "report:export"
    
    # Configuration permissions
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    
    # Plugin permissions
    PLUGIN_READ = "plugin:read"
    PLUGIN_MANAGE = "plugin:manage"
    
    # Admin permissions
    ADMIN_FULL = "admin:full"
    USER_MANAGE = "user:manage"
    TENANT_MANAGE = "tenant:manage"


class Role(str, Enum):
    """Pre-defined roles."""
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    NOC_MANAGER = "noc_manager"
    NOC_ENGINEER = "noc_engineer"
    VIEWER = "viewer"
    API_SERVICE = "api_service"


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: set(Permission),  # All permissions
    
    Role.TENANT_ADMIN: {
        Permission.DEVICE_READ,
        Permission.DEVICE_WRITE,
        Permission.DEVICE_SCAN,
        Permission.ALERT_READ,
        Permission.ALERT_ACK,
        Permission.ALERT_SUPPRESS,
        Permission.ALERT_CONFIGURE,
        Permission.REPORT_READ,
        Permission.REPORT_GENERATE,
        Permission.REPORT_EXPORT,
        Permission.CONFIG_READ,
        Permission.CONFIG_WRITE,
        Permission.PLUGIN_READ,
        Permission.USER_MANAGE,
    },
    
    Role.NOC_MANAGER: {
        Permission.DEVICE_READ,
        Permission.DEVICE_SCAN,
        Permission.ALERT_READ,
        Permission.ALERT_ACK,
        Permission.ALERT_SUPPRESS,
        Permission.ALERT_CONFIGURE,
        Permission.REPORT_READ,
        Permission.REPORT_GENERATE,
        Permission.REPORT_EXPORT,
        Permission.CONFIG_READ,
        Permission.PLUGIN_READ,
    },
    
    Role.NOC_ENGINEER: {
        Permission.DEVICE_READ,
        Permission.DEVICE_SCAN,
        Permission.ALERT_READ,
        Permission.ALERT_ACK,
        Permission.REPORT_READ,
        Permission.CONFIG_READ,
    },
    
    Role.VIEWER: {
        Permission.DEVICE_READ,
        Permission.ALERT_READ,
        Permission.REPORT_READ,
        Permission.CONFIG_READ,
    },
    
    Role.API_SERVICE: {
        Permission.DEVICE_READ,
        Permission.DEVICE_SCAN,
        Permission.ALERT_READ,
        Permission.REPORT_READ,
        Permission.CONFIG_READ,
    },
}


@dataclass(frozen=True)
class RBACContext:
    """Context for RBAC checks."""
    user_id: str
    tenant_id: str
    roles: List[Role]
    permissions: Set[Permission]
    resource_tenant_id: Optional[str] = None
    resource_device_id: Optional[str] = None


class RBACManager:
    """Role-Based Access Control manager."""
    
    def __init__(self):
        self.user_roles: Dict[str, List[Role]] = {}
        self.custom_permissions: Dict[str, Set[Permission]] = {}
        self.audit_log: List[Dict[str, Any]] = []
    
    def assign_role(self, user_id: str, role: Role):
        """Assign a role to a user."""
        if user_id not in self.user_roles:
            self.user_roles[user_id] = []
        
        if role not in self.user_roles[user_id]:
            self.user_roles[user_id].append(role)
            self._log_action("role_assign", user_id, {"role": role.value})
    
    def revoke_role(self, user_id: str, role: Role):
        """Revoke a role from a user."""
        if user_id in self.user_roles:
            self.user_roles[user_id] = [
                r for r in self.user_roles[user_id] if r != role
            ]
            self._log_action("role_revoke", user_id, {"role": role.value})
    
    def grant_permission(
        self, 
        user_id: str, 
        permission: Permission,
        resource_filter: Optional[Dict[str, Any]] = None
    ):
        """Grant a specific permission to a user (beyond their roles)."""
        if user_id not in self.custom_permissions:
            self.custom_permissions[user_id] = set()
        
        self.custom_permissions[user_id].add(permission)
        
        self._log_action(
            "permission_grant", 
            user_id, 
            {
                "permission": permission.value,
                "resource_filter": resource_filter,
            }
        )
    
    def revoke_permission(self, user_id: str, permission: Permission):
        """Revoke a specific permission from a user."""
        if user_id in self.custom_permissions:
            self.custom_permissions[user_id].discard(permission)
            self._log_action("permission_revoke", user_id, {"permission": permission.value})
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """Get all permissions for a user (from roles + custom)."""
        permissions: Set[Permission] = set()
        
        # Add permissions from roles
        for role in self.user_roles.get(user_id, []):
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
        
        # Add custom permissions
        if user_id in self.custom_permissions:
            permissions.update(self.custom_permissions[user_id])
        
        return permissions
    
    def has_permission(
        self,
        user_id: str,
        permission: Permission,
        context: Optional[RBACContext] = None
    ) -> bool:
        """Check if user has a specific permission."""
        # Super admin always has permission
        user_roles = self.user_roles.get(user_id, [])
        if Role.SUPER_ADMIN in user_roles:
            return True
        
        # Check if user has permission
        user_perms = self.get_user_permissions(user_id)
        if permission not in user_perms:
            return False
        
        # Check tenant isolation if context provided
        if context:
            if context.tenant_id != context.resource_tenant_id:
                # Cross-tenant access requires special permission
                if Permission.TENANT_MANAGE not in user_perms:
                    return False
        
        return True
    
    def check_access(
        self,
        user_id: str,
        required_permissions: List[Permission],
        context: Optional[RBACContext] = None,
        require_all: bool = True
    ) -> Tuple[bool, List[str]]:
        """
        Check if user has required permissions.
        Returns (granted, missing_permissions).
        """
        missing = []
        
        for perm in required_permissions:
            if not self.has_permission(user_id, perm, context):
                missing.append(perm.value)
        
        if require_all:
            granted = len(missing) == 0
        else:
            granted = len(missing) < len(required_permissions)
        
        return granted, missing
    
    def _log_action(self, action: str, user_id: str, details: Dict[str, Any]):
        """Log an RBAC action."""
        self.audit_log.append({
            "action": action,
            "user_id": user_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get RBAC audit log."""
        filtered = self.audit_log
        
        if user_id:
            filtered = [e for e in filtered if e["user_id"] == user_id]
        
        if action:
            filtered = [e for e in filtered if e["action"] == action]
        
        return filtered[-limit:]


class ResourceACL:
    """Fine-grained resource-level access control."""
    
    def __init__(self):
        self.resource_permissions: Dict[str, Dict[str, Set[Permission]]] = {}
        # Structure: {resource_id: {user_id: {permissions}}}
    
    def grant_resource_access(
        self,
        resource_id: str,
        user_id: str,
        permissions: Set[Permission]
    ):
        """Grant specific permissions on a resource."""
        if resource_id not in self.resource_permissions:
            self.resource_permissions[resource_id] = {}
        
        self.resource_permissions[resource_id][user_id] = permissions
    
    def revoke_resource_access(self, resource_id: str, user_id: str):
        """Revoke all access to a resource."""
        if resource_id in self.resource_permissions:
            self.resource_permissions[resource_id].pop(user_id, None)
    
    def check_resource_access(
        self,
        resource_id: str,
        user_id: str,
        permission: Permission
    ) -> bool:
        """Check if user has permission on a specific resource."""
        if resource_id not in self.resource_permissions:
            return False
        
        user_perms = self.resource_permissions[resource_id].get(user_id, set())
        return permission in user_perms
