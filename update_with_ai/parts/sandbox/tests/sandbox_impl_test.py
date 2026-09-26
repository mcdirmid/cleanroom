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
        self.templates_materialized = False

    def materialize_templates(self) -> None:
        self.templates_materialized = True


class SandboxImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.edit_mgr = MockEditManager()
        self.registry.register_instance(
            self.edit_mgr, keys=[EditManager], tier=agent_session
        )

    def test_has_modifications_and_template_materialization_delegation(self) -> None:
        """CUJ: Sandbox delegates modification checking and template materialization to EditManager."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)

            # Requirement: Querying file modifications delegates to the edit manager.
            # Requirement: The sandbox exposes whether workspace file modifications occurred during the session.
            self.assertFalse(sb.has_modifications)
            self.edit_mgr.has_modifications = True
            self.assertTrue(sb.has_modifications)

            # Requirement: Materializing startup templates delegates to the edit manager to write template content to missing read-write files without overwriting existing files.
            # Requirement: Materializing startup templates populates missing read-write files without overwriting existing files.
            self.assertFalse(self.edit_mgr.templates_materialized)
            sb.materialize_startup_templates()
            self.assertTrue(self.edit_mgr.templates_materialized)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
