"""Low-level implementation for subagent_tool_impl."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    enter_phase,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import session as agent_session
from . import subagent_coordinator, subagent_harness, subagent_tool


# Contract: SubagentToolRunner realizes command dispatch and execution runner for subagent orchestration in the agent session tier.
class SubagentToolRunner(subagent_tool.SubagentToolRunner):
    """Realizes command dispatch and execution runner for subagent orchestration."""

    tier = agent_session.agent_session

    # Contract: SubagentToolRunner.execute_command - parses CLI argument sequence and executes selected action.
    def execute_command(self, argv: Sequence[str]) -> int:
        """Dispatches and executes subagent commands matching an argument sequence."""
        parser = argparse.ArgumentParser(
            prog="orchestrate",
            description="Cleanroom Multi-Agent Workspace Orchestrator",
        )
        subparsers = parser.add_subparsers(dest="command", metavar="<command>")

        orch_parser = subparsers.add_parser(
            "orchestrate",
            help="Orchestrates iterative multi-agent execution across topological waves.",
        )
        orch_parser.add_argument(
            "dir_scope",
            nargs="?",
            default="",
            help="Directory scope to orchestrate.",
        )
        orch_parser.add_argument(
            "target_role",
            nargs="?",
            default=None,
            help="Optional target role boundary to execute up to.",
        )
        orch_parser.add_argument(
            "--scope",
            dest="scope_opt",
            default="",
            help="Directory scope (alternative flag).",
        )
        orch_parser.add_argument(
            "--role",
            dest="role_opt",
            default=None,
            help="Target role boundary (alternative flag).",
        )
        orch_parser.add_argument(
            "--harness",
            default="antigravity",
            help="Subagent execution harness (antigravity, dsh, simulation).",
        )
        orch_parser.add_argument(
            "--model",
            default=None,
            help="Optional model name override.",
        )
        orch_parser.add_argument(
            "--max-waves",
            type=int,
            default=50,
            help="Maximum execution wave iterations (default: 50).",
        )
        orch_parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Maximum targets dispatched per role turn.",
        )
        orch_parser.add_argument(
            "--timeout",
            type=float,
            default=None,
            help="Maximum execution timeout in seconds for subagent processes (default: no timeout).",
        )
        orch_parser.add_argument(
            "--max-context-tokens",
            type=int,
            default=None,
            help="Context token compaction limit for subagent processes.",
        )
        orch_parser.add_argument(
            "--max-unproductive-rounds",
            "--max-unproductive-turns",
            dest="max_unproductive_rounds",
            type=int,
            default=None,
            help="Maximum consecutive unproductive rounds before halting execution (default: resolved from model configuration or 5).",
        )
        orch_parser.add_argument(
            "--target",
            dest="target_node",
            default=None,
            help="Optional target unit or node boundary to restrict execution to.",
        )
        orch_parser.add_argument(
            "--repo-root",
            default=None,
            help="Repository root directory.",
        )
        orch_parser.add_argument(
            "--simulation",
            "--simulate",
            dest="simulation",
            action="store_true",
            help="Run in simulation mode without external subprocesses.",
        )
        orch_parser.add_argument(
            "--pretense",
            action="store_true",
            help="Use Pretense testing pipeline.",
        )

        args_list = list(argv)
        if not args_list or args_list[0] != "orchestrate":
            args_list = ["orchestrate"] + args_list

        parsed = parser.parse_args(args_list)
        if parsed.command == "orchestrate":
            scope = parsed.scope_opt or parsed.dir_scope
            if not scope:
                parser.error("Directory scope must be specified.")
            target_role = parsed.role_opt or parsed.target_role
            return self.run_orchestrate(
                dir_scope=scope,
                target_role=target_role,
                harness="simulation" if parsed.simulation else parsed.harness,
                model=parsed.model,
                max_waves=parsed.max_waves,
                batch_size=parsed.batch_size,
                timeout=parsed.timeout,
                max_context_tokens=parsed.max_context_tokens,
                repo_root=parsed.repo_root,
                max_unproductive_rounds=parsed.max_unproductive_rounds,
                target_node=parsed.target_node,
                pretense=parsed.pretense,
            )

        parser.print_help()
        return 1

    # Contract: SubagentToolRunner.run_orchestrate - orchestrates multi-agent execution across topological waves until convergence.
    def run_orchestrate(
        self,
        dir_scope: str,
        target_role: Optional[str] = None,
        harness: Optional[str] = None,
        model: Optional[str] = None,
        max_waves: int = 50,
        batch_size: Optional[int] = None,
        timeout: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        repo_root: Optional[str] = None,
        max_unproductive_turns: Optional[int] = None,
        target_node: Optional[str] = None,
        max_unproductive_rounds: Optional[int] = None,
        pretense: bool = False,
    ) -> int:
        """Orchestrates multi-agent execution across topological waves until convergence."""
        effective_unproductive = (
            max_unproductive_rounds
            if max_unproductive_rounds is not None
            else max_unproductive_turns
        )
        resolver = get_singleton(subagent_harness.HarnessResolver)
        harness_name = harness or "antigravity"
        simulation_mode = harness_name.lower() == "simulation"
        adapter = resolver.resolve_harness(
            platform_name=harness_name,
            model_name=model,
            timeout_seconds=timeout,
            max_context_tokens=max_context_tokens,
            simulation_mode=simulation_mode,
        )

        coordinator = get_singleton(subagent_coordinator.SubagentCoordinator)
        summary = coordinator.orchestrate(
            dir_scope=dir_scope,
            harness=adapter,
            target_role=target_role,
            max_waves=max_waves,
            batch_size=batch_size,
            repo_root=repo_root,
            model_name=model,
            max_unproductive_rounds=effective_unproductive,
            target_node=target_node,
        )

        print("\n=== Cleanroom Orchestration Summary ===")
        print(f"Status:     {'CONVERGED' if summary.is_converged else 'FAILED'}")
        print(f"Waves:      {summary.total_waves}")
        print(f"Submitted:  {summary.submitted_count}")
        print(f"Blamed:     {summary.blamed_count}")
        tel = summary.total_telemetry
        print(
            f"Tokens:     {tel.total_tokens} "
            f"(in: {tel.input_tokens}, cached: {tel.cached_tokens}, out: {tel.output_tokens})"
        )
        print(f"Est Cost:   ${tel.cost_usd:.4f}")
        print(f"Message:    {summary.status_message}\n")

        return 0 if summary.is_converged else 1


# Contract: __orphan__ - CLI Entrypoint executing within agent_session lifecycle phase
def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI Entrypoint executing within agent_session lifecycle phase."""
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    with enter_phase(agent_session.agent_session):
        try:
            runner = get_singleton(subagent_tool.SubagentToolRunner)
        except (KeyError, LifecycleResolutionError):
            from . import subagent_asm
            subagent_asm.__initialize__()
            runner = get_singleton(subagent_tool.SubagentToolRunner)
        return runner.execute_command(raw_args)
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-25T21:50:00Z
# CHANGE: Support pretense pipeline option in orchestrate CLI arguments
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        SubagentToolRunner,
        keys=[subagent_tool.SubagentToolRunner, SubagentToolRunner],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
