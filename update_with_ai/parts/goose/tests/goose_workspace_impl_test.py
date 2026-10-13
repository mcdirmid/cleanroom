# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T11:20:00Z
# CHANGE: align with HLS role agent documentation customization
# CODE_HASH: 4a7e6dad173d
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Unit tests for goose_workspace_impl."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.goose.lib import goose_workspace
from update_with_ai.parts.goose.lib.goose_workspace_impl import (
    GooseWorkspaceConfigurer,
    __initialize__,
)


class GooseWorkspaceImplTest(unittest.TestCase):
    """Test cases for GooseWorkspaceConfigurer."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_configure_role_workspace(self) -> None:
        """Requirement: MUST write boundary instructions into AGENTS.md."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(goose_workspace.GooseWorkspaceConfigurer)
            report = configurer.configure_role_workspace(
                workspace_dir=self.test_dir,
                role_name="low",
            )

            self.assertEqual(report.status, "configured")
            self.assertEqual(report.workspace_dir, self.test_dir)
            self.assertEqual(report.role_name, "low")

            agents_md_path = os.path.join(self.test_dir, "AGENTS.md")
            self.assertIn(agents_md_path, report.configured_files)

            # Validate AGENTS.md content
            self.assertTrue(os.path.isfile(agents_md_path))
            with open(agents_md_path, "r", encoding="utf-8") as f:
                agents_content = f.read()
            self.assertIn(self.test_dir, agents_content)
            self.assertIn("Assigned Role: low", agents_content)
            self.assertIn("bin/get_work", agents_content)
            self.assertIn("bin/check_files", agents_content)
            self.assertIn("bin/submit", agents_content)
            self.assertIn("bin/blame", agents_content)
            self.assertIn("bin/fail", agents_content)

    def test_configure_role_workspace_with_existing_agents_md(self) -> None:
        """Requirement: MUST preserve existing AGENTS.md content while incorporating confinement rules."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(goose_workspace.GooseWorkspaceConfigurer)
            agents_md_path = os.path.join(self.test_dir, "AGENTS.md")
            with open(agents_md_path, "w", encoding="utf-8") as f:
                f.write("# Role Specific Rules\nSpecial role guidelines here.\n")

            configurer.configure_role_workspace(
                workspace_dir=self.test_dir,
                role_name="qa",
            )
            with open(agents_md_path, "r", encoding="utf-8") as f:
                agents_content = f.read()
            self.assertIn("Assigned Role: qa", agents_content)
            self.assertIn("Special role guidelines here.", agents_content)
            self.assertIn("bin/get_work", agents_content)


if __name__ == "__main__":
    unittest.main()
