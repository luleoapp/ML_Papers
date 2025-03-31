"""Tests for the performance monitoring system."""

import os
import time
import unittest
import tempfile
from pathlib import Path
import json
import shutil

import pandas as pd
import numpy as np

from backtest_simulator.utils.performance import PerformanceMonitor, timed_operation


class TestPerformanceMonitor(unittest.TestCase):
    """Tests for the PerformanceMonitor class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for logs
        self.temp_dir = tempfile.mkdtemp()
        self.perf_monitor = PerformanceMonitor(log_dir=self.temp_dir, enabled=True)
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_start_stop_timer(self):
        """Test starting and stopping a timer."""
        # Start a timer
        timer_id = self.perf_monitor.start_timer("test_operation", {"test_param": 123})
        
        # Sleep for a bit
        time.sleep(0.1)
        
        # Stop the timer
        metrics = self.perf_monitor.stop_timer(timer_id, {"result": "success"})
        
        # Check that the timer metrics are correct
        self.assertEqual(metrics["operation"], "test_operation")
        self.assertGreaterEqual(metrics["duration_seconds"], 0.1)
        self.assertEqual(metrics["metadata"]["test_param"], 123)
        self.assertEqual(metrics["additional_metrics"]["result"], "success")
        
        # Check that a metrics file was created
        metrics_files = list(Path(self.temp_dir).glob("*.json"))
        self.assertGreaterEqual(len(metrics_files), 1)
    
    def test_disabled_monitor(self):
        """Test that the monitor does nothing when disabled."""
        # Create a disabled monitor
        disabled_monitor = PerformanceMonitor(log_dir=self.temp_dir, enabled=False)
        
        # Start a timer
        timer_id = disabled_monitor.start_timer("test_operation", {"test_param": 123})
        
        # Check that the timer ID is just the operation name
        self.assertEqual(timer_id, "test_operation")
        
        # Sleep for a bit
        time.sleep(0.1)
        
        # Stop the timer
        metrics = disabled_monitor.stop_timer(timer_id, {"result": "success"})
        
        # Check that no metrics were returned
        self.assertEqual(metrics, {})
        
        # Check that no metrics file was created
        metrics_files = list(Path(self.temp_dir).glob("test_operation_*.json"))
        self.assertEqual(len(metrics_files), 0)
    
    def test_log_database_metrics(self):
        """Test logging database metrics."""
        # Log database metrics
        self.perf_monitor.log_database_metrics(
            dataset_name="test_dataset",
            record_count=1000,
            size_bytes=1024 * 1024,  # 1 MB
            operation_type="upload",
            duration_seconds=2.5,
            additional_info={"format": "pandas"}
        )
        
        # Check that a metrics file was created
        metrics_files = list(Path(self.temp_dir).glob("database_upload_*.json"))
        self.assertGreaterEqual(len(metrics_files), 1)
        
        # Check the content of the metrics file
        with open(metrics_files[0], 'r') as f:
            metrics = json.load(f)
        
        self.assertEqual(metrics["operation"], "database_upload")
        self.assertEqual(metrics["dataset_name"], "test_dataset")
        self.assertEqual(metrics["record_count"], 1000)
        self.assertEqual(metrics["size_bytes"], 1024 * 1024)
        self.assertEqual(metrics["duration_seconds"], 2.5)
        self.assertEqual(metrics["records_per_second"], 400)  # 1000 / 2.5
        self.assertEqual(metrics["mb_per_second"], 1.0 / 2.5)
        self.assertEqual(metrics["additional_info"]["format"], "pandas")
    
    def test_log_backtest_metrics(self):
        """Test logging backtest metrics."""
        # Log backtest metrics
        self.perf_monitor.log_backtest_metrics(
            backtest_id="test_backtest",
            symbols_count=100,
            date_range="2023-01-01 to 2023-01-31",
            processed_files=31,
            result_count=10000,
            duration_seconds=60.0,
            additional_metrics={"custom_metric": 123}
        )
        
        # Check that a metrics file was created
        metrics_files = list(Path(self.temp_dir).glob("backtest_run_*.json"))
        self.assertGreaterEqual(len(metrics_files), 1)
        
        # Check the content of the metrics file
        with open(metrics_files[0], 'r') as f:
            metrics = json.load(f)
        
        self.assertEqual(metrics["operation"], "backtest_run")
        self.assertEqual(metrics["backtest_id"], "test_backtest")
        self.assertEqual(metrics["symbols_count"], 100)
        self.assertEqual(metrics["date_range"], "2023-01-01 to 2023-01-31")
        self.assertEqual(metrics["processed_files"], 31)
        self.assertEqual(metrics["result_count"], 10000)
        self.assertEqual(metrics["duration_seconds"], 60.0)
        self.assertEqual(metrics["results_per_second"], 10000 / 60.0)
        self.assertEqual(metrics["files_per_second"], 31 / 60.0)
        self.assertEqual(metrics["additional_metrics"]["custom_metric"], 123)
    
    def test_generate_report(self):
        """Test generating a performance report."""
        # Log some metrics
        self.perf_monitor.log_database_metrics(
            dataset_name="test_dataset1",
            record_count=1000,
            size_bytes=1024 * 1024,
            operation_type="upload",
            duration_seconds=1.5
        )
        
        self.perf_monitor.log_database_metrics(
            dataset_name="test_dataset2",
            record_count=2000,
            size_bytes=2 * 1024 * 1024,
            operation_type="download",
            duration_seconds=2.0
        )
        
        self.perf_monitor.log_backtest_metrics(
            backtest_id="test_backtest",
            symbols_count=100,
            date_range="2023-01-01 to 2023-01-31",
            processed_files=31,
            result_count=10000,
            duration_seconds=60.0
        )
        
        # Generate a report in each format
        json_report = self.perf_monitor.generate_report(
            output_file=os.path.join(self.temp_dir, "report.json"),
            format_type="json"
        )
        
        csv_report = self.perf_monitor.generate_report(
            output_file=os.path.join(self.temp_dir, "report.csv"),
            format_type="csv"
        )
        
        html_report = self.perf_monitor.generate_report(
            output_file=os.path.join(self.temp_dir, "report.html"),
            format_type="html"
        )
        
        # Check that the reports were created
        self.assertTrue(os.path.exists(json_report))
        self.assertTrue(os.path.exists(csv_report))
        self.assertTrue(os.path.exists(html_report))
        
        # Check the content of the JSON report
        with open(json_report, 'r') as f:
            report_data = json.load(f)
        
        self.assertEqual(len(report_data["operations"]), 3)
        self.assertEqual(len(report_data["type_statistics"]), 3)
        self.assertIn("backtest_run", report_data["type_statistics"])
        self.assertIn("database_upload", report_data["type_statistics"])
        self.assertIn("database_download", report_data["type_statistics"])
        
        # Check the content of the CSV report
        df = pd.read_csv(csv_report)
        self.assertEqual(len(df), 3)
        
        # Check the content of the HTML report (just check it's valid HTML)
        with open(html_report, 'r') as f:
            html_content = f.read()
        
        self.assertIn("<html>", html_content)
        self.assertIn("</html>", html_content)
        self.assertIn("<table>", html_content)
        self.assertIn("Performance Report", html_content)


class TestTimedOperationDecorator(unittest.TestCase):
    """Tests for the timed_operation decorator."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for logs
        self.temp_dir = tempfile.mkdtemp()
        
        # Set environment variable for log dir
        os.environ['BACKTEST_LOG_DIR'] = self.temp_dir
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
        
        # Remove environment variable
        del os.environ['BACKTEST_LOG_DIR']
    
    def test_timed_operation_decorator(self):
        """Test the timed_operation decorator."""
        @timed_operation("test_operation")
        def test_function(x, y):
            time.sleep(0.1)
            return x + y
        
        # Call the decorated function
        result = test_function(2, 3)
        
        # Check the result
        self.assertEqual(result, 5)
        
        # Check that a metrics file was created
        metrics_files = list(Path(self.temp_dir).glob("test_operation_*.json"))
        self.assertGreaterEqual(len(metrics_files), 1)
    
    def test_timed_operation_with_class_instance(self):
        """Test the timed_operation decorator with a class instance."""
        class TestClass:
            def __init__(self):
                self._performance_monitor = PerformanceMonitor(
                    log_dir=self.temp_dir,
                    enabled=True
                )
            
            @timed_operation("instance_method")
            def test_method(self, x, y):
                time.sleep(0.1)
                return x * y
        
        # Create an instance and call the decorated method
        instance = TestClass()
        result = instance.test_method(2, 3)
        
        # Check the result
        self.assertEqual(result, 6)
        
        # Check that a metrics file was created
        metrics_files = list(Path(self.temp_dir).glob("instance_method_*.json"))
        self.assertGreaterEqual(len(metrics_files), 1)


if __name__ == '__main__':
    unittest.main()