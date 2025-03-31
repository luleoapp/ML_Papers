"""Tests for the callback system and parallel processing functionality."""

import os
import unittest
import tempfile
import time
import threading
import queue
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any

import pandas as pd
import numpy as np

from backtest_simulator.utils.logging_config import LoggerFactory
from backtest_simulator.core.callback_manager import CallbackManager, global_callback_handler
from backtest_simulator.core.thread_manager import ThreadManager
from backtest_simulator.core.pybind_interface import CPPBacktestEngine
from backtest_simulator.engine import BacktestEngine
from backtest_simulator.config.settings import BacktestConfig


class TestCallbackSystem(unittest.TestCase):
    """Tests for the callback system."""
    
    def setUp(self):
        """Set up the test environment."""
        # Set up logging for tests
        LoggerFactory.setup_logging(
            log_level="DEBUG",
            console_level="INFO",
            file_level="DEBUG"
        )
        
        # Create a temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_data_dir = Path(self.temp_dir.name)
        
        # Create test data for a couple of days
        self._create_test_data()
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        self.temp_dir.cleanup()
    
    def _create_test_data(self):
        """Create test data for the callback system tests."""
        # Create directories for two dates
        date1 = datetime.now() - timedelta(days=2)
        date2 = datetime.now() - timedelta(days=1)
        
        date1_str = date1.strftime("%Y%m%d")
        date2_str = date2.strftime("%Y%m%d")
        
        date1_dir = self.test_data_dir / date1_str
        date2_dir = self.test_data_dir / date2_str
        
        date1_dir.mkdir(exist_ok=True)
        date2_dir.mkdir(exist_ok=True)
        
        # Create some mock tick data files
        exchanges = ["XNAS", "XNYS"]
        
        for exchange in exchanges:
            # Create files for each date
            with open(date1_dir / f"{exchange}_{date1_str}.parquet", "w") as f:
                f.write("MOCK TICK DATA")
            
            with open(date2_dir / f"{exchange}_{date2_str}.parquet", "w") as f:
                f.write("MOCK TICK DATA")
    
    def test_callback_manager(self):
        """Test the CallbackManager functionality."""
        # Create a callback manager
        callback_manager = CallbackManager(max_queue_size=100)
        
        # Create a queue to store the uploaded markings
        uploaded_markings = []
        
        # Define an upload function that just stores the markings
        def upload_func(markings):
            uploaded_markings.extend(markings)
            return True
        
        # Start processing
        callback_manager.start_processing(upload_func)
        
        try:
            # Create and send some test markings
            test_markings = []
            for i in range(10):
                marking = {
                    "ticker": f"SYM{i}",
                    "trade_time": int(time.time() * 1_000_000_000),
                    "price": 100.0 + i,
                    "qty": 100 * (i + 1),
                    "marking1": i % 3 - 1,
                    "marking2": float(i) / 10.0
                }
                test_markings.append(marking)
            
            # Process the markings
            callback_manager.process_marking_batch(test_markings)
            
            # Wait for processing to complete
            time.sleep(1.0)
            
            # Check that all markings were uploaded
            self.assertEqual(len(uploaded_markings), len(test_markings))
            
            # Check the content of the uploaded markings
            for i, marking in enumerate(uploaded_markings):
                self.assertEqual(marking["ticker"], test_markings[i]["ticker"])
                self.assertEqual(marking["price"], test_markings[i]["price"])
                self.assertEqual(marking["qty"], test_markings[i]["qty"])
                self.assertEqual(marking["marking1"], test_markings[i]["marking1"])
                self.assertEqual(marking["marking2"], test_markings[i]["marking2"])
        
        finally:
            # Stop processing
            callback_manager.stop_processing()
    
    def test_thread_manager(self):
        """Test the ThreadManager functionality."""
        # Create a thread manager
        thread_manager = ThreadManager(
            max_processing_workers=2,
            max_upload_workers=2,
            parallel_uploads=True
        )
        
        # Define a task function that sleeps for a bit and returns a value
        def task_func(item):
            time.sleep(0.1)
            return item * 2
        
        # Create some test items
        test_items = list(range(10))
        
        # Process the items
        results = thread_manager.parallel_execute(
            items=test_items,
            task_func=task_func,
            description="Test parallel execution"
        )
        
        # Check the results
        self.assertEqual(len(results), len(test_items))
        for i, result in enumerate(results):
            self.assertEqual(result, test_items[i] * 2)
        
        # Shutdown the thread manager
        thread_manager.shutdown()
    
    def test_backtest_engine_with_callbacks(self):
        """Test the BacktestEngine with callbacks enabled."""
        # Create a mock upload function to capture markings
        uploaded_markings = []
        
        def mock_upload_func(markings):
            uploaded_markings.extend(markings)
            return True
        
        # Initialize the backtest engine with callbacks enabled
        engine = BacktestEngine(
            use_cloud_store=False,  # Don't use real cloud store for tests
            parallel_processing=True,
            max_workers=2,
            max_window_size=60,  # Use a small window for testing
            log_level="INFO"
        )
        
        # Configure the engine
        engine.configure(
            start_date=datetime.now() - timedelta(days=2),
            end_date=datetime.now() - timedelta(days=1),
            exchanges=["XNAS", "XNYS"],
            universe=["AAPL", "MSFT", "GOOGL"],
            data_path=str(self.test_data_dir)
        )
        
        # Manually set up the callback system for testing
        # This bypasses the cloud store requirement
        engine.thread_manager.callback_manager.start_processing(mock_upload_func)
        
        try:
            # Run the backtest
            results = engine.run()
            
            # Give some time for callbacks to be processed
            time.sleep(2.0)
            
            # Check that we got some results
            self.assertTrue(len(results) > 0)
            
            # Check that some markings were uploaded
            self.assertTrue(len(uploaded_markings) > 0)
            
            # Check the structure of the markings
            for marking in uploaded_markings[:5]:  # Just check a few
                self.assertIn("ticker", marking)
                self.assertIn("trade_time", marking)
                self.assertIn("price", marking)
                self.assertIn("qty", marking)
        
        finally:
            # Shutdown the engine
            engine.shutdown()


if __name__ == '__main__':
    unittest.main()