# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T21:00:00Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_asm unit tests
# CODE_HASH: 456789abcdef
# --- END CLEANROOM METADATA ---

"""Unit tests for subagent_asm."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.subagent.lib import (
    subagent_asm,
    subagent_coordinator,
    subagent_harness,
    subagent_tool,
)


class SubagentAsmTest(unittest.TestCase):
    """Test cases for subagent_asm assembly."""

    def test_assembly_initialization(self) -> None:
        """Verifies subagent_asm initializes all constituent singletons into the registry."""
        registry = LifecycleRegistry()
        subagent_asm.__initialize__(registry)

        with enter_phase(agent_session.agent_session, registry=registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            self.assertIsNotNone(coord)

            resolver = scope.get_singleton(subagent_harness.HarnessResolver)
            self.assertIsNotNone(resolver)

            tool_runner = scope.get_singleton(subagent_tool.SubagentToolRunner)
            self.assertIsNotNone(tool_runner)


if __name__ == "__main__":
    unittest.main()
