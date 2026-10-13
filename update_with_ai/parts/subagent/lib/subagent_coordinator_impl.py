# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:37Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_coordinator_impl implementation library
# CODE_HASH: f4157377d391
# COVERAGE_AUDIT: 2026-10-12T23:37:37Z
# QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for subagent_coordinator_impl."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Set

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.workspace.lib import (
    workspace_provision,
    workspace_registry,
    workspace_work,
)
from . import subagent_coordinator


class SubagentCoordinator(
    subagent_coordinator.SubagentCoordinator,
    Singleton,
):
    """Realizes zero-execution multi-agent workspace coordination across execution waves."""

    tier = agent_session.agent_session

    def compute_execution_waves(
        self,
        dir_scope: str,
        repo_root: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> Sequence[Sequence[subagent_coordinator.RoleDispatch]]:
        """Evaluates DAG queues and groups unblocked ready roles into execution waves."""
        reg = get_singleton(workspace_registry.WorkspaceRegistry)
        work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)

        root = repo_root or reg.discover_repository_root()
        all_roles = reg.list_roles(repo_root=root, dir_scope=dir_scope)

        ready_dispatches: Dict[str, subagent_coordinator.RoleDispatch] = {}
        role_definitions: Dict[str, workspace_registry.RoleDefinition] = {}

        for r_entry in all_roles:
            role = r_entry.role_name if hasattr(r_entry, "role_name") else str(r_entry)
            r_def = r_entry if hasattr(r_entry, "role_name") else reg.resolve_role_definition(role, repo_root=root)
            role_definitions[role] = r_def
            ready_items, _ = work_mgr.compute_role_work_queue(
                role, dir_scope=dir_scope, repo_root=root
            )
            if ready_items:
                target_paths = [item.target_file for item in ready_items]
                if batch_size is not None and batch_size > 0:
                    target_paths = target_paths[:batch_size]

                ws_dir = reg.compute_workspace_dir(
                    role, dir_scope=dir_scope, repo_root=root
                )
                if not os.path.isdir(ws_dir):
                    prov = get_singleton(workspace_provision.WorkspaceProvisioner)
                    prov.commission(role, dir_scope=dir_scope, repo_root=root)

                dispatch = subagent_coordinator.RoleDispatch(
                    role_name=role,
                    workspace_dir=ws_dir,
                    dir_scope=dir_scope,
                    ready_targets=tuple(target_paths),
                    batch_size=batch_size,
                    task_prompt="",
                )
                ready_dispatches[role] = dispatch

        if not ready_dispatches:
            return ()

        # Partition roles:
        # Roles without stub_role_deps are sequential specification roles -> single-role waves.
        # Roles with stub_role_deps are parallelizable implementation roles -> grouped parallel wave.
        sequential_roles: List[str] = []
        parallel_roles: List[str] = []

        for role in ready_dispatches:
            r_def = role_definitions[role]
            if r_def.stub_role_deps:
                parallel_roles.append(role)
            else:
                sequential_roles.append(role)

        # Topological sorting for sequential roles based on role dependencies
        ordered_sequential: List[str] = []
        visited: Set[str] = set()
        visiting: Set[str] = set()

        def visit(r: str) -> None:
            if r in visited:
                return
            if r in visiting:
                return  # Break dependency cycles defensively
            visiting.add(r)
            r_def = role_definitions.get(r)
            if r_def:
                deps = set(r_def.role_deps) | set(r_def.star_role_deps)
                for dep in deps:
                    if dep in ready_dispatches and dep in sequential_roles:
                        visit(dep)
            visiting.remove(r)
            visited.add(r)
            ordered_sequential.append(r)

        for r in sequential_roles:
            visit(r)

        waves: List[Sequence[subagent_coordinator.RoleDispatch]] = []
        # Each sequential role forms its own wave
        for r in ordered_sequential:
            waves.append((ready_dispatches[r],))

        # Parallel roles cluster into a single parallel wave
        if parallel_roles:
            parallel_wave = tuple(ready_dispatches[r] for r in parallel_roles)
            waves.append(parallel_wave)

        return tuple(waves)

    def run_wave(
        self,
        wave: Sequence[subagent_coordinator.RoleDispatch],
        harness: subagent_coordinator.HarnessAdapter,
    ) -> Sequence[subagent_coordinator.RoleTurnResult]:
        """Dispatches all roles in an execution wave through the harness and awaits results."""
        handles: List[str] = []
        for dispatch in wave:
            handle = harness.dispatch_role(dispatch)
            handles.append(handle)

        results: List[subagent_coordinator.RoleTurnResult] = []
        for handle in handles:
            res = harness.await_role(handle)
            results.append(res)

        return tuple(results)

    def orchestrate(
        self,
        dir_scope: str,
        harness: subagent_coordinator.HarnessAdapter,
        max_waves: int = 50,
        batch_size: Optional[int] = None,
        repo_root: Optional[str] = None,
    ) -> subagent_coordinator.OrchestrationSummary:
        """Orchestrates iterative multi-agent execution until DAG convergence or failure."""
        reg = get_singleton(workspace_registry.WorkspaceRegistry)
        work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
        root = repo_root or reg.discover_repository_root()

        wave_count = 0
        submitted_count = 0
        blamed_count = 0
        cumulative_input = 0
        cumulative_cached = 0
        cumulative_output = 0
        cumulative_cost = 0.0
        failure_msg: Optional[str] = None

        while wave_count < max_waves:
            waves = self.compute_execution_waves(
                dir_scope=dir_scope, repo_root=root, batch_size=batch_size
            )
            if not waves:
                # Check whether all units across all roles evaluate clean
                all_clean = True
                blocked_count = 0
                all_roles = reg.list_roles(repo_root=root, dir_scope=dir_scope)
                for r_entry in all_roles:
                    r_name = r_entry.role_name if hasattr(r_entry, "role_name") else str(r_entry)
                    ready, blocked = work_mgr.compute_role_work_queue(
                        r_name, dir_scope=dir_scope, repo_root=root
                    )
                    if ready or blocked:
                        all_clean = False
                        blocked_count += len(blocked)

                if all_clean:
                    total_tokens = cumulative_input + cumulative_cached + cumulative_output
                    telemetry = subagent_coordinator.TokenUsage(
                        input_tokens=cumulative_input,
                        cached_tokens=cumulative_cached,
                        output_tokens=cumulative_output,
                        total_tokens=total_tokens,
                        cost_usd=cumulative_cost,
                    )
                    return subagent_coordinator.OrchestrationSummary(
                        is_converged=True,
                        total_waves=wave_count,
                        submitted_count=submitted_count,
                        blamed_count=blamed_count,
                        total_telemetry=telemetry,
                        status_message="All units converged cleanly across all roles.",
                    )
                else:
                    total_tokens = cumulative_input + cumulative_cached + cumulative_output
                    telemetry = subagent_coordinator.TokenUsage(
                        input_tokens=cumulative_input,
                        cached_tokens=cumulative_cached,
                        output_tokens=cumulative_output,
                        total_tokens=total_tokens,
                        cost_usd=cumulative_cost,
                    )
                    return subagent_coordinator.OrchestrationSummary(
                        is_converged=False,
                        total_waves=wave_count,
                        submitted_count=submitted_count,
                        blamed_count=blamed_count,
                        total_telemetry=telemetry,
                        status_message=f"Orchestration deadlocked: {blocked_count} units blocked on unresolved prerequisites.",
                    )

            for wave in waves:
                wave_count += 1
                results = self.run_wave(wave, harness)
                for res in results:
                    submitted_count += len(res.submitted_targets)
                    blamed_count += len(res.blamed_targets)
                    if res.telemetry:
                        cumulative_input += res.telemetry.input_tokens
                        cumulative_cached += res.telemetry.cached_tokens
                        cumulative_output += res.telemetry.output_tokens
                        cumulative_cost += res.telemetry.cost_usd
                    if res.status == "failed":
                        failure_msg = res.failure_reason or f"Role {res.role} failed execution."
                        break
                if failure_msg is not None or wave_count >= max_waves:
                    break

            if failure_msg is not None:
                break

        total_tokens = cumulative_input + cumulative_cached + cumulative_output
        telemetry = subagent_coordinator.TokenUsage(
            input_tokens=cumulative_input,
            cached_tokens=cumulative_cached,
            output_tokens=cumulative_output,
            total_tokens=total_tokens,
            cost_usd=cumulative_cost,
        )

        if failure_msg is not None:
            return subagent_coordinator.OrchestrationSummary(
                is_converged=False,
                total_waves=wave_count,
                submitted_count=submitted_count,
                blamed_count=blamed_count,
                total_telemetry=telemetry,
                status_message=f"Orchestration failed: {failure_msg}",
            )

        return subagent_coordinator.OrchestrationSummary(
            is_converged=False,
            total_waves=wave_count,
            submitted_count=submitted_count,
            blamed_count=blamed_count,
            total_telemetry=telemetry,
            status_message=f"Maximum wave limit ({max_waves}) reached before convergence.",
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        SubagentCoordinator,
        keys=[subagent_coordinator.SubagentCoordinator, SubagentCoordinator],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
