from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    name: str
    created_at: str
    settings: Dict[str, Any]
    allowed_devices: Optional[Set[str]]  # None = all devices
    allowed_networks: Optional[List[str]]  # CIDR ranges


@dataclass(frozen=True)
class User:
    user_id: str
    tenant_id: str
    username: str
    email: str
    created_at: str
    roles: List[str]
    api_key: str
    last_login: Optional[str] = None


class MultiTenantManager:
    """Manage multi-tenant isolation and resource allocation."""
    
    def __init__(self):
        self.tenants: Dict[str, Tenant] = {}
        self.users: Dict[str, User] = {}
        self.device_to_tenant: Dict[str, str] = {}
    
    def create_tenant(
        self,
        name: str,
        allowed_networks: Optional[List[str]] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> Tenant:
        """Create a new tenant."""
        tenant_id = f"TENANT-{secrets.token_hex(8)}"
        
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            created_at=datetime.now(timezone.utc).isoformat(),
            settings=settings or {},
            allowed_devices=None,  # All devices by default
            allowed_networks=allowed_networks,
        )
        
        self.tenants[tenant_id] = tenant
        return tenant
    
    def create_user(
        self,
        tenant_id: str,
        username: str,
        email: str,
        roles: List[str] = None
    ) -> User:
        """Create a user within a tenant."""
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        user_id = f"USER-{secrets.token_hex(8)}"
        api_key = self._generate_api_key()
        
        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            username=username,
            email=email,
            created_at=datetime.now(timezone.utc).isoformat(),
            roles=roles or ["viewer"],
            api_key=api_key,
        )
        
        self.users[user_id] = user
        return user
    
    def _generate_api_key(self) -> str:
        """Generate a secure API key."""
        return f"noc_{secrets.token_urlsafe(32)}"
    
    def authenticate_api_key(self, api_key: str) -> Optional[User]:
        """Authenticate user by API key."""
        for user in self.users.values():
            if hmac.compare_digest(user.api_key, api_key):
                return user
        return None
    
    def can_access_device(
        self,
        tenant_id: str,
        device_id: str,
        device_ip: Optional[str] = None
    ) -> bool:
        """Check if tenant can access a specific device."""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return False
        
        # Check if device is in allowed devices list
        if tenant.allowed_devices is not None:
            if device_id not in tenant.allowed_devices:
                return False
        
        # Check if device IP is in allowed networks
        if tenant.allowed_networks and device_ip:
            if not self._ip_in_networks(device_ip, tenant.allowed_networks):
                return False
        
        return True
    
    def _ip_in_networks(self, ip: str, networks: List[str]) -> bool:
        """Check if IP is in any of the allowed networks."""
        import ipaddress
        
        try:
            ip_obj = ipaddress.ip_address(ip)
            for network_str in networks:
                network = ipaddress.ip_network(network_str, strict=False)
                if ip_obj in network:
                    return True
        except Exception:
            return False
        
        return False
    
    def get_tenant_resources(self, tenant_id: str) -> Dict[str, Any]:
        """Get resource usage for a tenant."""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return {}
        
        tenant_users = [u for u in self.users.values() if u.tenant_id == tenant_id]
        tenant_devices = [
            d for d, t in self.device_to_tenant.items() 
            if t == tenant_id
        ]
        
        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant.name,
            "user_count": len(tenant_users),
            "device_count": len(tenant_devices),
            "created_at": tenant.created_at,
            "settings": tenant.settings,
        }
    
    def assign_device_to_tenant(
        self,
        device_id: str,
        tenant_id: str
    ) -> bool:
        """Assign a device to a tenant."""
        if tenant_id not in self.tenants:
            return False
        
        self.device_to_tenant[device_id] = tenant_id
        return True


class QuotaManager:
    """Manage resource quotas per tenant."""
    
    DEFAULT_QUOTAS = {
        "max_devices": 100,
        "max_polls_per_hour": 10000,
        "max_alerts_stored": 10000,
        "max_reports_stored": 100,
        "max_api_calls_per_hour": 1000,
    }
    
    def __init__(self):
        self.tenant_quotas: Dict[str, Dict[str, int]] = {}
        self.tenant_usage: Dict[str, Dict[str, int]] = {}
    
    def set_quota(
        self,
        tenant_id: str,
        quota_type: str,
        limit: int
    ):
        """Set a quota for a tenant."""
        if tenant_id not in self.tenant_quotas:
            self.tenant_quotas[tenant_id] = dict(self.DEFAULT_QUOTAS)
        
        self.tenant_quotas[tenant_id][quota_type] = limit
    
    def check_quota(
        self,
        tenant_id: str,
        quota_type: str,
        increment: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if operation is within quota."""
        quota = self.tenant_quotas.get(tenant_id, self.DEFAULT_QUOTAS).get(
            quota_type, self.DEFAULT_QUOTAS[quota_type]
        )
        
        current = self.tenant_usage.get(tenant_id, {}).get(quota_type, 0)
        
        if current + increment > quota:
            return False, {
                "quota_type": quota_type,
                "limit": quota,
                "current": current,
                "requested": increment,
                "remaining": max(0, quota - current),
            }
        
        # Update usage
        if tenant_id not in self.tenant_usage:
            self.tenant_usage[tenant_id] = {}
        self.tenant_usage[tenant_id][quota_type] = current + increment
        
        return True, {
            "quota_type": quota_type,
            "limit": quota,
            "current": current + increment,
            "remaining": quota - (current + increment),
        }
    
    def reset_usage(self, tenant_id: str, quota_type: Optional[str] = None):
        """Reset usage counters."""
        if tenant_id not in self.tenant_usage:
            return
        
        if quota_type:
            self.tenant_usage[tenant_id][quota_type] = 0
        else:
            self.tenant_usage[tenant_id] = {}
