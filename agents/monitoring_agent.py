"""
Monitoring Agent
================

Real-time monitoring of test execution output with pattern detection.

This agent hooks into the test suite's line-by-line output streaming to
detect issues as they happen, enabling immediate intervention.

Author: Tina Fitzgerald
Created: March 3, 2026
"""

import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .base_agent import BaseAgent


class MonitoringAgent(BaseAgent):
    """Real-time monitoring agent for test execution output."""

    def __init__(self, base_dir: Path, enabled: bool = True, verbose: bool = False):
        super().__init__("Monitor", base_dir, enabled, verbose)

        # Callback for when issues are detected
        self.issue_callback: Optional[Callable] = None

        # Buffer for multi-line pattern matching
        self.line_buffer: List[str] = []
        self.buffer_size = 50  # Keep last 50 lines for context

        # State tracking
        self.current_task = None
        self.waiting_for_resource = None
        self.timeout_warnings = 0

        # Debounce: track last issue type and time to avoid spamming
        self._last_issue_type = None
        self._last_issue_time = 0
        self._issue_debounce_seconds = 30  # Minimum seconds between same issue type

    def set_issue_callback(self, callback: Callable):
        """
        Set callback function to be called when issues are detected.

        Args:
            callback: Function(issue_type: str, context: Dict) -> None
        """
        self.issue_callback = callback
        self.log("Issue callback registered", "debug")

    def process_line(self, line: str) -> bool:
        """
        Process a single line of output from test execution.

        Args:
            line: Output line from Ansible/test execution

        Returns:
            True if line triggered an intervention
        """
        if not self.enabled:
            return False

        # Add to buffer for context
        self.line_buffer.append(line)
        if len(self.line_buffer) > self.buffer_size:
            self.line_buffer.pop(0)

        # Track current execution context
        self._update_execution_context(line)

        # Check for known issue patterns
        issue = self._detect_issue(line)
        if issue:
            self.log(f"Issue detected: {issue['type']}", "warning")
            self.patterns_detected.append(issue)

            # Trigger intervention if callback is set (with debounce)
            if self.issue_callback and self.should_intervene(issue):
                now = time.time()
                if issue['type'] == self._last_issue_type and (now - self._last_issue_time) < self._issue_debounce_seconds:
                    # Skip — same issue type fired too recently
                    return False

                self._last_issue_type = issue['type']
                self._last_issue_time = now

                context = {
                    "line": line,
                    "buffer": self.line_buffer[-30:],  # Last 30 lines for better extraction
                    "current_task": self.current_task,
                    "waiting_for": self.waiting_for_resource,
                }
                self.issue_callback(issue['type'], context, issue)
                return True

        return False

    def _update_execution_context(self, line: str):
        """Extract execution context from output line."""
        # Track current Ansible task
        if "TASK [" in line:
            # Extract task name: TASK [task name] ******
            task_match = line.split("TASK [")[1].split("]")[0] if "TASK [" in line else None
            if task_match:
                self.current_task = task_match
                self.update_context("current_task", task_match)
                self.log(f"Current task: {task_match}", "debug")

        # Track resource waiting states
        if "Waiting for" in line or "waiting for" in line:
            # Extract resource being waited for
            if "ROSANetwork" in line:
                self.waiting_for_resource = "ROSANetwork"
            elif "ROSAControlPlane" in line:
                self.waiting_for_resource = "ROSAControlPlane"
            elif "ROSARoleConfig" in line:
                self.waiting_for_resource = "ROSARoleConfig"

            self.update_context("waiting_for", self.waiting_for_resource)

    def _detect_issue(self, line: str) -> Optional[Dict]:
        """
        Detect known issues in output line.

        Returns:
            Issue dictionary if detected, None otherwise
        """
        # Load patterns from knowledge base
        patterns = self.known_issues.get("patterns", [])

        # Match against known patterns
        matched = self.match_pattern(line, patterns)
        if matched:
            return matched

        # Dynamic pattern detection based on keywords

        # ROSANetwork stuck in deletion
        if "rosanetwork" in line.lower() and ("deleting" in line.lower() or "deletiontimestamp" in line.lower()):
            if self._check_buffer_for_timeout():
                return {
                    "type": "rosanetwork_stuck_deletion",
                    "severity": "high",
                    "auto_fix": True,
                    "pattern": "ROSANetwork stuck in deletion state",
                    "description": "ROSANetwork resource stuck with deletion timestamp, likely due to finalizers"
                }

        # CloudFormation stack deletion failures
        if "cloudformation" in line.lower() and ("delete_failed" in line.lower() or "rollback" in line.lower()):
            return {
                "type": "cloudformation_deletion_failure",
                "severity": "high",
                "auto_fix": False,
                "pattern": "CloudFormation stack deletion failure",
                "description": "AWS CloudFormation stack failed to delete properly"
            }

        # OCM authentication issues
        if "ocm" in line.lower() and ("unauthorized" in line.lower() or "authentication" in line.lower() or "403" in line):
            return {
                "type": "ocm_auth_failure",
                "severity": "medium",
                "auto_fix": True,
                "pattern": "OCM authentication failure",
                "description": "OpenShift Cluster Manager authentication failed"
            }

        # CAPI/CAPA controller not found
        if ("capi" in line.lower() or "capa" in line.lower()) and ("not found" in line.lower() or "does not exist" in line.lower()):
            return {
                "type": "capi_not_installed",
                "severity": "high",
                "auto_fix": False,
                "pattern": "CAPI/CAPA not installed or configured",
                "description": "Cluster API controllers are not running"
            }

        # Timeout warnings
        if "timeout" in line.lower() or "timed out" in line.lower():
            self.timeout_warnings += 1
            if self.timeout_warnings > 2:  # Multiple timeout warnings
                return {
                    "type": "repeated_timeouts",
                    "severity": "medium",
                    "auto_fix": False,
                    "pattern": "Multiple timeout warnings detected",
                    "description": "Operation is timing out repeatedly"
                }

        # API rate limiting
        if "rate limit" in line.lower() or "429" in line or "too many requests" in line.lower():
            return {
                "type": "api_rate_limit",
                "severity": "low",
                "auto_fix": True,
                "pattern": "API rate limiting detected",
                "description": "Hitting API rate limits, need to back off"
            }

        return None

    def _check_buffer_for_timeout(self) -> bool:
        """Check if recent buffer contains timeout or stuck indicators."""
        recent_lines = " ".join(self.line_buffer[-10:]).lower()
        return any(keyword in recent_lines for keyword in [
            "timeout", "timed out", "still exists", "failed to delete",
            "deletiontimestamp", "stuck", "waiting"
        ])

    def get_statistics(self) -> Dict:
        """Get monitoring statistics."""
        return {
            "patterns_detected": len(self.patterns_detected),
            "interventions_performed": len(self.interventions),
            "timeout_warnings": self.timeout_warnings,
            "current_task": self.current_task,
            "waiting_for": self.waiting_for_resource,
        }

    def reset(self):
        """Reset monitoring state for new test run."""
        self.line_buffer.clear()
        self.patterns_detected.clear()
        self.current_task = None
        self.waiting_for_resource = None
        self.timeout_warnings = 0
        self._last_issue_type = None
        self._last_issue_time = 0
        self.log("Monitoring state reset", "debug")
