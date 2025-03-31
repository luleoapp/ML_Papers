"""
Performance monitoring utilities for tracking execution times.

This module provides a PerformanceMonitor class for tracking execution times
of different operations and generating reports.
"""

import time
import threading
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import statistics

from backtest_simulator.utils.logging_config import get_logger


class PerformanceMonitor:
    """Monitors and tracks performance metrics for operations."""
    
    def __init__(self, instance_name: str = None):
        """Initialize the performance monitor.
        
        Args:
            instance_name: Optional name for this monitor instance
        """
        # Set up logger
        self.logger = get_logger(f"{__name__}.PerformanceMonitor")
        
        # Generate instance name if not provided
        self.instance_name = instance_name or f"monitor_{int(time.time())}"
        self.logger.debug(f"Initializing performance monitor {self.instance_name}")
        
        # Set up thread-local storage for tracking ongoing operations
        self._thread_local = threading.local()
        
        # Set up global metrics storage
        self._metrics_lock = threading.RLock()
        self._start_times = {}
        self._durations = defaultdict(list)
        self._counts = defaultdict(int)
        self._last_operation_time = {}
        
        # Start time for the entire session
        self._session_start_time = time.time()
    
    def start_operation(self, operation_name: str) -> None:
        """Start timing an operation.
        
        Args:
            operation_name: Name of the operation to time
        """
        # Initialize thread-local dictionary for ongoing operations
        if not hasattr(self._thread_local, "ongoing_operations"):
            self._thread_local.ongoing_operations = {}
        
        # Record start time
        self._thread_local.ongoing_operations[operation_name] = time.time()
    
    def end_operation(self, operation_name: str) -> float:
        """End timing an operation and record its duration.
        
        Args:
            operation_name: Name of the operation to end
            
        Returns:
            Duration of the operation in seconds, or -1 if not started
        """
        # Check if the operation was started
        if not hasattr(self._thread_local, "ongoing_operations") or operation_name not in self._thread_local.ongoing_operations:
            self.logger.warning(f"Operation {operation_name} was not started")
            return -1
        
        # Calculate duration
        start_time = self._thread_local.ongoing_operations[operation_name]
        end_time = time.time()
        duration = end_time - start_time
        
        # Remove from ongoing operations
        del self._thread_local.ongoing_operations[operation_name]
        
        # Update metrics
        with self._metrics_lock:
            self._durations[operation_name].append(duration)
            self._counts[operation_name] += 1
            self._last_operation_time[operation_name] = end_time
        
        return duration
    
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all metrics collected so far.
        
        Returns:
            Dictionary of metrics by operation
        """
        with self._metrics_lock:
            metrics = {}
            
            for operation_name in self._durations.keys():
                durations = self._durations[operation_name]
                count = self._counts[operation_name]
                
                if durations:
                    metrics[operation_name] = {
                        "count": count,
                        "total_duration": sum(durations),
                        "average_duration": sum(durations) / count,
                        "min_duration": min(durations),
                        "max_duration": max(durations),
                        "last_operation_time": self._last_operation_time.get(operation_name, 0)
                    }
                    
                    # Add percentiles and standard deviation if we have enough data
                    if len(durations) >= 3:
                        metrics[operation_name].update({
                            "median_duration": statistics.median(durations),
                            "std_deviation": statistics.stdev(durations),
                            "p90_duration": sorted(durations)[int(count * 0.9)] if count >= 10 else None,
                            "p95_duration": sorted(durations)[int(count * 0.95)] if count >= 20 else None,
                            "p99_duration": sorted(durations)[int(count * 0.99)] if count >= 100 else None
                        })
            
            # Add session metrics
            session_duration = time.time() - self._session_start_time
            metrics["_session"] = {
                "start_time": self._session_start_time,
                "duration": session_duration,
                "operations_count": sum(self._counts.values())
            }
            
            return metrics
    
    def get_summary_text(self) -> str:
        """Get a text summary of performance metrics.
        
        Returns:
            Text summary of performance metrics
        """
        metrics = self.get_metrics()
        
        lines = [f"Performance Monitor Summary ({self.instance_name}):"]
        lines.append("-" * 80)
        
        # Add session info
        session_metrics = metrics.pop("_session", {})
        session_duration = session_metrics.get("duration", 0)
        operations_count = session_metrics.get("operations_count", 0)
        
        lines.append(f"Session duration: {session_duration:.2f}s")
        lines.append(f"Total operations: {operations_count}")
        lines.append("-" * 80)
        
        # Add operation metrics
        lines.append(f"{'Operation':<30} {'Count':>8} {'Total (s)':>12} {'Avg (s)':>10} {'Min (s)':>10} {'Max (s)':>10}")
        lines.append("-" * 80)
        
        # Sort operations by total duration (descending)
        sorted_ops = sorted(metrics.items(), key=lambda x: x[1]["total_duration"], reverse=True)
        
        for operation_name, operation_metrics in sorted_ops:
            count = operation_metrics["count"]
            total = operation_metrics["total_duration"]
            avg = operation_metrics["average_duration"]
            min_duration = operation_metrics["min_duration"]
            max_duration = operation_metrics["max_duration"]
            
            lines.append(f"{operation_name:<30} {count:>8} {total:>12.2f} {avg:>10.4f} {min_duration:>10.4f} {max_duration:>10.4f}")
        
        return "\n".join(lines)
    
    def get_json(self) -> str:
        """Get a JSON representation of performance metrics.
        
        Returns:
            JSON string of performance metrics
        """
        metrics = self.get_metrics()
        return json.dumps(metrics, indent=2)
    
    def get_csv(self) -> str:
        """Get a CSV representation of performance metrics.
        
        Returns:
            CSV string of performance metrics
        """
        metrics = self.get_metrics()
        
        lines = ["operation,count,total_duration,average_duration,min_duration,max_duration"]
        
        for operation_name, operation_metrics in metrics.items():
            if operation_name == "_session":
                continue
                
            count = operation_metrics["count"]
            total = operation_metrics["total_duration"]
            avg = operation_metrics["average_duration"]
            min_duration = operation_metrics["min_duration"]
            max_duration = operation_metrics["max_duration"]
            
            lines.append(f"{operation_name},{count},{total},{avg},{min_duration},{max_duration}")
        
        return "\n".join(lines)
    
    def get_html(self) -> str:
        """Get an HTML representation of performance metrics.
        
        Returns:
            HTML string of performance metrics
        """
        metrics = self.get_metrics()
        
        # Session metrics
        session_metrics = metrics.pop("_session", {})
        session_duration = session_metrics.get("duration", 0)
        operations_count = session_metrics.get("operations_count", 0)
        
        # Start HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Performance Monitor Report - {self.instance_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
                th {{ background-color: #f2f2f2; }}
                th:first-child, td:first-child {{ text-align: left; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .header {{ background-color: #4CAF50; color: white; padding: 15px; }}
                .summary {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Performance Monitor Report</h1>
                <p>Instance: {self.instance_name}</p>
                <p>Generated: {datetime.now().isoformat()}</p>
            </div>
            
            <div class="summary">
                <h2>Session Summary</h2>
                <p>Total duration: {session_duration:.2f} seconds</p>
                <p>Total operations: {operations_count}</p>
            </div>
            
            <h2>Operation Metrics</h2>
            <table>
                <tr>
                    <th>Operation</th>
                    <th>Count</th>
                    <th>Total (s)</th>
                    <th>Average (s)</th>
                    <th>Median (s)</th>
                    <th>Min (s)</th>
                    <th>Max (s)</th>
                    <th>Std Dev</th>
                </tr>
        """
        
        # Sort operations by total duration (descending)
        sorted_ops = sorted(metrics.items(), key=lambda x: x[1]["total_duration"], reverse=True)
        
        # Add rows
        for operation_name, operation_metrics in sorted_ops:
            count = operation_metrics["count"]
            total = operation_metrics["total_duration"]
            avg = operation_metrics["average_duration"]
            min_duration = operation_metrics["min_duration"]
            max_duration = operation_metrics["max_duration"]
            median = operation_metrics.get("median_duration", "N/A")
            std_dev = operation_metrics.get("std_deviation", "N/A")
            
            if isinstance(median, float):
                median = f"{median:.4f}"
            if isinstance(std_dev, float):
                std_dev = f"{std_dev:.4f}"
            
            html += f"""
                <tr>
                    <td>{operation_name}</td>
                    <td>{count}</td>
                    <td>{total:.2f}</td>
                    <td>{avg:.4f}</td>
                    <td>{median}</td>
                    <td>{min_duration:.4f}</td>
                    <td>{max_duration:.4f}</td>
                    <td>{std_dev}</td>
                </tr>
            """
        
        # End HTML
        html += """
            </table>
        </body>
        </html>
        """
        
        return html
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._metrics_lock:
            self._start_times = {}
            self._durations = defaultdict(list)
            self._counts = defaultdict(int)
            self._last_operation_time = {}
            self._session_start_time = time.time()
        
        # Clear thread-local storage
        if hasattr(self._thread_local, "ongoing_operations"):
            self._thread_local.ongoing_operations = {}