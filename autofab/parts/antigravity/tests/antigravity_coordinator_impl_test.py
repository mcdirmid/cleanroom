"""Unit tests for antigravity_coordinator_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from support.lib import app_info
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from autofab.parts.agent.lib import session as agent_session
from autofab.parts.antigravity.lib import (
    antigravity_coordinator,
    antigravity_coordinator_impl,
    antigravity_workspace,
)
from autofab.parts.subagent.lib import subagent_coordinator


class AntigravityCoordinatorImplTest(unittest.TestCase):
    """Test cases for AntigravityCoordinatorGenerator and AntigravityWorkspaceConfigurer."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        antigravity_coordinator_impl.__initialize__(self.registry)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_configure_workspace_creates_isolation_rules(self) -> None:
        """Scenario: Verifies that configure_workspace writes .agents/rules/isolation.md."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(
                antigravity_workspace.AntigravityWorkspaceConfigurer
            )
            self.assertIsNotNone(configurer)
            self.assertIsInstance(
                configurer,
                antigravity_coordinator_impl.AntigravityWorkspaceConfigurer,
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

            self.assertIn(".agents/hooks.json", report.rule_paths)
            hooks_file = os.path.join(self.test_dir, ".agents", "hooks.json")
            self.assertTrue(os.path.isfile(hooks_file))
            with open(hooks_file, "r", encoding="utf-8") as f:
                hooks_data = json.load(f)
            self.assertIn("checkpoint-pre-edit", hooks_data)
            self.assertIn("PreToolUse", hooks_data["checkpoint-pre-edit"])
            pre_tool = hooks_data["checkpoint-pre-edit"]["PreToolUse"][0]
            self.assertEqual(pre_tool["matcher"], "edit_file|write_file")
            self.assertEqual(pre_tool["hooks"][0]["command"], "./bin/checkpoint pre-edit")

    def test_configure_workspace_auditor_rules_and_hooks(self) -> None:
        """Auditor role workspace configures deny hooks and zero file-editing permissions."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(
                antigravity_workspace.AntigravityWorkspaceConfigurer
            )
            report = configurer.configure_workspace(
                workspace_dir=self.test_dir,
                role_name="qa",
                dir_scope="pkg_a",
            )
            rule_file = os.path.join(self.test_dir, ".agents", "rules", "isolation.md")
            with open(rule_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Zero File-Editing Permissions", content)
            self.assertIn("strictly forbidden from creating, modifying, editing", content)

            hooks_file = os.path.join(self.test_dir, ".agents", "hooks.json")
            with open(hooks_file, "r", encoding="utf-8") as f:
                hooks_data = json.load(f)
            self.assertIn("deny-edits-auditor", hooks_data)
            self.assertNotIn("checkpoint-pre-edit", hooks_data)
            pre_tool = hooks_data["deny-edits-auditor"]["PreToolUse"][0]
            self.assertEqual(pre_tool["matcher"], "edit_file|write_file")
            self.assertIn("Auditor roles have zero file-editing permissions", pre_tool["hooks"][0]["command"])

    def test_generate_coordinator_skill(self) -> None:
        """Scenario 1 & 2: Verifies skill generation and workspace pinning requirements."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            generator = scope.get_singleton(
                antigravity_coordinator.AntigravityCoordinatorGenerator
            )
            self.assertIsNotNone(generator)
            self.assertIsInstance(
                generator,
                antigravity_coordinator_impl.AntigravityCoordinatorGenerator,
            )

            skill_doc = generator.generate_coordinator_skill(dir_scope="pkg_a")
            self.assertEqual(skill_doc.name, app_info.get_coordinator_skill_name())
            self.assertIn(f"name: {app_info.get_coordinator_skill_name()}", skill_doc.frontmatter)
            self.assertIn("NO CODE CUSTODY", skill_doc.content)
            self.assertIn("STRICT BOUNDARY INVARIANT", skill_doc.content)
            self.assertIn("Workspace: inherit", skill_doc.content)
            self.assertIn("PROHIBITED", skill_doc.content)
            self.assertIn("UNRESOLVED ROUND REMINDER", skill_doc.content)

    def test_format_dispatch_directive(self) -> None:
        """Scenario 3: Verifies formatting a RoleDispatch into a SubagentDispatchSpec."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            generator = scope.get_singleton(
                antigravity_coordinator.AntigravityCoordinatorGenerator
            )
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="test",
                workspace_dir="/tmp/test_workspace",
                dir_scope="pkg_a",
                ready_targets=("tests/foo_test.py",),
            )
            spec = generator.format_dispatch_directive(dispatch, model="flash")

            self.assertEqual(spec.type_name, app_info.get_worker_type_name())
            self.assertEqual(spec.role, "test")
            self.assertEqual(spec.workspace, "/tmp/test_workspace")
            self.assertEqual(spec.model, "flash")
            self.assertIn("bin/get_work", spec.prompt)
            self.assertIn("bin/check_files", spec.prompt)
            self.assertIn("sole author and custodian", spec.prompt)
            self.assertIn("Avoid sequential micro-reads", spec.prompt)
            self.assertIn("Never scan outside your workspace root", spec.prompt)
            self.assertIn("bin/submit", spec.prompt)
            self.assertIn("bin/blame", spec.prompt)
            self.assertIn("bin/fail", spec.prompt)
            self.assertIn("Nodes ready:", spec.prompt)

            dispatch_with_reminder = subagent_coordinator.RoleDispatch(
                role_name="test",
                workspace_dir="/tmp/test_workspace",
                dir_scope="pkg_a",
                ready_targets=("tests/foo_test.py",),
                task_prompt="CRITICAL REMINDER: Unresolved targets must be concluded.",
            )
            spec_reminder = generator.format_dispatch_directive(dispatch_with_reminder, model="flash")
            self.assertIn("CRITICAL REMINDER: Unresolved targets must be concluded.", spec_reminder.prompt)
            self.assertIn(f"Execute autonomous {app_info.APP_TITLE} round", spec_reminder.prompt)

    def test_parse_wake_notification_json(self) -> None:
        """Scenario 4: Verifies parsing structured JSON wake notification message."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            generator = scope.get_singleton(
                antigravity_coordinator.AntigravityCoordinatorGenerator
            )
            json_text = """```json
{
  "action": "complete",
  "role": "lib",
  "submitted": ["lib/foo.py", "lib/bar.py"],
  "blamed": []
}
```"""
            msg = generator.parse_wake_notification(json_text)
            self.assertEqual(msg.action, "complete")
            self.assertEqual(msg.role, "lib")
            self.assertEqual(msg.submitted_targets, ["lib/foo.py", "lib/bar.py"])
            self.assertEqual(msg.blamed_targets, [])

    def test_parse_wake_notification_plain_text(self) -> None:
        """Scenario 4b: Verifies fallback parsing for text-based subagent completion."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            generator = scope.get_singleton(
                antigravity_coordinator.AntigravityCoordinatorGenerator
            )
            text = "Role: lib\nSubmitted: lib/foo.py\nStatus: complete"
            msg = generator.parse_wake_notification(text)
            self.assertEqual(msg.action, "complete")
            self.assertEqual(msg.role, "lib")
            self.assertIn("lib/foo.py", msg.submitted_targets)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-30T05:30:00Z
# CHANGE: Test role dispatch prompt grounding for file custodianship, targeted chunk reads, and workspace confinement
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
