"""Management of marking configurations for backtest runs."""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Set

import pandas as pd

from .run_manager import RunManager, RunVersion


class MarkingConfig:
    """Configuration for trade markings."""
    
    def __init__(self, 
                name: str,
                parameters: Dict[str, Any],
                version: str = "1.0.0",
                description: Optional[str] = None):
        """Initialize a marking configuration.
        
        Args:
            name: Name of the marking
            parameters: Parameters for this marking
            version: Version of this marking configuration
            description: Optional description
        """
        self.name = name
        self.parameters = parameters
        self.version = version
        self.description = description or ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarkingConfig':
        """Create a MarkingConfig from a dictionary.
        
        Args:
            data: Dictionary with marking config data
            
        Returns:
            MarkingConfig instance
        """
        return cls(
            name=data['name'],
            parameters=data['parameters'],
            version=data.get('version', "1.0.0"),
            description=data.get('description', "")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'parameters': self.parameters,
            'version': self.version,
            'description': self.description
        }
    
    def get_hash(self) -> str:
        """Get a hash of this marking configuration.
        
        Returns:
            Hash string
        """
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()


class MarkingManager:
    """Manager for marking configurations."""
    
    def __init__(self, run_manager: RunManager):
        """Initialize the marking manager.
        
        Args:
            run_manager: RunManager instance for versioning
        """
        self.run_manager = run_manager
        self.markings_path = self.run_manager.local_store_path / "markings"
        self.markings_path.mkdir(parents=True, exist_ok=True)
    
    def create_marking_config(self, 
                             name: str,
                             parameters: Dict[str, Any],
                             version: str = "1.0.0",
                             description: Optional[str] = None) -> MarkingConfig:
        """Create a new marking configuration.
        
        Args:
            name: Name of the marking
            parameters: Parameters for this marking
            version: Version of this marking configuration
            description: Optional description
            
        Returns:
            Created MarkingConfig
        """
        marking_config = MarkingConfig(
            name=name,
            parameters=parameters,
            version=version,
            description=description
        )
        
        # Save the marking config
        self._save_marking_config(marking_config)
        
        return marking_config
    
    def _save_marking_config(self, marking_config: MarkingConfig) -> None:
        """Save a marking configuration to storage.
        
        Args:
            marking_config: Marking configuration to save
        """
        # Convert to dictionary
        config_dict = marking_config.to_dict()
        
        # Save with version in filename
        filename = f"{marking_config.name}_v{marking_config.version.replace('.', '_')}.json"
        config_path = self.markings_path / filename
        
        with open(config_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        # Save to cloud if enabled
        if self.run_manager.use_cloud_store and self.run_manager.cloud_store:
            self.run_manager.cloud_store.upload_results(
                pd.DataFrame([config_dict]),
                dataset_name="backtest_marking_configs",
                description=f"Marking config {marking_config.name} v{marking_config.version}",
                partition=marking_config.name
            )
    
    def get_marking_config(self, name: str, version: Optional[str] = None) -> Optional[MarkingConfig]:
        """Get a marking configuration by name and optional version.
        
        Args:
            name: Name of the marking config
            version: Optional version of the marking config
            
        Returns:
            MarkingConfig if found, None otherwise
        """
        if version:
            # Try to load specific version
            version_str = version.replace('.', '_')
            config_path = self.markings_path / f"{name}_v{version_str}.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_dict = json.load(f)
                return MarkingConfig.from_dict(config_dict)
        else:
            # Load latest version
            versions = self.list_marking_versions(name)
            if versions:
                latest_version = versions[0]
                return self.get_marking_config(name, latest_version)
        
        return None
    
    def list_marking_types(self) -> List[str]:
        """List all available marking types.
        
        Returns:
            List of marking type names
        """
        marking_types = set()
        for file_path in self.markings_path.glob("*.json"):
            # Extract marking name from filename
            filename = file_path.stem
            marking_name = filename.split('_v')[0]
            marking_types.add(marking_name)
        
        return sorted(list(marking_types))
    
    def list_marking_versions(self, name: str) -> List[str]:
        """List all available versions for a marking type.
        
        Args:
            name: Name of the marking
            
        Returns:
            List of version strings, newest first
        """
        versions = []
        for file_path in self.markings_path.glob(f"{name}_v*.json"):
            # Extract version from filename
            filename = file_path.stem
            version_str = filename.split('_v')[1].replace('_', '.')
            versions.append(version_str)
        
        # Sort versions in descending order (newest first)
        from packaging import version
        versions.sort(key=lambda v: version.parse(v), reverse=True)
        
        return versions
    
    def associate_markings_with_run(self, 
                                  run_version_id: str,
                                  marking_configs: List[MarkingConfig]) -> RunVersion:
        """Associate marking configurations with a run version.
        
        Args:
            run_version_id: ID of the run version
            marking_configs: List of marking configurations
            
        Returns:
            Updated RunVersion
        """
        # Get the run version
        run_version = self.run_manager.get_run_version(run_version_id)
        if not run_version:
            raise ValueError(f"Run version {run_version_id} not found")
        
        # Extract marking information
        markings_info = []
        for marking in marking_configs:
            markings_info.append({
                'name': marking.name,
                'version': marking.version,
                'hash': marking.get_hash()
            })
        
        # Update run config with markings info
        run_config = dict(run_version.config)
        run_config['markings'] = markings_info
        
        # Update the run version
        run_version.config = run_config
        self.run_manager._save_run_version(run_version)
        
        return run_version
    
    def get_markings_for_run(self, run_version_id: str) -> List[MarkingConfig]:
        """Get marking configurations associated with a run version.
        
        Args:
            run_version_id: ID of the run version
            
        Returns:
            List of marking configurations
        """
        # Get the run version
        run_version = self.run_manager.get_run_version(run_version_id)
        if not run_version:
            raise ValueError(f"Run version {run_version_id} not found")
        
        # Extract marking information from config
        markings_info = run_version.config.get('markings', [])
        
        # Load marking configurations
        marking_configs = []
        for info in markings_info:
            marking = self.get_marking_config(info['name'], info['version'])
            if marking:
                marking_configs.append(marking)
        
        return marking_configs
    
    def create_marking_bundle(self, 
                            name: str,
                            marking_configs: List[MarkingConfig],
                            description: Optional[str] = None) -> Dict[str, Any]:
        """Create a bundle of marking configurations.
        
        This allows grouping multiple markings together for easier reference.
        
        Args:
            name: Name of the bundle
            marking_configs: List of marking configurations
            description: Optional description
            
        Returns:
            Bundle information
        """
        # Create bundle information
        bundle = {
            'name': name,
            'description': description or "",
            'created_at': datetime.now().isoformat(),
            'markings': []
        }
        
        # Add marking information
        for marking in marking_configs:
            bundle['markings'].append({
                'name': marking.name,
                'version': marking.version,
                'hash': marking.get_hash()
            })
        
        # Save bundle
        bundle_path = self.run_manager.local_store_path / "bundles" / f"{name}.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(bundle_path, 'w') as f:
            json.dump(bundle, f, indent=2)
        
        # Save to cloud if enabled
        if self.run_manager.use_cloud_store and self.run_manager.cloud_store:
            self.run_manager.cloud_store.upload_results(
                pd.DataFrame([bundle]),
                dataset_name="backtest_marking_bundles",
                description=f"Marking bundle {name}",
                partition="bundles"
            )
        
        return bundle
    
    def get_marking_bundle(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a marking bundle by name.
        
        Args:
            name: Name of the bundle
            
        Returns:
            Bundle information if found, None otherwise
        """
        bundle_path = self.run_manager.local_store_path / "bundles" / f"{name}.json"
        if bundle_path.exists():
            with open(bundle_path, 'r') as f:
                return json.load(f)
        
        return None
    
    def get_markings_from_bundle(self, bundle_name: str) -> List[MarkingConfig]:
        """Get marking configurations from a bundle.
        
        Args:
            bundle_name: Name of the bundle
            
        Returns:
            List of marking configurations
        """
        bundle = self.get_marking_bundle(bundle_name)
        if not bundle:
            raise ValueError(f"Bundle {bundle_name} not found")
        
        # Load marking configurations
        marking_configs = []
        for info in bundle.get('markings', []):
            marking = self.get_marking_config(info['name'], info['version'])
            if marking:
                marking_configs.append(marking)
        
        return marking_configs