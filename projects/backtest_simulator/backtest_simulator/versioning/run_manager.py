"""Run versioning and management system for backtests."""

import os
import json
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Tuple

import pandas as pd

from ..config.settings import BacktestConfig
from ..data.cloud_store import DataStoreClient


class RunVersion:
    """Representation of a backtest run version."""
    
    def __init__(self, 
                version_id: str,
                config: Dict[str, Any],
                created_at: datetime,
                description: Optional[str] = None,
                tags: Optional[List[str]] = None,
                metrics: Optional[Dict[str, float]] = None):
        """Initialize a run version.
        
        Args:
            version_id: Unique identifier for this run version
            config: Configuration used for this run
            created_at: When this run was created
            description: Optional description of this run
            tags: Optional tags for categorizing runs
            metrics: Optional performance metrics
        """
        self.version_id = version_id
        self.config = config
        self.created_at = created_at
        self.description = description or ""
        self.tags = tags or []
        self.metrics = metrics or {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunVersion':
        """Create a RunVersion from a dictionary.
        
        Args:
            data: Dictionary with run version data
            
        Returns:
            RunVersion instance
        """
        # Convert string date to datetime if needed
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        return cls(
            version_id=data['version_id'],
            config=data['config'],
            created_at=created_at,
            description=data.get('description', ""),
            tags=data.get('tags', []),
            metrics=data.get('metrics', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            'version_id': self.version_id,
            'config': self.config,
            'created_at': self.created_at.isoformat(),
            'description': self.description,
            'tags': self.tags,
            'metrics': self.metrics
        }


class RunManager:
    """Manager for backtest run versioning and storage."""
    
    def __init__(self, 
                local_store_path: Optional[str] = None,
                use_cloud_store: bool = False,
                datastore_name: str = "prod",
                workspace: Optional[str] = None):
        """Initialize the run manager.
        
        Args:
            local_store_path: Path to store run data locally
            use_cloud_store: Whether to use cloud storage
            datastore_name: Name of the DataStore to use
            workspace: Workspace name in DataStore
        """
        self.local_store_path = Path(local_store_path) if local_store_path else Path.home() / ".backtest_store"
        self.use_cloud_store = use_cloud_store
        self.cloud_store = None
        
        # Create local storage directory if it doesn't exist
        self.local_store_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize cloud storage if requested
        if use_cloud_store:
            self.cloud_store = DataStoreClient(
                datastore_name=datastore_name,
                workspace=workspace
            )
            self.cloud_store.connect()
    
    def _generate_version_id(self, config: Dict[str, Any]) -> str:
        """Generate a unique version ID based on configuration and timestamp.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Unique version ID
        """
        # Use combination of timestamp, UUID and config hash
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        config_str = json.dumps(config, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]
        unique_id = str(uuid.uuid4())[:8]
        
        return f"{timestamp}_{config_hash}_{unique_id}"
    
    def create_run_version(self, 
                          config: Union[BacktestConfig, Dict[str, Any]],
                          description: Optional[str] = None,
                          tags: Optional[List[str]] = None) -> RunVersion:
        """Create a new run version.
        
        Args:
            config: Configuration to use for this run
            description: Optional description of this run
            tags: Optional tags for categorizing runs
            
        Returns:
            Created RunVersion
        """
        # Convert BacktestConfig to dict if needed
        if isinstance(config, BacktestConfig):
            config_dict = config.to_dict()
        else:
            config_dict = config
            
        # Generate version ID
        version_id = self._generate_version_id(config_dict)
        
        # Create run version
        run_version = RunVersion(
            version_id=version_id,
            config=config_dict,
            created_at=datetime.now(),
            description=description,
            tags=tags
        )
        
        # Save the run version
        self._save_run_version(run_version)
        
        return run_version
    
    def _save_run_version(self, run_version: RunVersion) -> None:
        """Save a run version to storage.
        
        Args:
            run_version: Run version to save
        """
        # Convert to dictionary
        run_dict = run_version.to_dict()
        
        # Save locally
        version_path = self.local_store_path / f"run_{run_version.version_id}.json"
        with open(version_path, 'w') as f:
            json.dump(run_dict, f, indent=2)
        
        # Save to cloud if enabled
        if self.use_cloud_store and self.cloud_store:
            self.cloud_store.upload_results(
                pd.DataFrame([run_dict]),
                dataset_name="backtest_run_versions",
                description=f"Backtest run version {run_version.version_id}",
                partition=run_version.created_at.strftime("%Y%m")
            )
    
    def get_run_version(self, version_id: str) -> Optional[RunVersion]:
        """Get a run version by ID.
        
        Args:
            version_id: ID of the run version to get
            
        Returns:
            RunVersion if found, None otherwise
        """
        # Try to load from local storage first
        version_path = self.local_store_path / f"run_{version_id}.json"
        if version_path.exists():
            with open(version_path, 'r') as f:
                run_dict = json.load(f)
            return RunVersion.from_dict(run_dict)
        
        # Try to load from cloud if enabled
        if self.use_cloud_store and self.cloud_store:
            # This is a simplified approach - in reality, you'd need to search through partitions
            try:
                for month in range(1, 13):
                    partition = datetime.now().strftime(f"%Y{month:02d}")
                    df = self.cloud_store.download_dataset(
                        dataset_name="backtest_run_versions",
                        partition=partition,
                        format_type="pandas"
                    )
                    if not df.empty and 'version_id' in df.columns:
                        match = df[df['version_id'] == version_id]
                        if not match.empty:
                            return RunVersion.from_dict(match.iloc[0].to_dict())
            except Exception:
                # Handle potential errors from cloud storage
                pass
        
        return None
    
    def list_run_versions(self, 
                         tags: Optional[List[str]] = None, 
                         start_date: Optional[Union[str, datetime]] = None,
                         end_date: Optional[Union[str, datetime]] = None) -> List[RunVersion]:
        """List run versions with optional filtering.
        
        Args:
            tags: Optional filter by tags
            start_date: Optional filter by start date
            end_date: Optional filter by end date
            
        Returns:
            List of RunVersion objects
        """
        # Convert dates to datetime if needed
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)
        
        # Get all run versions from local storage
        versions = []
        for file_path in self.local_store_path.glob("run_*.json"):
            try:
                with open(file_path, 'r') as f:
                    run_dict = json.load(f)
                version = RunVersion.from_dict(run_dict)
                
                # Apply filters
                if tags and not any(tag in version.tags for tag in tags):
                    continue
                if start_date and version.created_at < start_date:
                    continue
                if end_date and version.created_at > end_date:
                    continue
                
                versions.append(version)
            except Exception as e:
                print(f"Error loading run version from {file_path}: {e}")
        
        # Sort by creation date, newest first
        versions.sort(key=lambda v: v.created_at, reverse=True)
        
        return versions
    
    def update_run_metrics(self, version_id: str, metrics: Dict[str, float]) -> Optional[RunVersion]:
        """Update metrics for a run version.
        
        Args:
            version_id: ID of the run version to update
            metrics: Performance metrics to update
            
        Returns:
            Updated RunVersion if found, None otherwise
        """
        # Get the run version
        run_version = self.get_run_version(version_id)
        if not run_version:
            return None
        
        # Update metrics
        run_version.metrics.update(metrics)
        
        # Save updated version
        self._save_run_version(run_version)
        
        return run_version
    
    def tag_run_version(self, version_id: str, tags: List[str]) -> Optional[RunVersion]:
        """Add tags to a run version.
        
        Args:
            version_id: ID of the run version to tag
            tags: Tags to add
            
        Returns:
            Updated RunVersion if found, None otherwise
        """
        # Get the run version
        run_version = self.get_run_version(version_id)
        if not run_version:
            return None
        
        # Add tags
        for tag in tags:
            if tag not in run_version.tags:
                run_version.tags.append(tag)
        
        # Save updated version
        self._save_run_version(run_version)
        
        return run_version
    
    def mark_as_production(self, version_id: str) -> Optional[RunVersion]:
        """Mark a run version as production.
        
        This is a special tag that indicates this version should be used for production.
        
        Args:
            version_id: ID of the run version to mark as production
            
        Returns:
            Updated RunVersion if found, None otherwise
        """
        return self.tag_run_version(version_id, ["production"])
    
    def get_production_version(self) -> Optional[RunVersion]:
        """Get the current production run version.
        
        Returns:
            The production RunVersion if found, None otherwise
        """
        versions = self.list_run_versions(tags=["production"])
        return versions[0] if versions else None
    
    def export_config_for_rerun(self, version_id: str, output_path: Optional[str] = None) -> str:
        """Export configuration for rerunning a specific version.
        
        Args:
            version_id: ID of the run version to export
            output_path: Optional path to save the configuration
            
        Returns:
            Path to the exported configuration file
        """
        # Get the run version
        run_version = self.get_run_version(version_id)
        if not run_version:
            raise ValueError(f"Run version {version_id} not found")
        
        # Create output path if not provided
        if not output_path:
            output_path = f"config_rerun_{version_id}.json"
        
        # Save configuration to file
        with open(output_path, 'w') as f:
            json.dump(run_version.config, f, indent=2)
        
        return output_path
    
    def create_run_from_previous(self, 
                               version_id: str,
                               override_params: Optional[Dict[str, Any]] = None,
                               description: Optional[str] = None,
                               tags: Optional[List[str]] = None) -> RunVersion:
        """Create a new run based on a previous one with optional parameter overrides.
        
        Args:
            version_id: ID of the previous run version
            override_params: Parameters to override from the previous run
            description: Optional description of this run
            tags: Optional tags for categorizing runs
            
        Returns:
            Created RunVersion
        """
        # Get the previous run version
        prev_run = self.get_run_version(version_id)
        if not prev_run:
            raise ValueError(f"Run version {version_id} not found")
        
        # Copy configuration and apply overrides
        config = dict(prev_run.config)
        if override_params:
            config.update(override_params)
        
        # Create description if not provided
        if not description:
            description = f"Based on run {version_id}"
        
        # Create tags if not provided
        if not tags:
            tags = []
        
        # Add reference to parent run
        if "derived_from" not in tags:
            tags.append(f"derived_from:{version_id}")
        
        # Create new run version
        return self.create_run_version(config, description, tags)
    
    def store_run_artifacts(self, 
                           version_id: str, 
                           artifacts_path: Union[str, Path],
                           artifact_type: str = "results") -> None:
        """Store artifacts associated with a run version.
        
        Args:
            version_id: ID of the run version
            artifacts_path: Path to the artifacts
            artifact_type: Type of artifact (e.g., "results", "plots", etc.)
        """
        # Get the run version
        run_version = self.get_run_version(version_id)
        if not run_version:
            raise ValueError(f"Run version {version_id} not found")
        
        # Convert to Path object
        artifacts_path = Path(artifacts_path)
        
        # Create artifact directory
        artifact_dir = self.local_store_path / "artifacts" / version_id / artifact_type
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine if it's a directory or file
        if artifacts_path.is_dir():
            # Copy entire directory
            import shutil
            for item in artifacts_path.glob("*"):
                dst = artifact_dir / item.name
                if item.is_file():
                    shutil.copy2(item, dst)
                else:
                    shutil.copytree(item, dst)
        else:
            # Copy single file
            import shutil
            shutil.copy2(artifacts_path, artifact_dir / artifacts_path.name)
        
        # Store in cloud if enabled
        if self.use_cloud_store and self.cloud_store and artifacts_path.suffix == '.parquet':
            try:
                df = pd.read_parquet(artifacts_path)
                self.cloud_store.upload_results(
                    df,
                    dataset_name=f"backtest_artifacts_{artifact_type}",
                    description=f"Artifacts for run {version_id}",
                    partition=run_version.created_at.strftime("%Y%m")
                )
            except Exception as e:
                print(f"Error uploading artifact to cloud: {e}")
    
    def get_run_artifacts(self, 
                         version_id: str, 
                         artifact_type: str = "results") -> Path:
        """Get artifacts associated with a run version.
        
        Args:
            version_id: ID of the run version
            artifact_type: Type of artifact
            
        Returns:
            Path to the artifacts
        """
        # Get the run version
        run_version = self.get_run_version(version_id)
        if not run_version:
            raise ValueError(f"Run version {version_id} not found")
        
        # Get artifact directory
        artifact_dir = self.local_store_path / "artifacts" / version_id / artifact_type
        if not artifact_dir.exists():
            raise ValueError(f"No {artifact_type} artifacts found for run {version_id}")
        
        return artifact_dir