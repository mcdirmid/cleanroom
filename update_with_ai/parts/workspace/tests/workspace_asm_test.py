# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-08T12:55:00Z
# LAST_CHANGED: 2026-10-06T16:03:00Z
# CHANGE: test assembly initialization
# CODE_HASH: d40af934a2e3
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_asm."""

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from update_with_ai.parts.workspace.lib import (
    workspace_asm,
    workspace_provision,
    workspace_registry,
    workspace_sync,
    workspace_work,
)


class WorkspaceAsmTest(unittest.TestCase):
    def test_assembly_initialization(self) -> None:
        registry = LifecycleRegistry()
        workspace_asm.__initialize__(registry)

        with enter_phase("agent_session", registry=registry):
            reg = get_singleton(workspace_registry.WorkspaceRegistry)
            self.assertIsNotNone(reg)

            prov = get_singleton(workspace_provision.WorkspaceProvisioner)
            self.assertIsNotNone(prov)

            sync = get_singleton(workspace_sync.WorkspaceSynchronizer)
            self.assertIsNotNone(sync)

            work = get_singleton(workspace_work.WorkspaceWorkManager)
            self.assertIsNotNone(work)


if __name__ == "__main__":
    unittest.main()
