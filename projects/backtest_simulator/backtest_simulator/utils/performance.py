"""Performance monitoring and metrics for backtest operations."""

import time
import json
import logging
import functools
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable
from pathlib import Path
import os

import pandas as pd
import numpy as np


class PerformanceMonitor:
    """Monitor and log performance metrics for backtest operations."""
    
    def __init__(self, 
                log_dir: Optional[str] = None, 
                enabled: bool = True,
                log_level: int = logging.INFO):
        """Initialize the performance monitor.
        
        Args:
            log_dir: Directory to store performance logs. Defaults to './performance_logs'.
            enabled: Whether performance monitoring is enabled.
            log_level: Logging level.
        """
        self.enabled = enabled
        self.log_dir = Path(log_dir) if log_dir else Path("./performance_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up logging
        self.logger = logging.getLogger("backtest_performance")
        self.logger.setLevel(log_level)
        
        # Add file handler if not already present
        if not self.logger.handlers:
            log_file = self.log_dir / "performance.log"
            file_handler = logging.FileHandler(str(log_file))
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        # Store current session metrics
        self.session_metrics = {
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "start_time": datetime.now().isoformat(),
            "operations": []
        }
        
        # Store running timers
        self.timers = {}
    
    def start_timer(self, operation_name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start a timer for an operation.
        
        Args:
            operation_name: Name of the operation being timed.
            metadata: Additional information about the operation.
            
        Returns:
            Timer ID that can be used to stop the timer.
        """
        if not self.enabled:
            return operation_name
            
        timer_id = f"{operation_name}_{time.time()}"
        self.timers[timer_id] = {
            "operation": operation_name,
            "start_time": time.time(),
            "metadata": metadata or {}
        }
        
        self.logger.info(f"Started timer for operation: {operation_name}")
        return timer_id
    
    def stop_timer(self, timer_id: str, additional_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Stop a timer and record the metrics.
        
        Args:
            timer_id: Timer ID returned by start_timer.
            additional_metrics: Additional metrics to record.
            
        Returns:
            Dictionary with timing metrics.
        """
        if not self.enabled or timer_id not in self.timers:
            return {}
            
        end_time = time.time()
        timer_info = self.timers.pop(timer_id)
        
        duration = end_time - timer_info["start_time"]
        operation = timer_info["operation"]
        
        # Create metrics
        metrics = {
            "operation": operation,
            "duration_seconds": duration,
            "start_time": datetime.fromtimestamp(timer_info["start_time"]).isoformat(),
            "end_time": datetime.fromtimestamp(end_time).isoformat(),
            "metadata": timer_info["metadata"]
        }
        
        # Add additional metrics
        if additional_metrics:
            metrics["additional_metrics"] = additional_metrics
        
        # Log metrics
        self.logger.info(f"Operation '{operation}' completed in {duration:.2f} seconds")
        if additional_metrics:
            for key, value in additional_metrics.items():
                self.logger.info(f"  {key}: {value}")
        
        # Add to session metrics
        self.session_metrics["operations"].append(metrics)
        
        # Write metrics to file
        self._write_metrics(metrics)
        
        return metrics
    
    def _write_metrics(self, metrics: Dict[str, Any]) -> None:
        """Write metrics to JSON file.
        
        Args:
            metrics: Metrics dictionary to write.
        """
        # Create a filename based on the operation and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        operation_name = metrics["operation"].replace(" ", "_").lower()
        filename = f"{operation_name}_{timestamp}.json"
        
        # Write to file
        metrics_file = self.log_dir / filename
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def log_database_metrics(self, 
                           dataset_name: str, 
                           record_count: int,
                           size_bytes: Optional[int] = None,
                           operation_type: str = "upload",
                           duration_seconds: Optional[float] = None,
                           additional_info: Optional[Dict[str, Any]] = None) -> None:
        """Log metrics for database operations.
        
        Args:
            dataset_name: Name of the dataset.
            record_count: Number of records processed.
            size_bytes: Size of the data in bytes.
            operation_type: Type of operation (upload, download, etc.).
            duration_seconds: Duration of the operation if already measured.
            additional_info: Additional information about the operation.
        """
        if not self.enabled:
            return
            
        metrics = {
            "operation": f"database_{operation_type}",
            "dataset_name": dataset_name,
            "record_count": record_count,
            "timestamp": datetime.now().isoformat()
        }
        
        if size_bytes is not None:
            metrics["size_bytes"] = size_bytes
            metrics["size_mb"] = size_bytes / (1024 * 1024)
        
        if duration_seconds is not None:
            metrics["duration_seconds"] = duration_seconds
            metrics["records_per_second"] = record_count / duration_seconds if duration_seconds > 0 else 0
            if size_bytes is not None:
                metrics["mb_per_second"] = (size_bytes / (1024 * 1024)) / duration_seconds if duration_seconds > 0 else 0
        
        if additional_info:
            metrics["additional_info"] = additional_info
        
        # Log the metrics
        self.logger.info(f"Database {operation_type} metrics for {dataset_name}:")
        self.logger.info(f"  Records: {record_count}")
        if size_bytes is not None:
            self.logger.info(f"  Size: {size_bytes / (1024 * 1024):.2f} MB")
        if duration_seconds is not None:
            self.logger.info(f"  Duration: {duration_seconds:.2f} seconds")
            self.logger.info(f"  Records/second: {record_count / duration_seconds if duration_seconds > 0 else 0:.2f}")
            if size_bytes is not None:
                self.logger.info(f"  MB/second: {(size_bytes / (1024 * 1024)) / duration_seconds if duration_seconds > 0 else 0:.2f}")
        
        # Add to session metrics
        self.session_metrics["operations"].append(metrics)
        
        # Write metrics to file
        self._write_metrics(metrics)
    
    def log_backtest_metrics(self,
                           backtest_id: str,
                           symbols_count: int,
                           date_range: str,
                           processed_files: int,
                           result_count: int,
                           duration_seconds: float,
                           additional_metrics: Optional[Dict[str, Any]] = None) -> None:
        """Log metrics specific to a backtest run.
        
        Args:
            backtest_id: Identifier for the backtest run.
            symbols_count: Number of symbols in the backtest.
            date_range: String representing the date range.
            processed_files: Number of data files processed.
            result_count: Number of result records.
            duration_seconds: Duration of the backtest in seconds.
            additional_metrics: Additional metrics specific to the backtest.
        """
        if not self.enabled:
            return
            
        metrics = {
            "operation": "backtest_run",
            "backtest_id": backtest_id,
            "symbols_count": symbols_count,
            "date_range": date_range,
            "processed_files": processed_files,
            "result_count": result_count,
            "duration_seconds": duration_seconds,
            "timestamp": datetime.now().isoformat(),
            "results_per_second": result_count / duration_seconds if duration_seconds > 0 else 0,
            "files_per_second": processed_files / duration_seconds if duration_seconds > 0 else 0
        }
        
        if additional_metrics:
            metrics["additional_metrics"] = additional_metrics
        
        # Log the metrics
        self.logger.info(f"Backtest run metrics for {backtest_id}:")
        self.logger.info(f"  Symbols: {symbols_count}")
        self.logger.info(f"  Date range: {date_range}")
        self.logger.info(f"  Processed files: {processed_files}")
        self.logger.info(f"  Result records: {result_count}")
        self.logger.info(f"  Duration: {duration_seconds:.2f} seconds")
        self.logger.info(f"  Results/second: {result_count / duration_seconds if duration_seconds > 0 else 0:.2f}")
        self.logger.info(f"  Files/second: {processed_files / duration_seconds if duration_seconds > 0 else 0:.2f}")
        
        # Add to session metrics
        self.session_metrics["operations"].append(metrics)
        
        # Write metrics to file
        self._write_metrics(metrics)
    
    def generate_report(self, 
                       output_file: Optional[str] = None, 
                       format_type: str = "json") -> Optional[str]:
        """Generate a performance report for the current session.
        
        Args:
            output_file: Path to write the report to. If None, generates a default path.
            format_type: Format of the report ("json", "csv", or "html").
            
        Returns:
            Path to the generated report.
        """
        if not self.enabled:
            return None
            
        # Update session end time
        self.session_metrics["end_time"] = datetime.now().isoformat()
        
        # Calculate aggregate metrics
        total_duration = 0
        operation_types = {}
        
        for op in self.session_metrics["operations"]:
            if "duration_seconds" in op:
                total_duration += op["duration_seconds"]
            
            op_type = op["operation"]
            if op_type not in operation_types:
                operation_types[op_type] = []
            operation_types[op_type].append(op)
        
        # Add summary stats
        self.session_metrics["summary"] = {
            "total_duration_seconds": total_duration,
            "operation_count": len(self.session_metrics["operations"]),
            "operation_types": list(operation_types.keys())
        }
        
        # Add per-operation-type stats
        type_stats = {}
        for op_type, ops in operation_types.items():
            durations = [op.get("duration_seconds", 0) for op in ops]
            type_stats[op_type] = {
                "count": len(ops),
                "total_duration": sum(durations),
                "avg_duration": sum(durations) / len(durations) if durations else 0,
                "min_duration": min(durations) if durations else 0,
                "max_duration": max(durations) if durations else 0
            }
        
        self.session_metrics["type_statistics"] = type_stats
        
        # Create default output path if none provided
        if not output_file:
            session_id = self.session_metrics["session_id"]
            if format_type == "json":
                output_file = str(self.log_dir / f"performance_report_{session_id}.json")
            elif format_type == "csv":
                output_file = str(self.log_dir / f"performance_report_{session_id}.csv")
            elif format_type == "html":
                output_file = str(self.log_dir / f"performance_report_{session_id}.html")
            else:
                output_file = str(self.log_dir / f"performance_report_{session_id}.json")
                format_type = "json"
        
        # Write the report
        if format_type == "json":
            with open(output_file, 'w') as f:
                json.dump(self.session_metrics, f, indent=2)
        elif format_type == "csv":
            # Flatten operations for CSV format
            flat_ops = []
            for op in self.session_metrics["operations"]:
                flat_op = {k: v for k, v in op.items() if not isinstance(v, (dict, list))}
                if "additional_metrics" in op:
                    for k, v in op["additional_metrics"].items():
                        if not isinstance(v, (dict, list)):
                            flat_op[f"additional_{k}"] = v
                if "metadata" in op:
                    for k, v in op["metadata"].items():
                        if not isinstance(v, (dict, list)):
                            flat_op[f"metadata_{k}"] = v
                flat_ops.append(flat_op)
            
            pd.DataFrame(flat_ops).to_csv(output_file, index=False)
        elif format_type == "html":
            # Create a simple HTML report
            import matplotlib.pyplot as plt
            import base64
            from io import BytesIO
            
            # Create plots
            plots = []
            
            # Plot 1: Operation durations by type
            if operation_types:
                plt.figure(figsize=(10, 6))
                
                op_types = list(operation_types.keys())
                durations = [type_stats[op_type]["avg_duration"] for op_type in op_types]
                counts = [type_stats[op_type]["count"] for op_type in op_types]
                
                # Create bars with count-based color intensity
                bars = plt.bar(op_types, durations)
                
                # Color bars based on count
                max_count = max(counts)
                for i, (bar, count) in enumerate(zip(bars, counts)):
                    intensity = 0.2 + 0.8 * (count / max_count) if max_count > 0 else 0.5
                    bar.set_color((0, 0, 1, intensity))
                
                plt.ylabel('Average Duration (seconds)')
                plt.title('Average Duration by Operation Type')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # Save plot to BytesIO
                buf = BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                img1 = base64.b64encode(buf.getvalue()).decode('utf-8')
                plots.append(f'<img src="data:image/png;base64,{img1}">')
                plt.close()
            
            # Plot 2: Operation counts by type
            if operation_types:
                plt.figure(figsize=(10, 6))
                
                op_types = list(operation_types.keys())
                counts = [len(operation_types[op_type]) for op_type in op_types]
                
                plt.bar(op_types, counts, color='green', alpha=0.7)
                plt.ylabel('Count')
                plt.title('Operation Counts by Type')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # Save plot to BytesIO
                buf = BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                img2 = base64.b64encode(buf.getvalue()).decode('utf-8')
                plots.append(f'<img src="data:image/png;base64,{img2}">')
                plt.close()
            
            # Create HTML report
            html = f"""
            <html>
            <head>
                <title>Performance Report {self.session_metrics["session_id"]}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1 {{ color: #333366; }}
                    h2 {{ color: #333366; margin-top: 20px; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ text-align: left; padding: 8px; border: 1px solid #ddd; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    .plot-container {{ margin: 20px 0; text-align: center; }}
                </style>
            </head>
            <body>
                <h1>Performance Report</h1>
                <p><strong>Session ID:</strong> {self.session_metrics["session_id"]}</p>
                <p><strong>Start Time:</strong> {self.session_metrics["start_time"]}</p>
                <p><strong>End Time:</strong> {self.session_metrics["end_time"]}</p>
                
                <h2>Summary</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Duration (seconds)</td><td>{self.session_metrics["summary"]["total_duration_seconds"]:.2f}</td></tr>
                    <tr><td>Operation Count</td><td>{self.session_metrics["summary"]["operation_count"]}</td></tr>
                    <tr><td>Operation Types</td><td>{", ".join(self.session_metrics["summary"]["operation_types"])}</td></tr>
                </table>
                
                <h2>Operation Type Statistics</h2>
                <table>
                    <tr>
                        <th>Type</th>
                        <th>Count</th>
                        <th>Total Duration (s)</th>
                        <th>Avg Duration (s)</th>
                        <th>Min Duration (s)</th>
                        <th>Max Duration (s)</th>
                    </tr>
            """
            
            for op_type, stats in type_stats.items():
                html += f"""
                    <tr>
                        <td>{op_type}</td>
                        <td>{stats["count"]}</td>
                        <td>{stats["total_duration"]:.2f}</td>
                        <td>{stats["avg_duration"]:.2f}</td>
                        <td>{stats["min_duration"]:.2f}</td>
                        <td>{stats["max_duration"]:.2f}</td>
                    </tr>
                """
            
            html += """
                </table>
            """
            
            if plots:
                html += """
                <h2>Visualizations</h2>
                <div class="plot-container">
                """
                for plot in plots:
                    html += plot
                
                html += """
                </div>
                """
            
            html += """
            </body>
            </html>
            """
            
            with open(output_file, 'w') as f:
                f.write(html)
        
        self.logger.info(f"Performance report generated: {output_file}")
        return output_file


def timed_operation(operation_name: str):
    """Decorator for timing function execution.
    
    Args:
        operation_name: Name of the operation for logging.
        
    Returns:
        Decorated function.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to get the performance monitor from class instance if available
            perf_monitor = None
            if args and hasattr(args[0], '_performance_monitor'):
                perf_monitor = args[0]._performance_monitor
            
            # Use default if not available in instance
            if perf_monitor is None:
                log_dir = os.environ.get('BACKTEST_LOG_DIR', './performance_logs')
                perf_monitor = PerformanceMonitor(log_dir=log_dir)
                
            # Extract metadata
            metadata = kwargs.pop('_performance_metadata', {})
            if not metadata:
                # Try to extract basic metadata from args/kwargs
                if kwargs:
                    for k, v in kwargs.items():
                        if isinstance(v, (str, int, float, bool)):
                            metadata[k] = v
            
            # Start timer
            timer_id = perf_monitor.start_timer(operation_name, metadata)
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Add result metadata if it's a simple type
                additional_metrics = {}
                if isinstance(result, (list, dict)):
                    additional_metrics['result_size'] = len(result)
                elif isinstance(result, pd.DataFrame):
                    additional_metrics['result_rows'] = len(result)
                    additional_metrics['result_columns'] = len(result.columns)
                    additional_metrics['result_memory_usage'] = result.memory_usage(deep=True).sum()
                
                # Stop timer
                perf_monitor.stop_timer(timer_id, additional_metrics)
                
                return result
            except Exception as e:
                # Stop timer with error status
                perf_monitor.stop_timer(timer_id, {'error': str(e)})
                raise
                
        return wrapper
    return decorator


# Global performance monitor for CLI and scripts
default_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Get the global default performance monitor.
    
    Returns:
        Global performance monitor instance.
    """
    return default_monitor