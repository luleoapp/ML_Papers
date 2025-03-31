"""Tests for the cloud storage integration."""

import pytest
from datetime import datetime
import pandas as pd
import xarray as xr

from backtest_simulator.data.cloud_store import DataStoreClient


@pytest.fixture
def datastore_client():
    """Return a configured DataStore client for testing."""
    return DataStoreClient(datastore_name="test", workspace="test_workspace").connect()


@pytest.fixture
def sample_results():
    """Return sample backtest results for testing."""
    return [
        {
            "date": "2023-01-01",
            "exchange": "XNAS",
            "symbol": "AAPL",
            "trade_id": 1,
            "trade_time": "2023-01-01T09:30:00.000000",
            "trade_price": 100.0,
            "trade_size": 100,
            "trade_side": "buy",
            "return_10s": 0.001,
            "is_iso": True,
        },
        {
            "date": "2023-01-01",
            "exchange": "XNAS",
            "symbol": "MSFT",
            "trade_id": 1,
            "trade_time": "2023-01-01T09:30:00.000000",
            "trade_price": 200.0,
            "trade_size": 50,
            "trade_side": "sell",
            "return_10s": -0.002,
            "is_iso": False,
        }
    ]


def test_datastore_init():
    """Test that the DataStore client initializes correctly."""
    client = DataStoreClient()
    assert client.datastore_name == "prod"
    assert client.workspace is not None
    
    # Test with custom parameters
    client = DataStoreClient(datastore_name="test", workspace="test_workspace")
    assert client.datastore_name == "test"
    assert client.workspace == "test_workspace"


def test_datastore_connect(datastore_client):
    """Test that the DataStore client connects correctly."""
    assert datastore_client._client is not None


def test_upload_results(datastore_client, sample_results):
    """Test uploading results to DataStore."""
    # Convert to DataFrame
    df = pd.DataFrame(sample_results)
    
    # Should not raise any exceptions
    datastore_client.upload_results(
        df,
        dataset_name="test_results",
        description="Test results",
        partition="test_partition"
    )
    
    # Also test with list of dictionaries
    datastore_client.upload_results(
        sample_results,
        dataset_name="test_results_list",
        description="Test results from list",
        partition="test_partition"
    )


def test_upload_xarray_results(datastore_client, sample_results):
    """Test uploading xarray results to DataStore."""
    # Convert to DataFrame and then to xarray
    df = pd.DataFrame(sample_results)
    ds = df.set_index(['date', 'symbol']).to_xarray()
    
    # Should not raise any exceptions
    datastore_client.upload_xarray_results(
        ds,
        dataset_name="test_xarray_results",
        description="Test xarray results",
        partition="test_partition"
    )


def test_download_dataset(datastore_client):
    """Test downloading a dataset from DataStore."""
    # Test pandas format
    df = datastore_client.download_dataset(
        dataset_name="test_results",
        partition="test_partition",
        format_type="pandas"
    )
    assert isinstance(df, pd.DataFrame)
    
    # Test xarray format
    ds = datastore_client.download_dataset(
        dataset_name="test_xarray_results",
        partition="test_partition",
        format_type="xarray"
    )
    assert isinstance(ds, xr.Dataset)
    
    # Test with invalid format
    with pytest.raises(ValueError):
        datastore_client.download_dataset(
            dataset_name="test_results",
            partition="test_partition",
            format_type="invalid_format"
        )