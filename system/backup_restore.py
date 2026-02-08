from __future__ import annotations

import json
import os
import shutil
import tarfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class BackupManager:
    """Manage system backups and restore operations."""
    
    def __init__(self, backup_dir: str = "./backups"):
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_backup(
        self,
        name: Optional[str] = None,
        include_data: bool = True,
        include_configs: bool = True,
        include_logs: bool = False
    ) -> Dict[str, Any]:
        """Create a full system backup."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"backup_{timestamp}"
        backup_path = os.path.join(self.backup_dir, f"{backup_name}.tar.gz")
        
        backup_info = {
            "name": backup_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "includes": {
                "data": include_data,
                "configs": include_configs,
                "logs": include_logs,
            },
            "files": [],
        }
        
        # Create temporary manifest
        manifest = []
        
        with tarfile.open(backup_path, "w:gz") as tar:
            # Backup data directory
            if include_data and os.path.exists("./data"):
                tar.add("./data", arcname="data")
                manifest.append("data/")
            
            # Backup config directory
            if include_configs and os.path.exists("./config"):
                tar.add("./config", arcname="config")
                manifest.append("config/")
            
            # Backup reports
            if os.path.exists("./reports"):
                tar.add("./reports", arcname="reports")
                manifest.append("reports/")
            
            # Backup plugin customizations
            if os.path.exists("./autodetector/plugins/custom"):
                tar.add(
                    "./autodetector/plugins/custom",
                    arcname="autodetector/plugins/custom"
                )
                manifest.append("autodetector/plugins/custom/")
            
            # Create backup metadata
            metadata = json.dumps(backup_info, indent=2).encode()
            import io
            metadata_bytes = io.BytesIO(metadata)
            metadata_tarinfo = tarfile.TarInfo(name="backup_metadata.json")
            metadata_tarinfo.size = len(metadata)
            tar.addfile(metadata_tarinfo, metadata_bytes)
        
        backup_info["path"] = backup_path
        backup_info["size_bytes"] = os.path.getsize(backup_path)
        
        return backup_info
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []
        
        for filename in os.listdir(self.backup_dir):
            if filename.endswith(".tar.gz"):
                path = os.path.join(self.backup_dir, filename)
                stat = os.stat(path)
                backups.append({
                    "name": filename[:-7],  # Remove .tar.gz
                    "filename": filename,
                    "created_at": datetime.fromtimestamp(
                        stat.st_mtime, timezone.utc
                    ).isoformat(),
                    "size_bytes": stat.st_size,
                    "path": path,
                })
        
        return sorted(backups, key=lambda x: x["created_at"], reverse=True)
    
    def restore_backup(
        self,
        backup_name: str,
        restore_data: bool = True,
        restore_configs: bool = True,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Restore from a backup."""
        backup_path = os.path.join(self.backup_dir, f"{backup_name}.tar.gz")
        
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        
        restored = []
        errors = []
        
        with tarfile.open(backup_path, "r:gz") as tar:
            # Read metadata
            try:
                metadata_file = tar.extractfile("backup_metadata.json")
                if metadata_file:
                    metadata = json.loads(metadata_file.read().decode())
            except Exception as e:
                metadata = {"error": str(e)}
            
            if not dry_run:
                for member in tar.getmembers():
                    try:
                        if member.name.startswith("data/") and restore_data:
                            tar.extract(member)
                            restored.append(member.name)
                        elif member.name.startswith("config/") and restore_configs:
                            tar.extract(member)
                            restored.append(member.name)
                        elif member.name.startswith("reports/"):
                            tar.extract(member)
                            restored.append(member.name)
                        elif member.name.startswith("autodetector/plugins/custom/"):
                            tar.extract(member)
                            restored.append(member.name)
                    except Exception as e:
                        errors.append({"file": member.name, "error": str(e)})
        
        return {
            "backup_name": backup_name,
            "restored_files": restored,
            "errors": errors,
            "dry_run": dry_run,
            "metadata": metadata,
            "restored_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def delete_backup(self, backup_name: str) -> bool:
        """Delete a backup."""
        backup_path = os.path.join(self.backup_dir, f"{backup_name}.tar.gz")
        
        if os.path.exists(backup_path):
            os.remove(backup_path)
            return True
        return False
    
    def export_config_only(self, export_path: str) -> Dict[str, Any]:
        """Export only configuration (for migration)."""
        export_info = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "files": [],
        }
        
        with tarfile.open(export_path, "w:gz") as tar:
            if os.path.exists("./config"):
                tar.add("./config", arcname="config")
                export_info["files"].append("config/")
            
            # Export devices registry
            if os.path.exists("./data/devices.yaml"):
                tar.add("./data/devices.yaml", arcname="data/devices.yaml")
                export_info["files"].append("data/devices.yaml")
        
        export_info["path"] = export_path
        export_info["size_bytes"] = os.path.getsize(export_path)
        
        return export_info


class ConfigMigrator:
    """Migrate configuration between versions."""
    
    MIGRATIONS = {
        "1.0.0": {
            "add_fields": ["collector.retries", "alerting.cooldown_by_severity"],
            "remove_fields": [],
        },
        "1.1.0": {
            "add_fields": ["ai.anomaly.zscore_crit", "correlation.incident_window_sec"],
            "remove_fields": [],
        },
    }
    
    def __init__(self, current_version: str = "1.1.0"):
        self.current_version = current_version
    
    def migrate_config(
        self,
        config: Dict[str, Any],
        from_version: str
    ) -> Dict[str, Any]:
        """Migrate config from old version to current."""
        migrated = config.copy()
        
        # Apply migrations in order
        versions = sorted(self.MIGRATIONS.keys())
        start_idx = versions.index(from_version) if from_version in versions else 0
        
        for version in versions[start_idx:]:
            migration = self.MIGRATIONS[version]
            
            # Add new fields with defaults
            for field in migration.get("add_fields", []):
                keys = field.split(".")
                self._ensure_field(migrated, keys)
            
            # Remove deprecated fields
            for field in migration.get("remove_fields", []):
                keys = field.split(".")
                self._remove_field(migrated, keys)
        
        migrated["_meta"] = migrated.get("_meta", {})
        migrated["_meta"]["version"] = self.current_version
        migrated["_meta"]["migrated_at"] = datetime.now(timezone.utc).isoformat()
        migrated["_meta"]["from_version"] = from_version
        
        return migrated
    
    def _ensure_field(self, config: Dict[str, Any], keys: List[str]):
        """Ensure a nested field exists with default value."""
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set default if not exists
        final_key = keys[-1]
        if final_key not in current:
            current[final_key] = self._get_default_value(".".join(keys))
    
    def _remove_field(self, config: Dict[str, Any], keys: List[str]):
        """Remove a nested field."""
        current = config
        for key in keys[:-1]:
            if key not in current:
                return
            current = current[key]
        
        current.pop(keys[-1], None)
    
    def _get_default_value(self, field: str) -> Any:
        """Get default value for a field."""
        defaults = {
            "collector.retries": {"attempts": 2, "sleep_sec": 0.5},
            "alerting.cooldown_by_severity": {"info": 600, "warning": 300, "critical": 120},
            "ai.anomaly.zscore_crit": 3.5,
            "correlation.incident_window_sec": 300,
        }
        return defaults.get(field)
