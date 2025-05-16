"""
Report Generator - Creates test reports in various formats.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from jinja2 import Environment, FileSystemLoader
from orchestrator.test_orchestrator import TestResult

try:
    import junit_xml
    from junit_xml import TestSuite, TestCase
    junit_available = True
except ImportError:
    junit_available = False

try:
    import matplotlib.pyplot as plt
    matplotlib_available = True
except ImportError:
    matplotlib_available = False


class ReportGenerator:
    """
    Generates test reports in various formats.
    """
    
    def __init__(self, output_dir: str):
        """
        Initialize the report generator.
        
        Args:
            output_dir: Directory to store reports
        """
        self.output_dir = Path(output_dir)
        self.logger = logging.getLogger("report_generator")
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up Jinja2 environment for HTML reports
        template_dir = Path(__file__).parent / "templates"
        if template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(template_dir),
                autoescape=True
            )
        else:
            self.logger.warning(f"Template directory not found: {template_dir}")
            self.jinja_env = None
    
    def generate_junit_report(self, result: TestResult) -> str:
        """
        Generate a JUnit XML report.
        
        Args:
            result: Test result object
            
        Returns:
            Path to the generated report file
            
        Raises:
            ImportError: If junit_xml module is not available
        """
        if not junit_available:
            self.logger.error("junit_xml module not available")
            raise ImportError("junit_xml module is required for JUnit reports")
        
        # Create a test case
        test_case = TestCase(
            name=result.test_id,
            classname="cross_dc_failover",
            elapsed_sec=result.end_time - result.start_time
        )
        
        # Add issues as failures
        if not result.success and result.issues:
            test_case.add_failure_info(
                message="Test failed",
                output="\n".join(result.issues)
            )
        
        # Create a test suite
        test_suite = TestSuite(
            name="Teracloud Streams Cross-DC Failover Tests",
            test_cases=[test_case],
            timestamp=datetime.fromtimestamp(result.start_time).isoformat()
        )
        
        # Generate the XML report
        xml_report = junit_xml.to_xml_report_string([test_suite])
        
        # Save the report to a file
        report_path = self.output_dir / f"{result.test_id}_junit.xml"
        with open(report_path, "w") as f:
            f.write(xml_report)
        
        self.logger.info(f"JUnit report saved to {report_path}")
        return str(report_path)
    
    def generate_html_report(self, result: TestResult) -> str:
        """
        Generate an HTML report.
        
        Args:
            result: Test result object
            
        Returns:
            Path to the generated report file
        """
        if not self.jinja_env:
            # Create a simple HTML report without Jinja2
            report_path = self.output_dir / f"{result.test_id}_report.html"
            self._generate_simple_html_report(result, report_path)
            return str(report_path)
        
        # Generate metrics charts if available
        charts = {}
        if matplotlib_available and result.metrics:
            charts = self._generate_metrics_charts(result)
        
        # Prepare template data
        template_data = {
            "test_id": result.test_id,
            "success": result.success,
            "start_time": datetime.fromtimestamp(result.start_time).strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": datetime.fromtimestamp(result.end_time).strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": round(result.end_time - result.start_time, 2),
            "phases_completed": [phase.name for phase in result.phases_completed],
            "rto_seconds": result.rto_seconds,
            "rpo_events": result.rpo_events,
            "metrics": result.metrics,
            "issues": result.issues,
            "data_validation": result.data_validation_result,
            "charts": charts
        }
        
        # Render the template
        template = self.jinja_env.get_template("report.html")
        html_content = template.render(**template_data)
        
        # Save the report to a file
        report_path = self.output_dir / f"{result.test_id}_report.html"
        with open(report_path, "w") as f:
            f.write(html_content)
        
        self.logger.info(f"HTML report saved to {report_path}")
        return str(report_path)
    
    def _generate_simple_html_report(self, result: TestResult, report_path: Path) -> None:
        """
        Generate a simple HTML report without Jinja2.
        
        Args:
            result: Test result object
            report_path: Path to save the report
        """
        # Convert metrics to HTML
        metrics_html = "<table border='1'><tr><th>Metric</th><th>Value</th></tr>"
        for name, value in result.metrics.items():
            metrics_html += f"<tr><td>{name}</td><td>{value}</td></tr>"
        metrics_html += "</table>"
        
        # Convert issues to HTML
        issues_html = "<ul>"
        for issue in result.issues:
            issues_html += f"<li>{issue}</li>"
        issues_html += "</ul>"
        
        # Create simple HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Failover Test Report: {result.test_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .success {{ color: green; }}
                .failure {{ color: red; }}
                table {{ border-collapse: collapse; margin: 10px 0; }}
                th, td {{ padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Failover Test Report: {result.test_id}</h1>
            
            <h2>Overall Result: <span class="{'success' if result.success else 'failure'}">
                {result.success and 'PASSED' or 'FAILED'}
            </span></h2>
            
            <h2>Summary</h2>
            <table border='1'>
                <tr><td>Start Time</td><td>{datetime.fromtimestamp(result.start_time).strftime("%Y-%m-%d %H:%M:%S")}</td></tr>
                <tr><td>End Time</td><td>{datetime.fromtimestamp(result.end_time).strftime("%Y-%m-%d %H:%M:%S")}</td></tr>
                <tr><td>Duration</td><td>{round(result.end_time - result.start_time, 2)} seconds</td></tr>
                <tr><td>RTO (Recovery Time)</td><td>{result.rto_seconds or 'N/A'} seconds</td></tr>
                <tr><td>RPO (Data Loss)</td><td>{result.rpo_events or 'N/A'} events</td></tr>
                <tr><td>Phases Completed</td><td>{', '.join([phase.name for phase in result.phases_completed])}</td></tr>
            </table>
            
            <h2>Metrics</h2>
            {metrics_html}
            
            <h2>Issues</h2>
            {issues_html if result.issues else "<p>No issues reported.</p>"}
            
        </body>
        </html>
        """
        
        # Save the report to a file
        with open(report_path, "w") as f:
            f.write(html_content)
    
    def _generate_metrics_charts(self, result: TestResult) -> Dict[str, str]:
        """
        Generate charts for metrics.
        
        Args:
            result: Test result object
            
        Returns:
            Dictionary mapping chart names to image file paths
        """
        if not matplotlib_available:
            return {}
        
        charts = {}
        
        # Create a directory for charts
        charts_dir = self.output_dir / "charts"
        charts_dir.mkdir(exist_ok=True)
        
        # Check if we have time series metrics
        time_series = result.metrics.get("time_series", {})
        if time_series:
            # Generate throughput chart if available
            if "throughput" in time_series:
                throughput_file = self._generate_time_series_chart(
                    time_series["throughput"],
                    "Throughput Over Time",
                    "Time",
                    "Events/sec",
                    charts_dir / f"{result.test_id}_throughput.png"
                )
                if throughput_file:
                    charts["throughput"] = throughput_file
            
            # Generate latency chart if available
            if "latency" in time_series:
                latency_file = self._generate_time_series_chart(
                    time_series["latency"],
                    "Latency Over Time",
                    "Time",
                    "Latency (ms)",
                    charts_dir / f"{result.test_id}_latency.png"
                )
                if latency_file:
                    charts["latency"] = latency_file
        
        return charts
    
    def _generate_time_series_chart(
        self,
        data: Dict[str, float],
        title: str,
        xlabel: str,
        ylabel: str,
        output_path: Path
    ) -> Optional[str]:
        """
        Generate a time series chart.
        
        Args:
            data: Time series data (timestamp -> value)
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            output_path: Path to save the chart
            
        Returns:
            Path to the generated chart file, or None if generation failed
        """
        try:
            # Sort data by timestamp
            timestamps = sorted(float(ts) for ts in data.keys())
            values = [data[str(ts)] for ts in timestamps]
            
            # Convert timestamps to relative time
            start_time = timestamps[0] if timestamps else 0
            rel_times = [(ts - start_time) for ts in timestamps]
            
            # Create the plot
            plt.figure(figsize=(10, 6))
            plt.plot(rel_times, values)
            plt.title(title)
            plt.xlabel(xlabel)
            plt.ylabel(ylabel)
            plt.grid(True)
            
            # Add a vertical line for failover time if available
            if "failover_time" in data:
                failover_time = float(data["failover_time"]) - start_time
                plt.axvline(x=failover_time, color='r', linestyle='--', label='Failover')
                plt.legend()
            
            # Save the plot
            plt.savefig(output_path)
            plt.close()
            
            return str(output_path)
        except Exception as e:
            self.logger.error(f"Failed to generate chart: {str(e)}")
            return None
    
    def generate_json_report(self, result: TestResult) -> str:
        """
        Generate a JSON report.
        
        Args:
            result: Test result object
            
        Returns:
            Path to the generated report file
        """
        # Convert result to serializable dictionary
        report_data = {
            "test_id": result.test_id,
            "success": result.success,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "duration_seconds": result.end_time - result.start_time,
            "phases_completed": [phase.name for phase in result.phases_completed],
            "rto_seconds": result.rto_seconds,
            "rpo_events": result.rpo_events,
            "metrics": result.metrics,
            "issues": result.issues,
            "data_validation_result": result.data_validation_result
        }
        
        # Save the report to a file
        report_path = self.output_dir / f"{result.test_id}_report.json"
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)
        
        self.logger.info(f"JSON report saved to {report_path}")
        return str(report_path)