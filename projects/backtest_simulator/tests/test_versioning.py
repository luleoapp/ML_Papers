"""Tests for the run versioning system."""

import pytest
import os
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
import shutil

from backtest_simulator.versioning.run_manager import RunManager, RunVersion
from backtest_simulator.versioning.marking_config import MarkingManager, MarkingConfig


@pytest.fixture
def temp_store_path():
    """Create a temporary directory for storing run data."""
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    
    yield temp_dir
    
    # Clean up after tests
    shutil.rmtree(temp_dir)


@pytest.fixture
def run_manager(temp_store_path):
    """Return a run manager instance."""
    return RunManager(local_store_path=temp_store_path)


@pytest.fixture
def marking_manager(run_manager):
    """Return a marking manager instance."""
    return MarkingManager(run_manager)


@pytest.fixture
def sample_config():
    """Return a sample configuration for testing."""
    return {
        "start_date": "2023-01-01",
        "end_date": "2023-01-31",
        "exchanges": ["XNAS"],
        "universe": ["AAPL", "MSFT", "GOOGL"],
        "max_window_size": 3600,
        "use_multiple_exchanges": False
    }


@pytest.fixture
def sample_marking_config():
    """Return a sample marking configuration for testing."""
    return {
        "name": "test_marking",
        "parameters": {
            "threshold": 0.5,
            "window_size": 10,
            "use_log_returns": True
        },
        "version": "1.0.0",
        "description": "Test marking configuration"
    }


def test_run_version_creation():
    """Test creation of a run version."""
    config = {
        "start_date": "2023-01-01",
        "end_date": "2023-01-31"
    }
    
    # Create a run version
    version = RunVersion(
        version_id="test_001",
        config=config,
        created_at=datetime.now(),
        description="Test run",
        tags=["test"]
    )
    
    # Check properties
    assert version.version_id == "test_001"
    assert version.config == config
    assert isinstance(version.created_at, datetime)
    assert version.description == "Test run"
    assert version.tags == ["test"]
    
    # Test to_dict
    version_dict = version.to_dict()
    assert version_dict["version_id"] == "test_001"
    assert version_dict["config"] == config
    assert isinstance(version_dict["created_at"], str)
    assert version_dict["description"] == "Test run"
    assert version_dict["tags"] == ["test"]
    
    # Test from_dict
    restored = RunVersion.from_dict(version_dict)
    assert restored.version_id == version.version_id
    assert restored.config == version.config
    assert restored.description == version.description
    assert restored.tags == version.tags


def test_run_manager_create_version(run_manager, sample_config):
    """Test creating a run version with the manager."""
    # Create a run version
    run_version = run_manager.create_run_version(
        config=sample_config,
        description="Test run",
        tags=["test"]
    )
    
    # Check properties
    assert run_version.config == sample_config
    assert run_version.description == "Test run"
    assert run_version.tags == ["test"]
    
    # Check that the version was saved
    version_path = Path(run_manager.local_store_path) / f"run_{run_version.version_id}.json"
    assert version_path.exists()
    
    # Read the saved version
    with open(version_path, 'r') as f:
        saved_data = json.load(f)
    
    assert saved_data["version_id"] == run_version.version_id
    assert saved_data["config"] == sample_config
    assert saved_data["description"] == "Test run"
    assert saved_data["tags"] == ["test"]


def test_run_manager_get_version(run_manager, sample_config):
    """Test getting a run version by ID."""
    # Create a run version
    run_version = run_manager.create_run_version(
        config=sample_config,
        description="Test run",
        tags=["test"]
    )
    
    # Get the version
    retrieved = run_manager.get_run_version(run_version.version_id)
    
    # Check properties
    assert retrieved.version_id == run_version.version_id
    assert retrieved.config == run_version.config
    assert retrieved.description == run_version.description
    assert retrieved.tags == run_version.tags
    
    # Test getting a non-existent version
    assert run_manager.get_run_version("non_existent") is None


def test_run_manager_list_versions(run_manager, sample_config):
    """Test listing run versions with filtering."""
    # Create multiple run versions
    version1 = run_manager.create_run_version(
        config=sample_config,
        description="Test run 1",
        tags=["test", "production"]
    )
    
    version2 = run_manager.create_run_version(
        config=sample_config,
        description="Test run 2",
        tags=["test", "development"]
    )
    
    version3 = run_manager.create_run_version(
        config=sample_config,
        description="Test run 3",
        tags=["test", "experimental"]
    )
    
    # List all versions
    versions = run_manager.list_run_versions()
    assert len(versions) == 3
    
    # List versions with tag filter
    prod_versions = run_manager.list_run_versions(tags=["production"])
    assert len(prod_versions) == 1
    assert prod_versions[0].version_id == version1.version_id
    
    dev_versions = run_manager.list_run_versions(tags=["development"])
    assert len(dev_versions) == 1
    assert dev_versions[0].version_id == version2.version_id
    
    # List versions with date filter
    future_date = datetime.now() + timedelta(days=1)
    dated_versions = run_manager.list_run_versions(end_date=future_date)
    assert len(dated_versions) == 3


