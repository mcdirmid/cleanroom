# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T09:50:00Z
# LAST_CHANGED: 2026-10-13T09:50:00Z
# CHANGE: author goose_asm unit tests
# CODE_HASH: 000000000000
# --- END CLEANROOM METADATA ---

"""Unit tests for goose_asm."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.goose.lib import (
    goose_asm,
    goose_harness,
    goose_workspace,
)


class GooseAsmTest(unittest.TestCase):
    """Test cases for goose_asm assembly."""

    def test_assembly_initialization(self) -> None:
        """Verifies goose_asm initializes all constituent singletons into the registry."""
        registry = LifecycleRegistry()
        goose_asm.__initialize__(registry)

        with enter_phase(agent_session.agent_session, registry=registry) as scope:
            workspace_cfg = scope.get_singleton(goose_workspace.GooseWorkspaceConfigurer)
            self.assertIsNotNone(workspace_cfg)

            harness_mgr = scope.get_singleton(goose_harness.GooseHarnessManager)
            self.assertIsNotNone(harness_mgr)


if __name__ == "__main__":
    unittest.main()
