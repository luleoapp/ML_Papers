"""Tests for the integration of versioning with BacktestEngine."""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from backtest_simulator import BacktestEngine
from backtest_simulator.config.settings import BacktestConfig
from backtest_simulator.versioning.run_manager import RunManager
from backtest_simulator.versioning.marking_config import MarkingManager


@pytest.fixture
def temp_store_path():
    """Create a temporary directory for storing run data."""
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    
    yield temp_dir
    
    # Clean up after tests
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_config():
    """Return a sample configuration for testing."""
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today - timedelta(days=1)
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "exchanges": ["XNAS"],
        "universe": ["AAPL", "MSFT", "GOOGL"],
        "max_window_size": 3600,
        "use_multiple_exchanges": False
    }


@pytest.fixture
def sample_marking_configs():
    """Return sample marking configurations for testing."""
    return [
        {
            "name": "iso_marking",
            "parameters": {
                "threshold": 0.5,
                "window_size": 10,
                "use_log_returns": True
            },
            "version": "1.0.0",
            "description": "ISO trade marking configuration"
        },
        {
            "name": "sweep_marking",
            "parameters": {
                "min_size": 1000,
                "max_levels": 3,
                "aggressive_side_only": True
            },
            "version": "1.0.0",
            "description": "Sweep trade marking configuration"
        }
    ]


@pytest.fixture
def versioned_engine(temp_store_path, sample_config):
    """Return a configured BacktestEngine with versioning enabled."""
    engine = BacktestEngine(use_versioning=True, local_store_path=temp_store_path)
    
    # Configure the engine
    engine.configure(
        start_date=sample_config["start_date"],
        end_date=sample_config["end_date"],
        exchanges=sample_config["exchanges"],
        universe=sample_config["universe"],
        max_window_size=sample_config["max_window_size"],
        use_multiple_exchanges=sample_config["use_multiple_exchanges"],
        run_description="Test backtest run",
        run_tags=["test", "initial"]
    )
    
    return engine


@pytest.fixture
def versioned_engine_with_markings(temp_store_path, sample_config, sample_marking_configs):
    """Return a configured BacktestEngine with versioning and markings."""
    engine = BacktestEngine(use_versioning=True, local_store_path=temp_store_path)
    
    # Configure the engine with markings
    engine.configure(
        start_date=sample_config["start_date"],
        end_date=sample_config["end_date"],
        exchanges=sample_config["exchanges"],
        universe=sample_config["universe"],
        max_window_size=sample_config["max_window_size"],
        use_multiple_exchanges=sample_config["use_multiple_exchanges"],
        marking_configs=sample_marking_configs,
        run_description="Test backtest run with markings",
        run_tags=["test", "markings"]
    )
    
    return engine


def test_engine_versioning_initialization(temp_store_path):
    """Test initialization of BacktestEngine with versioning."""
    # Initialize with versioning disabled
    engine1 = BacktestEngine(use_versioning=False)
    assert not engine1.use_versioning
    assert engine1.run_manager is None
    assert engine1.marking_manager is None
    
    # Initialize with versioning enabled
    engine2 = BacktestEngine(use_versioning=True, local_store_path=temp_store_path)
    assert engine2.use_versioning
    assert engine2.run_manager is not None
    assert engine2.marking_manager is not None
    assert engine2.current_run_version is None  # Not configured yet


def test_engine_configure_with_versioning(versioned_engine):
    """Test configuring the engine with versioning."""
    # Check that a run version was created
    assert versioned_engine.current_run_version is not None
    
    # Check run version properties
    run_version = versioned_engine.current_run_version
    assert "start_date" in run_version.config
    assert "end_date" in run_version.config
    assert run_version.config["exchanges"] == ["XNAS"]
    assert run_version.config["universe"] == ["AAPL", "MSFT", "GOOGL"]
    assert run_version.config["max_window_size"] == 3600
    assert run_version.description == "Test backtest run"
    assert "test" in run_version.tags
    assert "initial" in run_version.tags