def test_run_manager_update_metrics(run_manager, sample_config):
    """Test updating metrics for a run version."""
    # Create a run version
    run_version = run_manager.create_run_version(
        config=sample_config,
        description="Test run",
        tags=["test"]
    )
    
    # Update metrics
    metrics = {
        "run_duration_seconds": 120.5,
        "result_count": 1000,
        "symbols_count": 3
    }
    
    updated = run_manager.update_run_metrics(run_version.version_id, metrics)
    
    # Check that metrics were updated
    assert updated.metrics == metrics
    
    # Get the version again to verify persistence
    retrieved = run_manager.get_run_version(run_version.version_id)
    assert retrieved.metrics == metrics
    
    # Update with additional metrics
    more_metrics = {
        "accuracy": 0.95,
        "loss": 0.05
    }
    
    updated = run_manager.update_run_metrics(run_version.version_id, more_metrics)
    
    # Check that new metrics were added to existing ones
    expected_metrics = {**metrics, **more_metrics}
    assert updated.metrics == expected_metrics


def test_run_manager_tag_version(run_manager, sample_config):
    """Test tagging a run version."""
    # Create a run version
    run_version = run_manager.create_run_version(
        config=sample_config,
        description="Test run",
        tags=["test"]
    )
    
    # Add tags
    updated = run_manager.tag_run_version(run_version.version_id, ["production", "validated"])
    
    # Check that tags were added
    assert "production" in updated.tags
    assert "validated" in updated.tags
    assert "test" in updated.tags
    
    # Get the version again to verify persistence
    retrieved = run_manager.get_run_version(run_version.version_id)
    assert "production" in retrieved.tags
    assert "validated" in retrieved.tags
    assert "test" in retrieved.tags


def test_run_manager_mark_as_production(run_manager, sample_config):
    """Test marking a run version as production."""
    # Create multiple run versions
    version1 = run_manager.create_run_version(
        config=sample_config,
        description="Test run 1",
        tags=["test"]
    )
    
    version2 = run_manager.create_run_version(
        config=sample_config,
        description="Test run 2",
        tags=["test"]
    )
    
    # Mark version1 as production
    run_manager.mark_as_production(version1.version_id)
    
    # Check that version1 is marked as production
    retrieved = run_manager.get_run_version(version1.version_id)
    assert "production" in retrieved.tags
    
    # Get production version
    prod_version = run_manager.get_production_version()
    assert prod_version is not None
    assert prod_version.version_id == version1.version_id
    
    # Mark version2 as production
    run_manager.mark_as_production(version2.version_id)
    
    # Check that version2 is now the production version
    prod_version = run_manager.get_production_version()
    assert prod_version is not None
    assert prod_version.version_id == version2.version_id


def test_marking_config_creation():
    """Test creation of a marking configuration."""
    # Create a marking configuration
    marking = MarkingConfig(
        name="test_marking",
        parameters={"threshold": 0.5},
        version="1.0.0",
        description="Test marking"
    )
    
    # Check properties
    assert marking.name == "test_marking"
    assert marking.parameters == {"threshold": 0.5}
    assert marking.version == "1.0.0"
    assert marking.description == "Test marking"
    
    # Test to_dict
    marking_dict = marking.to_dict()
    assert marking_dict["name"] == "test_marking"
    assert marking_dict["parameters"] == {"threshold": 0.5}
    assert marking_dict["version"] == "1.0.0"
    assert marking_dict["description"] == "Test marking"
    
    # Test from_dict
    restored = MarkingConfig.from_dict(marking_dict)
    assert restored.name == marking.name
    assert restored.parameters == marking.parameters
    assert restored.version == marking.version
    assert restored.description == marking.description
    
    # Test get_hash
    hash1 = marking.get_hash()
    assert isinstance(hash1, str)
    assert len(hash1) > 0
    
    # Create a different marking and check that hash is different
    marking2 = MarkingConfig(
        name="test_marking",
        parameters={"threshold": 0.6},  # Different parameter
        version="1.0.0",
        description="Test marking"
    )
    
    hash2 = marking2.get_hash()
    assert hash1 != hash2


def test_marking_manager_create_config(marking_manager, sample_marking_config):
    """Test creating a marking configuration with the manager."""
    # Create a marking configuration
    marking = marking_manager.create_marking_config(
        name=sample_marking_config["name"],
        parameters=sample_marking_config["parameters"],
        version=sample_marking_config["version"],
        description=sample_marking_config["description"]
    )
    
    # Check properties
    assert marking.name == sample_marking_config["name"]
    assert marking.parameters == sample_marking_config["parameters"]
    assert marking.version == sample_marking_config["version"]
    assert marking.description == sample_marking_config["description"]
    
    # Check that the configuration was saved
    config_path = Path(marking_manager.markings_path) / f"{marking.name}_v{marking.version.replace('.', '_')}.json"
    assert config_path.exists()
    
    # Read the saved configuration
    with open(config_path, 'r') as f:
        saved_data = json.load(f)
    
    assert saved_data["name"] == marking.name
    assert saved_data["parameters"] == marking.parameters
    assert saved_data["version"] == marking.version
    assert saved_data["description"] == marking.description


