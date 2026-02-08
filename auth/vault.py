from __future__ import annotations

import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json
from typing import Dict, Any, Optional


class CredentialVault:
    """
    Encrypted credential vault for secure password and key storage.
    Uses Fernet symmetric encryption with PBKDF2 key derivation.
    """
    
    def __init__(self, vault_file: str = "./config/vault.enc", master_key: Optional[str] = None):
        self.vault_file = vault_file
        self._key = None
        self._fernet = None
        self._cache: Dict[str, Any] = {}
        
        if master_key:
            self.unlock(master_key)
    
    def _derive_key(self, master_key: str, salt: Optional[bytes] = None) -> tuple:
        """Derive encryption key from master password."""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return key, salt
    
    def unlock(self, master_key: str) -> bool:
        """Unlock vault with master key."""
        try:
            if os.path.exists(self.vault_file):
                # Read existing vault to get salt
                with open(self.vault_file, 'rb') as f:
                    data = f.read()
                    salt = data[:16]
                    self._key, _ = self._derive_key(master_key, salt)
                    self._fernet = Fernet(self._key)
                    # Test decryption
                    self._fernet.decrypt(data[16:])
            else:
                # Create new vault
                self._key, salt = self._derive_key(master_key)
                self._fernet = Fernet(self._key)
                # Save with salt
                self._save_with_salt(salt, b'{}')
            
            return True
        except Exception:
            self._key = None
            self._fernet = None
            return False
    
    def _save_with_salt(self, salt: bytes, encrypted_data: bytes):
        """Save vault with salt prefix."""
        with open(self.vault_file, 'wb') as f:
            f.write(salt + encrypted_data)
    
    def store(self, credential_id: str, data: Dict[str, Any]):
        """Store encrypted credential."""
        if not self._fernet:
            raise ValueError("Vault is locked. Call unlock() first.")
        
        # Load existing vault
        vault_data = self._load_vault()
        vault_data[credential_id] = data
        
        # Encrypt and save
        json_data = json.dumps(vault_data).encode()
        encrypted = self._fernet.encrypt(json_data)
        
        # Get current salt
        with open(self.vault_file, 'rb') as f:
            salt = f.read()[:16]
        
        self._save_with_salt(salt, encrypted)
        self._cache[credential_id] = data
    
    def retrieve(self, credential_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve decrypted credential."""
        if credential_id in self._cache:
            return self._cache[credential_id]
        
        if not self._fernet:
            raise ValueError("Vault is locked. Call unlock() first.")
        
        vault_data = self._load_vault()
        data = vault_data.get(credential_id)
        if data:
            self._cache[credential_id] = data
        return data
    
    def _load_vault(self) -> Dict[str, Any]:
        """Load and decrypt vault data."""
        if not os.path.exists(self.vault_file):
            return {}
        
        with open(self.vault_file, 'rb') as f:
            data = f.read()
            salt = data[:16]
            encrypted = data[16:]
        
        try:
            decrypted = self._fernet.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception:
            return {}
    
    def delete(self, credential_id: str) -> bool:
        """Delete credential from vault."""
        if not self._fernet:
            raise ValueError("Vault is locked.")
        
        vault_data = self._load_vault()
        if credential_id in vault_data:
            del vault_data[credential_id]
            self._cache.pop(credential_id, None)
            
            json_data = json.dumps(vault_data).encode()
            encrypted = self._fernet.encrypt(json_data)
            
            with open(self.vault_file, 'rb') as f:
                salt = f.read()[:16]
            
            self._save_with_salt(salt, encrypted)
            return True
        return False
    
    def list_credentials(self) -> list:
        """List all credential IDs in vault."""
        if not self._fernet:
            raise ValueError("Vault is locked.")
        
        vault_data = self._load_vault()
        return list(vault_data.keys())
    
    def change_master_key(self, old_key: str, new_key: str) -> bool:
        """Change master key (re-encrypt vault)."""
        if not self.unlock(old_key):
            return False
        
        # Load all data
        vault_data = self._load_vault()
        
        # Re-encrypt with new key
        self._key, salt = self._derive_key(new_key)
        self._fernet = Fernet(self._key)
        
        json_data = json.dumps(vault_data).encode()
        encrypted = self._fernet.encrypt(json_data)
        self._save_with_salt(salt, encrypted)
        
        return True
    
    def is_locked(self) -> bool:
        """Check if vault is locked."""
        return self._fernet is None


class CredentialResolver:
    """Resolve credentials from vault or environment variables."""
    
    def __init__(self, vault: Optional[CredentialVault] = None):
        self.vault = vault
    
    def resolve(self, value: str) -> str:
        """
        Resolve credential value.
        Supports:
        - ${ENV_VAR} - Environment variable
        - ${VAULT:credential_id:field} - Vault lookup
        - Plain text - Returned as-is
        """
        if value.startswith("${") and value.endswith("}"):
            inner = value[2:-1]
            
            # Vault lookup
            if inner.startswith("VAULT:"):
                if not self.vault or self.vault.is_locked():
                    raise ValueError("Vault required for VAULT: reference")
                
                parts = inner.split(":")
                if len(parts) >= 3:
                    credential_id = parts[1]
                    field = parts[2]
                    data = self.vault.retrieve(credential_id)
                    if data and field in data:
                        return data[field]
                    raise ValueError(f"Vault credential '{credential_id}.{field}' not found")
            
            # Environment variable
            env_var = inner
            env_value = os.environ.get(env_var)
            if env_value is None:
                raise ValueError(f"Environment variable '{env_var}' not set")
            return env_value
        
        return value
    
    def resolve_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve all credential references in a dictionary."""
        resolved = {}
        for key, value in data.items():
            if isinstance(value, str):
                resolved[key] = self.resolve(value)
            elif isinstance(value, dict):
                resolved[key] = self.resolve_dict(value)
            else:
                resolved[key] = value
        return resolved