def test_engine_configure_with_markings(versioned_engine_with_markings):
    """Test configuring the engine with markings."""
    # Check that a run version was created
    assert versioned_engine_with_markings.current_run_version is not None
    
    # Check that markings were associated
    run_version = versioned_engine_with_markings.current_run_version
    assert "markings" in run_version.config
    assert len(run_version.config["markings"]) == 2
    
    # Check marking properties
    marking_info = run_version.config["markings"]
    assert any(m["name"] == "iso_marking" for m in marking_info)
    assert any(m["name"] == "sweep_marking" for m in marking_info)
    
    # Get markings for run
    markings = versioned_engine_with_markings.get_markings_for_run(run_version.version_id)
    assert len(markings) == 2
    assert any(m["name"] == "iso_marking" for m in markings)
    assert any(m["name"] == "sweep_marking" for m in markings)


def test_engine_run_with_versioning(versioned_engine):
    """Test running the engine with versioning."""
    # Run the backtest
    results = versioned_engine.run()
    
    # Check that metrics were recorded
    run_version = versioned_engine.current_run_version
    run_id = run_version.version_id
    
    # Get run version
    run_info = versioned_engine.get_run_version(run_id)
    assert run_info is not None
    assert "metrics" in run_info
    
    # Check specific metrics
    metrics = run_info["metrics"]
    assert "run_duration_seconds" in metrics
    assert "eligible_dates" in metrics
    assert "processed_dates" in metrics
    assert "result_count" in metrics
    assert "symbols_count" in metrics
    assert metrics["symbols_count"] == 3  # AAPL, MSFT, GOOGL


def test_engine_save_results_with_versioning(versioned_engine, temp_store_path):
    """Test saving results with versioning."""
    # Run the backtest
    results = versioned_engine.run()
    
    # Create a temporary results file
    results_path = os.path.join(temp_store_path, "results.parquet")
    
    # Save results
    versioned_engine.save_results(results_path, store_with_run=True)
    
    # Check that results file was created
    assert os.path.exists(results_path)
    
    # Check that results are stored with the run version
    run_id = versioned_engine.current_run_version.version_id
    artifacts_path = versioned_engine.run_manager.local_store_path / "artifacts" / run_id / "results"
    assert artifacts_path.exists()


def test_engine_versioning_methods(versioned_engine):
    """Test versioning methods in the engine."""
    # Get current run ID
    run_id = versioned_engine.get_current_run_id()
    assert run_id is not None
    
    # List run versions
    versions = versioned_engine.list_run_versions()
    assert len(versions) == 1
    assert versions[0]["version_id"] == run_id
    
    # Get run version
    run_info = versioned_engine.get_run_version(run_id)
    assert run_info["version_id"] == run_id
    
    # Mark as production
    success = versioned_engine.mark_as_production(run_id)
    assert success
    
    # Get production version
    prod_version = versioned_engine.get_production_version()
    assert prod_version["version_id"] == run_id


def test_create_marking_config(versioned_engine):
    """Test creating a marking configuration."""
    # Create a marking configuration
    marking = versioned_engine.create_marking_config(
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


def test_rerun_version(versioned_engine, sample_config):
    """Test rerunning a version."""
    # Run the backtest to generate a version
    results = versioned_engine.run()
    original_run_id = versioned_engine.get_current_run_id()
    
    # Create a marking configuration to associate with the run
    marking = versioned_engine.create_marking_config(
        name="test_marking",
        parameters={"threshold": 0.5},
        version="1.0.0"
    )
    
    # Associate marking with the run
    versioned_engine.marking_manager.associate_markings_with_run(
        original_run_id,
        [marking]
    )
    
    # Create parameter overrides
    overrides = {
        "max_window_size": 7200,  # Changed from 3600
    }
    
    # Rerun the version with overrides
    new_run_id = versioned_engine.rerun_version(
        original_run_id,
        override_params=overrides,
        description="Rerun with modified parameters"
    )
    
    # Check that a new run version was created
    assert new_run_id != original_run_id
    
    # Check that parameters were overridden
    new_run_info = versioned_engine.get_run_version(new_run_id)
    assert new_run_info["config"]["max_window_size"] == 7200
    
    # Check that markings were transferred
    markings = versioned_engine.get_markings_for_run(new_run_id)
    assert len(markings) == 1
    assert markings[0]["name"] == "test_marking"
    
    # Check that tags were set correctly
    assert "rerun" in new_run_info["tags"]
    assert any(tag.startswith("parent:") for tag in new_run_info["tags"])