def test_marking_manager_get_config(marking_manager, sample_marking_config):
    """Test getting a marking configuration by name and version."""
    # Create multiple versions of a marking configuration
    marking1 = marking_manager.create_marking_config(
        name=sample_marking_config["name"],
        parameters=sample_marking_config["parameters"],
        version="1.0.0",
        description="Version 1.0.0"
    )
    
    marking2 = marking_manager.create_marking_config(
        name=sample_marking_config["name"],
        parameters={"threshold": 0.6, "window_size": 20},
        version="1.1.0",
        description="Version 1.1.0"
    )
    
    # Get a specific version
    retrieved = marking_manager.get_marking_config(sample_marking_config["name"], "1.0.0")
    assert retrieved.name == marking1.name
    assert retrieved.parameters == marking1.parameters
    assert retrieved.version == marking1.version
    assert retrieved.description == marking1.description
    
    # Get the latest version (no version specified)
    latest = marking_manager.get_marking_config(sample_marking_config["name"])
    assert latest.name == marking2.name
    assert latest.parameters == marking2.parameters
    assert latest.version == marking2.version
    assert latest.description == marking2.description


def test_marking_manager_list_types_and_versions(marking_manager, sample_marking_config):
    """Test listing marking types and versions."""
    # Create multiple marking configurations
    marking_manager.create_marking_config(
        name="marking1",
        parameters={"threshold": 0.5},
        version="1.0.0"
    )
    
    marking_manager.create_marking_config(
        name="marking1",
        parameters={"threshold": 0.6},
        version="1.1.0"
    )
    
    marking_manager.create_marking_config(
        name="marking2",
        parameters={"window_size": 10},
        version="1.0.0"
    )
    
    # List marking types
    types = marking_manager.list_marking_types()
    assert "marking1" in types
    assert "marking2" in types
    assert len(types) == 2
    
    # List versions for marking1
    versions = marking_manager.list_marking_versions("marking1")
    assert "1.1.0" in versions  # Latest version first
    assert "1.0.0" in versions
    assert len(versions) == 2
    
    # List versions for marking2
    versions = marking_manager.list_marking_versions("marking2")
    assert "1.0.0" in versions
    assert len(versions) == 1


def test_associate_markings_with_run(run_manager, marking_manager, sample_config, sample_marking_config):
    """Test associating marking configurations with a run version."""
    # Create a run version
    run_version = run_manager.create_run_version(
        config=sample_config,
        description="Test run",
        tags=["test"]
    )
    
    # Create marking configurations
    marking1 = marking_manager.create_marking_config(
        name="marking1",
        parameters={"threshold": 0.5},
        version="1.0.0"
    )
    
    marking2 = marking_manager.create_marking_config(
        name="marking2",
        parameters={"window_size": 10},
        version="1.0.0"
    )
    
    # Associate markings with the run
    updated_run = marking_manager.associate_markings_with_run(
        run_version.version_id,
        [marking1, marking2]
    )
    
    # Check that markings were associated
    assert "markings" in updated_run.config
    assert len(updated_run.config["markings"]) == 2
    
    # Verify marking info
    marking_info = updated_run.config["markings"]
    assert any(m["name"] == "marking1" for m in marking_info)
    assert any(m["name"] == "marking2" for m in marking_info)
    
    # Get markings for run
    retrieved_markings = marking_manager.get_markings_for_run(run_version.version_id)
    assert len(retrieved_markings) == 2
    assert any(m.name == "marking1" for m in retrieved_markings)
    assert any(m.name == "marking2" for m in retrieved_markings)


def test_create_and_get_marking_bundle(marking_manager, sample_marking_config):
    """Test creating and retrieving a marking bundle."""
    # Create marking configurations
    marking1 = marking_manager.create_marking_config(
        name="marking1",
        parameters={"threshold": 0.5},
        version="1.0.0"
    )
    
    marking2 = marking_manager.create_marking_config(
        name="marking2",
        parameters={"window_size": 10},
        version="1.0.0"
    )
    
    # Create a bundle
    bundle = marking_manager.create_marking_bundle(
        name="test_bundle",
        marking_configs=[marking1, marking2],
        description="Test bundle"
    )
    
    # Check bundle properties
    assert bundle["name"] == "test_bundle"
    assert bundle["description"] == "Test bundle"
    assert "created_at" in bundle
    assert len(bundle["markings"]) == 2
    
    # Get the bundle
    retrieved = marking_manager.get_marking_bundle("test_bundle")
    assert retrieved["name"] == "test_bundle"
    assert retrieved["description"] == "Test bundle"
    assert len(retrieved["markings"]) == 2
    
    # Get markings from bundle
    markings = marking_manager.get_markings_from_bundle("test_bundle")
    assert len(markings) == 2
    assert any(m.name == "marking1" for m in markings)
    assert any(m.name == "marking2" for m in markings)