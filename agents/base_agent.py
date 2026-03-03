"""
Base AI Agent Class
===================

Foundation for all AI agents in the self-healing test framework.

Provides:
    - Logging and event tracking
    - Pattern matching infrastructure
    - Intervention history
    - Learning capabilities

Author: Tina Fitzgerald
Created: March 3, 2026
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BaseAgent:
    """Base class for all AI agents with core functionality."""

    def __init__(self, name: str, base_dir: Path, enabled: bool = True, verbose: bool = False):
        """
        Initialize base agent.

        Args:
            name: Agent identifier
            base_dir: Base directory for the test framework
            enabled: Whether agent is active
            verbose: Enable detailed logging
        """
        self.name = name
        self.base_dir = base_dir
        self.enabled = enabled
        self.verbose = verbose

        # Setup logging
        self.logger = logging.getLogger(f"agent.{name}")
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)

        # Agent state
        self.interventions = []
        self.patterns_detected = []
        self.current_context = {}

        # Knowledge base paths
        self.kb_dir = base_dir / "agents" / "knowledge_base"
        self.kb_dir.mkdir(parents=True, exist_ok=True)

        # Load knowledge base
        self.known_issues = self._load_knowledge("known_issues.json")
        self.fix_strategies = self._load_knowledge("fix_strategies.json")

        self.log(f"🤖 {name} agent initialized (enabled={enabled})")

    def log(self, message: str, level: str = "info"):
        """Log a message with the agent's context."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}] [{self.name}]"

        if level == "debug" and self.verbose:
            self.logger.debug(f"{prefix} {message}")
            print(f"\033[90m{prefix} {message}\033[0m")  # Gray
        elif level == "info":
            self.logger.info(f"{prefix} {message}")
            if self.verbose:
                print(f"\033[96m{prefix} {message}\033[0m")  # Cyan
        elif level == "warning":
            self.logger.warning(f"{prefix} {message}")
            print(f"\033[93m{prefix} ⚠️  {message}\033[0m")  # Yellow
        elif level == "error":
            self.logger.error(f"{prefix} {message}")
            print(f"\033[91m{prefix} ❌ {message}\033[0m")  # Red
        elif level == "success":
            self.logger.info(f"{prefix} {message}")
            print(f"\033[92m{prefix} ✓ {message}\033[0m")  # Green

    def _load_knowledge(self, filename: str) -> Dict:
        """Load knowledge base JSON file."""
        kb_file = self.kb_dir / filename
        if kb_file.exists():
            try:
                with open(kb_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                self.log(f"Failed to load {filename}: {e}", "error")
                return {}
        return {}

    def _save_knowledge(self, filename: str, data: Dict):
        """Save knowledge base JSON file."""
        kb_file = self.kb_dir / filename
        try:
            with open(kb_file, 'w') as f:
                json.dump(data, f, indent=2)
            self.log(f"Saved knowledge to {filename}", "debug")
        except Exception as e:
            self.log(f"Failed to save {filename}: {e}", "error")

    def match_pattern(self, text: str, patterns: List[Dict]) -> Optional[Dict]:
        """
        Match text against known patterns.

        Args:
            text: Text to match
            patterns: List of pattern dictionaries with 'pattern', 'type', 'severity'

        Returns:
            Matched pattern dict or None
        """
        for pattern_def in patterns:
            pattern = pattern_def.get("pattern", "")
            if re.search(pattern, text, re.IGNORECASE):
                self.log(f"Pattern matched: {pattern_def.get('type', 'unknown')}", "debug")
                return pattern_def
        return None

    def record_intervention(self, intervention_type: str, details: Dict):
        """
        Record an intervention for learning and auditing.

        Args:
            intervention_type: Type of intervention performed
            details: Details about the intervention
        """
        intervention = {
            "timestamp": datetime.now().isoformat(),
            "type": intervention_type,
            "agent": self.name,
            "details": details,
        }
        self.interventions.append(intervention)

        # Save to persistent log
        log_file = self.kb_dir / "intervention_log.json"
        interventions_log = []
        if log_file.exists():
            with open(log_file, 'r') as f:
                interventions_log = json.load(f)

        interventions_log.append(intervention)

        with open(log_file, 'w') as f:
            json.dump(interventions_log, f, indent=2)

        self.log(f"Recorded intervention: {intervention_type}", "debug")

    def update_context(self, key: str, value: any):
        """Update the current execution context."""
        self.current_context[key] = value
        self.log(f"Context updated: {key} = {value}", "debug")

    def get_context(self, key: str, default=None):
        """Get value from current execution context."""
        return self.current_context.get(key, default)

    def should_intervene(self, pattern: Dict) -> bool:
        """
        Determine if agent should intervene based on pattern and policy.

        Args:
            pattern: Matched pattern dictionary

        Returns:
            True if intervention is warranted
        """
        if not self.enabled:
            return False

        severity = pattern.get("severity", "medium")
        auto_fix = pattern.get("auto_fix", False)

        # High severity issues always trigger intervention if auto_fix is enabled
        if severity == "high" and auto_fix:
            return True

        # Medium severity with auto_fix enabled
        if severity == "medium" and auto_fix:
            return True

        # Low severity only if explicitly enabled
        if severity == "low" and auto_fix:
            return True

        return False

    def get_fix_strategy(self, issue_type: str) -> Optional[Dict]:
        """
        Get fix strategy for a specific issue type.

        Args:
            issue_type: Type of issue

        Returns:
            Fix strategy dictionary or None
        """
        return self.fix_strategies.get(issue_type)

    def learn_from_success(self, issue_type: str, fix_applied: str):
        """
        Learn from a successful fix to improve future interventions.

        Args:
            issue_type: Type of issue that was fixed
            fix_applied: Description of the fix that worked
        """
        learning_file = self.kb_dir / "learning_log.json"
        learning_log = []

        if learning_file.exists():
            with open(learning_file, 'r') as f:
                learning_log = json.load(f)

        learning_entry = {
            "timestamp": datetime.now().isoformat(),
            "issue_type": issue_type,
            "fix_applied": fix_applied,
            "agent": self.name,
            "success": True
        }

        learning_log.append(learning_entry)

        with open(learning_file, 'w') as f:
            json.dump(learning_log, f, indent=2)

        self.log(f"Learned from success: {issue_type}", "success")
