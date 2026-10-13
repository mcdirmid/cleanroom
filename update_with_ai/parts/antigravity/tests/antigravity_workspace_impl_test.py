# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_workspace_impl unit tests
# CODE_HASH: 39a41247ec78
# COVERAGE_AUDIT: 2026-10-12T23:37:36Z
# QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Unit tests for antigravity_workspace_impl."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.antigravity.lib import (
    antigravity_workspace,
    antigravity_workspace_impl,
)


class AntigravityWorkspaceImplTest(unittest.TestCase):
    """Test cases for AntigravityWorkspaceConfigurer."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        antigravity_workspace_impl.__initialize__(self.registry)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_configure_workspace_creates_isolation_rules(self) -> None:
        """Scenario 1: Verifies that configure_workspace writes .agents/rules/isolation.md."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(
                antigravity_workspace.AntigravityWorkspaceConfigurer
            )
            self.assertIsNotNone(configurer)
            self.assertIsInstance(
                configurer, antigravity_workspace_impl.AntigravityWorkspaceConfigurer
            )

            report = configurer.configure_workspace(
                workspace_dir=self.test_dir,
                role_name="lib",
                dir_scope="pkg_a",
            )

            self.assertTrue(report.is_confined)
            self.assertEqual(report.role_name, "lib")
            self.assertIn(".agents/rules/isolation.md", report.rule_paths)

            rule_file = os.path.join(self.test_dir, ".agents", "rules", "isolation.md")
            self.assertTrue(os.path.isfile(rule_file))

            with open(rule_file, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("NEVER Navigate Outside This Workspace", content)
            self.assertIn("bin/get_work", content)
            self.assertIn("bin/submit", content)
            self.assertIn("bin/blame", content)
            self.assertIn("bin/fail", content)


if __name__ == "__main__":
    unittest.main()
