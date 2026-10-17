# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T21:45:00Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_asm unit tests
# CODE_HASH: 445566778899
# --- END CLEANROOM METADATA ---

"""Unit tests for antigravity_asm."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.antigravity.lib import (
    antigravity_asm,
    antigravity_coordinator,
    antigravity_harness,
    antigravity_workspace,
)


class AntigravityAsmTest(unittest.TestCase):
    """Test cases for antigravity_asm assembly."""

    def test_assembly_initialization(self) -> None:
        """Verifies antigravity_asm initializes all constituent singletons into the registry."""
        registry = LifecycleRegistry()
        antigravity_asm.__initialize__(registry)

        with enter_phase(agent_session.agent_session, registry=registry) as scope:
            ws_cfg = scope.get_singleton(
                antigravity_workspace.AntigravityWorkspaceConfigurer
            )
            self.assertIsNotNone(ws_cfg)

            coord_gen = scope.get_singleton(
                antigravity_coordinator.AntigravityCoordinatorGenerator
            )
            self.assertIsNotNone(coord_gen)

            harness_mgr = scope.get_singleton(
                antigravity_harness.AntigravityHarnessManager
            )
            self.assertIsNotNone(harness_mgr)


if __name__ == "__main__":
    unittest.main()
