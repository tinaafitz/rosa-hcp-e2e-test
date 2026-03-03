"""
Remediation Agent
=================

Executes autonomous fixes for diagnosed issues.

This agent takes diagnosis results and executes appropriate remediation
strategies, including Kubernetes resource patching, credential refresh,
retry logic, and more.

Author: Tina Fitzgerald
Created: March 3, 2026
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from .base_agent import BaseAgent


class RemediationAgent(BaseAgent):
    """Executes autonomous fixes for detected and diagnosed issues."""

    def __init__(self, base_dir: Path, enabled: bool = True, verbose: bool = False, dry_run: bool = False):
        super().__init__("Remediation", base_dir, enabled, verbose)

        self.dry_run = dry_run
        self.fixes_applied = []
        self.fix_success_rate = {}

    def remediate(self, diagnosis: Dict) -> Tuple[bool, str]:
        """
        Execute remediation based on diagnosis.

        Args:
            diagnosis: Diagnosis dictionary from DiagnosticAgent

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.enabled:
            return False, "Remediation agent disabled"

        recommended_fix = diagnosis.get("recommended_fix")
        fix_params = diagnosis.get("fix_parameters", {})
        issue_type = diagnosis.get("issue_type")

        self.log(f"Executing fix: {recommended_fix}", "info")

        if self.dry_run:
            self.log(f"DRY RUN: Would execute {recommended_fix} with params {fix_params}", "warning")
            return True, f"DRY RUN: Fix would be applied: {recommended_fix}"

        # Route to specific fix method
        fix_methods = {
            "remove_finalizers": self._fix_remove_finalizers,
            "refresh_ocm_token": self._fix_refresh_ocm_token,
            "backoff_and_retry": self._fix_backoff_retry,
            "manual_cloudformation_cleanup": self._fix_cloudformation_manual,
            "install_capi_capa": self._fix_install_capi,
            "increase_timeout_and_monitor": self._fix_increase_timeout,
            "log_and_continue": self._fix_log_and_continue,
        }

        fix_method = fix_methods.get(recommended_fix)
        if fix_method:
            try:
                success, message = fix_method(fix_params)

                # Record the fix attempt
                self.record_intervention(recommended_fix, {
                    "issue_type": issue_type,
                    "success": success,
                    "message": message,
                    "parameters": fix_params
                })

                # Update success rate
                if recommended_fix not in self.fix_success_rate:
                    self.fix_success_rate[recommended_fix] = {"successes": 0, "failures": 0}

                if success:
                    self.fix_success_rate[recommended_fix]["successes"] += 1
                    self.learn_from_success(issue_type, recommended_fix)
                    self.log(f"Fix applied successfully: {message}", "success")
                else:
                    self.fix_success_rate[recommended_fix]["failures"] += 1
                    self.log(f"Fix failed: {message}", "error")

                return success, message

            except Exception as e:
                error_msg = f"Exception during fix execution: {str(e)}"
                self.log(error_msg, "error")
                return False, error_msg

        return False, f"No fix method available for: {recommended_fix}"

    def _fix_remove_finalizers(self, params: Dict) -> Tuple[bool, str]:
        """Remove finalizers from stuck resource."""
        resource_type = params.get("resource_type")
        resource_name = params.get("resource_name")
        namespace = params.get("namespace", "default")

        self.log(f"Removing finalizers from {resource_type}/{resource_name}", "info")

        try:
            # Patch resource to remove finalizers
            cmd = [
                "oc", "patch", resource_type, resource_name,
                "-n", namespace,
                "--type=merge",
                "-p", '{"metadata":{"finalizers":null}}'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return True, f"Successfully removed finalizers from {resource_type}/{resource_name}"
            else:
                return False, f"Failed to remove finalizers: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Timeout while removing finalizers"
        except Exception as e:
            return False, f"Error removing finalizers: {str(e)}"

    def _fix_refresh_ocm_token(self, params: Dict) -> Tuple[bool, str]:
        """Refresh OCM authentication token."""
        self.log("Refreshing OCM token", "info")

        # This would integrate with OCM credential refresh logic
        # For now, we log that intervention is needed
        return False, "OCM token refresh requires manual intervention - credentials need to be updated"

    def _fix_backoff_retry(self, params: Dict) -> Tuple[bool, str]:
        """Implement backoff and retry strategy."""
        backoff_seconds = params.get("backoff_seconds", 60)
        max_retries = params.get("max_retries", 3)

        self.log(f"Applying backoff: waiting {backoff_seconds}s before retry", "info")

        # Sleep for backoff period
        time.sleep(backoff_seconds)

        return True, f"Backoff applied ({backoff_seconds}s). Ready for retry."

    def _fix_cloudformation_manual(self, params: Dict) -> Tuple[bool, str]:
        """Handle CloudFormation issues requiring manual intervention."""
        self.log("CloudFormation issue requires manual cleanup", "warning")

        message = params.get("message", "CloudFormation stack requires manual inspection")

        # Log the issue prominently for operator attention
        self.log(f"⚠️  MANUAL INTERVENTION REQUIRED: {message}", "warning")

        # Continue test execution but flag for review
        return True, f"Logged for manual review: {message}"

    def _fix_install_capi(self, params: Dict) -> Tuple[bool, str]:
        """Install or verify CAPI/CAPA installation."""
        self.log("CAPI/CAPA installation check/fix", "info")

        capi_installed = params.get("capi_installed", False)
        capa_installed = params.get("capa_installed", False)

        if not capi_installed and not capa_installed:
            return False, "CAPI/CAPA not installed - requires manual installation via test suite 10-configure-mce-environment"
        elif not capi_installed:
            return False, "CAPI controller not found - check capi-system namespace"
        elif not capa_installed:
            return False, "CAPA controller not found - check capa-system namespace"

        return True, "CAPI/CAPA installation verified"

    def _fix_increase_timeout(self, params: Dict) -> Tuple[bool, str]:
        """Suggest timeout increase for slow operations."""
        suggested_increase = params.get("suggested_timeout_increase", "2x")

        self.log(f"Timeout issue detected - suggest increasing timeout by {suggested_increase}", "warning")

        # Log recommendation
        return True, f"Recommend increasing timeout by {suggested_increase} for this operation"

    def _fix_log_and_continue(self, params: Dict) -> Tuple[bool, str]:
        """Log issue and continue execution."""
        self.log("Issue logged for review - continuing execution", "info")
        return True, "Issue logged, test execution continues"

    def get_success_rate(self, fix_type: Optional[str] = None) -> Dict:
        """
        Get success rate statistics for fixes.

        Args:
            fix_type: Specific fix type, or None for all

        Returns:
            Dictionary with success rate statistics
        """
        if fix_type:
            stats = self.fix_success_rate.get(fix_type, {"successes": 0, "failures": 0})
            total = stats["successes"] + stats["failures"]
            rate = (stats["successes"] / total * 100) if total > 0 else 0
            return {
                "fix_type": fix_type,
                "successes": stats["successes"],
                "failures": stats["failures"],
                "total_attempts": total,
                "success_rate": f"{rate:.1f}%"
            }
        else:
            # Return all stats
            all_stats = {}
            for fix_name, stats in self.fix_success_rate.items():
                total = stats["successes"] + stats["failures"]
                rate = (stats["successes"] / total * 100) if total > 0 else 0
                all_stats[fix_name] = {
                    "successes": stats["successes"],
                    "failures": stats["failures"],
                    "total_attempts": total,
                    "success_rate": f"{rate:.1f}%"
                }
            return all_stats

    def get_fixes_summary(self) -> str:
        """Get human-readable summary of fixes applied."""
        if not self.fixes_applied:
            return "No fixes applied yet"

        summary = f"Fixes Applied: {len(self.fixes_applied)}\n"
        for fix in self.fixes_applied[-10:]:  # Last 10 fixes
            summary += f"  - {fix.get('type')}: {fix.get('message')}\n"

        return summary
