# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-08T00:44:00Z
# LAST_CHANGED: 2026-10-08T00:44:00Z
# CHANGE: Remove template materialization tests from sandbox_impl_test
# CODE_HASH: 3f76cfaa318f
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Unit tests for sandbox_impl aligned with grounding specifications."""

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib.sandbox import Sandbox
from update_with_ai.parts.sandbox.lib.sandbox_file_editor import EditManager
from update_with_ai.parts.sandbox.lib.sandbox_impl import (
    Sandbox as SandboxImpl,
    __initialize__,
)


class MockEditManager:
    tier = agent_session

    def __init__(self) -> None:
        self.has_modifications = False


class SandboxImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.edit_mgr = MockEditManager()
        self.registry.register_instance(
            self.edit_mgr, keys=[EditManager], tier=agent_session
        )

    def test_has_modifications_delegation(self) -> None:
        """CUJ: Sandbox delegates modification checking to EditManager."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)

            # Requirement: Querying file modifications delegates to the edit manager.
            # Requirement: The sandbox exposes whether workspace file modifications occurred during the session.
            self.assertFalse(sb.has_modifications)
            self.edit_mgr.has_modifications = True
            self.assertTrue(sb.has_modifications)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
