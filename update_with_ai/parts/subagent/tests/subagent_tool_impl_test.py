# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:37Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_tool_impl unit tests
# CODE_HASH: 96140368a208
# COVERAGE_AUDIT: 2026-10-12T23:37:37Z
# QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Unit tests for subagent_tool_impl."""

from __future__ import annotations

import unittest
from typing import Optional

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.subagent.lib import (
    subagent_coordinator,
    subagent_harness,
    subagent_tool,
)
from update_with_ai.parts.subagent.lib.subagent_tool_impl import (
    SubagentToolRunner,
    __initialize__,
)


class FakeCoordinator:
    """Test double implementing SubagentCoordinator."""

    tier = agent_session.agent_session

    def __init__(self, converged: bool = True) -> None:
        self.converged = converged

    def compute_execution_waves(self, dir_scope: str, repo_root: Optional[str] = None, batch_size: Optional[int] = None):
        return ()

    def run_wave(self, wave, harness):
        return ()

    def orchestrate(
        self,
        dir_scope: str,
        harness: subagent_coordinator.HarnessAdapter,
        max_waves: int = 50,
        batch_size: Optional[int] = None,
        repo_root: Optional[str] = None,
    ) -> subagent_coordinator.OrchestrationSummary:
        return subagent_coordinator.OrchestrationSummary(
            is_converged=self.converged,
            total_waves=3,
            submitted_count=5,
            blamed_count=0,
            total_telemetry=subagent_coordinator.TokenUsage(
                input_tokens=1000,
                cached_tokens=500,
                output_tokens=200,
                total_tokens=1700,
                cost_usd=0.015,
            ),
            status_message="All units converged cleanly." if self.converged else "Convergence failed.",
        )


class FakeHarnessResolver:
    """Test double implementing HarnessResolver."""

    tier = agent_session.agent_session

    def resolve_harness(
        self,
        platform_name: str,
        model_name: Optional[str] = None,
        timeout_seconds: float = 600.0,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
    ) -> subagent_coordinator.HarnessAdapter:
        class DummyAdapter:
            def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
                return "dummy"

            def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
                return subagent_coordinator.RoleTurnResult(role="test", status="clean")

            def interrupt_role(self, task_handle: str) -> None:
                pass

        return DummyAdapter()


class SubagentToolImplTest(unittest.TestCase):
    """Test cases for SubagentToolRunner implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.fake_resolver = FakeHarnessResolver()
        self.fake_coord = FakeCoordinator(converged=True)

        self.registry.register_instance(
            self.fake_resolver,
            keys=[subagent_harness.HarnessResolver],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            self.fake_coord,
            keys=[subagent_coordinator.SubagentCoordinator],
            tier=agent_session.agent_session,
        )

    def test_run_orchestrate_success(self) -> None:
        """Verifies run_orchestrate returns 0 when coordinator converges."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            runner = scope.get_singleton(subagent_tool.SubagentToolRunner)
            status = runner.run_orchestrate("pkg_a", harness="simulation")
            self.assertEqual(status, 0)

    def test_run_orchestrate_failure(self) -> None:
        """Verifies run_orchestrate returns 1 when coordinator fails to converge."""
        self.fake_coord.converged = False
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            runner = scope.get_singleton(subagent_tool.SubagentToolRunner)
            status = runner.run_orchestrate("pkg_a", harness="simulation")
            self.assertEqual(status, 1)

    def test_execute_command_orchestrate(self) -> None:
        """Verifies execute_command parses orchestrate CLI arguments."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            runner = scope.get_singleton(subagent_tool.SubagentToolRunner)
            status = runner.execute_command(["orchestrate", "pkg_a", "--simulation"])
            self.assertEqual(status, 0)

    def test_execute_command_shorthand(self) -> None:
        """Verifies execute_command accepts scope without explicit subcommand keyword."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            runner = scope.get_singleton(subagent_tool.SubagentToolRunner)
            status = runner.execute_command(["pkg_a", "--simulation"])
            self.assertEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
