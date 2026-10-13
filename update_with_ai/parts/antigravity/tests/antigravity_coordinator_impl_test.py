# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_coordinator_impl unit tests
# CODE_HASH: 17552a3bd531
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Unit tests for antigravity_coordinator_impl."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.antigravity.lib import (
    antigravity_coordinator,
    antigravity_coordinator_impl,
)
from update_with_ai.parts.subagent.lib import subagent_coordinator


class AntigravityCoordinatorImplTest(unittest.TestCase):
    """Test cases for AntigravityCoordinatorGenerator."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        antigravity_coordinator_impl.__initialize__(self.registry)

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
            self.assertEqual(skill_doc.name, "cleanroom_coordinator")
            self.assertIn("name: cleanroom_coordinator", skill_doc.frontmatter)
            self.assertIn("NO CODE CUSTODY", skill_doc.content)
            self.assertIn("STRICT BOUNDARY INVARIANT", skill_doc.content)
            self.assertIn("Workspace: inherit", skill_doc.content)
            self.assertIn("PROHIBITED", skill_doc.content)

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

            self.assertEqual(spec.type_name, "cleanroom_worker")
            self.assertEqual(spec.role, "test")
            self.assertEqual(spec.workspace, "/tmp/test_workspace")
            self.assertEqual(spec.model, "flash")
            self.assertIn("bin/get_work", spec.prompt)
            self.assertIn("bin/check_files", spec.prompt)
            self.assertIn("bin/submit", spec.prompt)
            self.assertIn("bin/blame", spec.prompt)
            self.assertIn("bin/fail", spec.prompt)
            self.assertIn("Nodes ready:", spec.prompt)

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
