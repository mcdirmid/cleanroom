# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T03:03:01Z
# CHANGE: Add MockEditManager collaborator and tests verifying Sandbox.has_modifications returns true/false by delegating to EditManager.has_modifications (including live, non-cached state); strengthen initialization test to check interface-key singleton identity.
# CODE_HASH: 4d36952be67d
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for sandbox_impl per its grounding specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib import sandbox, sandbox_file_editor
from update_with_ai.parts.sandbox.lib.sandbox_impl import (
    Sandbox,
    __initialize__,
)


class MockEditManager:
    """Test double for sandbox_file_editor.EditManager with scripted modification state."""

    tier = agent_session

    def __init__(self, modified: bool = False) -> None:
        self.modified = modified
        self.has_modifications_queries = 0

    @property
    def has_modifications(self) -> bool:
        self.has_modifications_queries += 1
        return self.modified


class SandboxImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_edit_manager = MockEditManager()
        self.registry.register_instance(
            self.mock_edit_manager,
            keys=[sandbox_file_editor.EditManager],
            tier=agent_session,
        )

    def test_initialization(self) -> None:
        """CUJ: Sandbox resolves as an agent_session singleton under its implementation and interface keys."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            instance = scope.get_singleton(Sandbox)
            self.assertIsInstance(instance, Sandbox)
            interface_instance = scope.get_singleton(sandbox.Sandbox)
            self.assertIs(interface_instance, instance)

    def test_has_modifications_true_when_edit_manager_reports_modifications(self) -> None:
        """Postcondition: WHEN workspace files were modified (EditManager reports true), MUST return true."""
        self.mock_edit_manager.modified = True
        with enter_phase(agent_session, registry=self.registry) as scope:
            instance = scope.get_singleton(Sandbox)
            self.assertIs(instance.has_modifications, True)
            self.assertGreaterEqual(self.mock_edit_manager.has_modifications_queries, 1)

    def test_has_modifications_false_when_edit_manager_reports_no_modifications(self) -> None:
        """Postcondition: WHEN no workspace files were modified (EditManager reports false), MUST return false."""
        self.mock_edit_manager.modified = False
        with enter_phase(agent_session, registry=self.registry) as scope:
            instance = scope.get_singleton(Sandbox)
            self.assertIs(instance.has_modifications, False)
            self.assertGreaterEqual(self.mock_edit_manager.has_modifications_queries, 1)

    def test_has_modifications_reflects_current_edit_manager_state(self) -> None:
        """Postcondition: has_modifications reflects modifications occurring during the session, not a cached value."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            instance = scope.get_singleton(Sandbox)
            self.assertIs(instance.has_modifications, False)
            self.mock_edit_manager.modified = True
            self.assertIs(instance.has_modifications, True)
            self.assertGreaterEqual(self.mock_edit_manager.has_modifications_queries, 2)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
