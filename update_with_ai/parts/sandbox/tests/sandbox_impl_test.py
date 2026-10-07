# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 0e2ad35b3eca
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Unit tests for sandbox_impl aligned with grounding specifications."""

import unittest

from unittest.mock import MagicMock
from typing import Any

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_node_config import NodeConfig
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.dag.lib import dag_storage
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


class MockDagStorage:
    tier = "system"

    def __init__(self) -> None:
        self.materialized_nodes: list[Any] = []

    def materialize_template(self, node: Any) -> None:
        self.materialized_nodes.append(node)


class SandboxImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.edit_mgr = MockEditManager()
        self.registry.register_instance(
            self.edit_mgr, keys=[EditManager], tier=agent_session
        )
        self.storage = MockDagStorage()
        self.registry.register_instance(
            self.storage, keys=[dag_storage.DagStorage], tier="system"
        )

    def test_has_modifications_and_template_materialization_delegation(self) -> None:
        """CUJ: Sandbox delegates modification checking to EditManager and template materialization to DagStorage."""
        node = MagicMock()
        rw_file = MagicMock()
        rw_file.owning_node = node
        node_cfg = MagicMock()
        node_cfg.read_write_files = [rw_file]
        self.registry.register_instance(node_cfg, keys=[NodeConfig], tier=agent_session)

        with enter_phase(agent_session, registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)

            # Requirement: Querying file modifications delegates to the edit manager.
            # Requirement: The sandbox exposes whether workspace file modifications occurred during the session.
            self.assertFalse(sb.has_modifications)
            self.edit_mgr.has_modifications = True
            self.assertTrue(sb.has_modifications)

            # Requirement: Materializing startup templates delegates to dag storage.
            self.assertEqual(len(self.storage.materialized_nodes), 0)
            sb.materialize_templates()
            self.assertEqual(self.storage.materialized_nodes, [node])


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
