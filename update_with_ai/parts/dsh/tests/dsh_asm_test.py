# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:00:00Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_asm unit tests
# --- END CLEANROOM METADATA ---

"""Unit tests for dsh_asm."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.dsh.lib import (
    dsh_asm,
    dsh_harness,
    dsh_workspace,
)


class DshAsmTest(unittest.TestCase):
    """Test cases for dsh_asm assembly."""

    def test_assembly_initialization(self) -> None:
        """Verifies dsh_asm initializes all constituent singletons into the registry."""
        registry = LifecycleRegistry()
        dsh_asm.__initialize__(registry)

        with enter_phase(agent_session.agent_session, registry=registry) as scope:
            workspace_cfg = scope.get_singleton(dsh_workspace.DshWorkspaceConfigurer)
            self.assertIsNotNone(workspace_cfg)

            harness_mgr = scope.get_singleton(dsh_harness.DshHarnessManager)
            self.assertIsNotNone(harness_mgr)


if __name__ == "__main__":
    unittest.main()
