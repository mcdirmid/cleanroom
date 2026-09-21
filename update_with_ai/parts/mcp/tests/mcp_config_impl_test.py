"""Unit tests for mcp_config_impl per its grounding specification."""

from __future__ import annotations

import os
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.dag.lib.dag_config import DagConfig
from update_with_ai.parts.mcp.lib.mcp_config_impl import McpConfig, __initialize__


class McpConfigImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_default_configuration_parameters(self) -> None:
        """CUJ: Resolve MCP configuration with standard defaults."""
        with enter_phase(system, registry=self.registry) as scope:
            cfg = scope.get_singleton(McpConfig)
            agent_cfg = scope.get_singleton(AgentConfig)
            dag_cfg = scope.get_singleton(DagConfig)

            self.assertIs(cfg, agent_cfg)
            self.assertIs(cfg, dag_cfg)

            # Requirement: [AgentConfig] The agent config provides the conversation limit bounding interaction turns.
            self.assertEqual(cfg.conversation_limit, 50)

            # Requirement: [AgentConfig] The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.
            self.assertFalse(cfg.inject_followups)

            # Requirement: [AgentConfig] The agent config provides whether the agent should use step mode to communicate a guide progressively.
            self.assertFalse(cfg.is_step_mode)

            # Requirement: [AgentConfig] The agent config provides whether the agent should perform startup reads to inspect declared files at session start.
            self.assertFalse(cfg.is_startup_reads)

            # Requirement: [AgentConfig] The agent config provides whether editing tools should produce delta output.
            self.assertFalse(cfg.edit_delta_output)

            # Requirement: [AgentConfig] The agent config provides whether the agent should operate in mcp mode.
            self.assertTrue(cfg.is_mcp_mode)

            # Requirement: [DagConfig] The dag config provides the node visit limit bounding node visits during graph cleaning.
            self.assertEqual(cfg.node_visit_limit, 500)

            # Requirement: [DagConfig] The dag config provides the batch size bounding dirty nodes processed together in an agent session.
            self.assertEqual(cfg.batch_size, 1)

    def test_environment_override_parameters(self) -> None:
        """CUJ: Resolve MCP configuration with environment variable overrides."""
        env_overrides = {
            "CONVERSATION_LIMIT": "25",
            "INJECT_FOLLOWUPS": "true",
            "STEP_MODE": "true",
            "STARTUP_READS": "true",
            "EDIT_DELTA_OUTPUT": "true",
            "MCP_MODE": "false",
            "NODE_VISIT_LIMIT": "100",
            "BATCH_SIZE": "4",
        }
        for k, v in env_overrides.items():
            os.environ[k] = v

        try:
            reg = LifecycleRegistry()
            __initialize__(reg)
            with enter_phase(system, registry=reg) as scope:
                cfg = scope.get_singleton(McpConfig)
                self.assertEqual(cfg.conversation_limit, 25)
                self.assertTrue(cfg.inject_followups)
                self.assertTrue(cfg.is_step_mode)
                self.assertTrue(cfg.is_startup_reads)
                self.assertTrue(cfg.edit_delta_output)
                self.assertFalse(cfg.is_mcp_mode)
                self.assertEqual(cfg.node_visit_limit, 100)
                self.assertEqual(cfg.batch_size, 4)
        finally:
            for k in env_overrides:
                os.environ.pop(k, None)

    def test_mutable_mcp_mode(self) -> None:
        """CUJ: Update mcp mode at runtime."""
        with enter_phase(system, registry=self.registry) as scope:
            cfg = scope.get_singleton(McpConfig)
            # Requirement: [AgentConfig] The agent config provides whether the agent should operate in mcp mode.
            self.assertTrue(cfg.is_mcp_mode)
            cfg.is_mcp_mode = False
            self.assertFalse(cfg.is_mcp_mode)
            cfg.is_mcp_mode = True
            self.assertTrue(cfg.is_mcp_mode)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
