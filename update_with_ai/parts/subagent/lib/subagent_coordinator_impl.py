"""Low-level implementation for subagent_coordinator_impl."""

from __future__ import annotations

import json
import os
import shutil
import time
from typing import Dict, List, Optional, Sequence, Set, Tuple

try:
    import tomllib  # type: ignore
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.workspace_cli.lib import work
from update_with_ai.parts.workspace.lib import (
    provision,
    role_registry,
)
from . import subagent_coordinator


# Contract: __orphan__ - MUST dynamically resolve subagent batch sizes, conversation token limits, and maximum unproductive rounds thresholds from model configurations.
def resolve_model_parameters(
    repo_root: str,
    model_name: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Resolves (subagent_batch_size, conversation_max_tokens, max_unproductive_rounds) from model_configs.toml."""
    if tomllib is None:
        return None, None, None
    cfg_path = os.path.join(repo_root, "model_configs.toml")
    if not os.path.isfile(cfg_path):
        env_cfg = os.environ.get("CLEANROOM_MODEL_CONFIG_FILE")
        if env_cfg and os.path.isfile(env_cfg):
            cfg_path = env_cfg
        elif model_name:
            candidates = [
                os.path.join(os.path.dirname(repo_root), "model_configs.toml"),
            ]
            try:
                from support.lib import app_info
                candidates.append(app_info.get_user_model_config_file())
                candidates.append(app_info.get_template_model_config_file())
            except Exception:
                try:
                    from update_with_ai.support.lib import app_info
                    candidates.append(app_info.get_user_model_config_file())
                    candidates.append(app_info.get_template_model_config_file())
                except Exception:
                    try:
                        from update_python_with_ai.support.lib import app_info
                        candidates.append(app_info.get_user_model_config_file())
                        candidates.append(app_info.get_template_model_config_file())
                    except Exception:
                        candidates.append(os.path.expanduser("~/.config/cleanroom/model_configs.toml"))
            for cand in candidates:
                if cand and os.path.isfile(cand):
                    cfg_path = cand
                    break
        else:
            return None, None, None

    if not cfg_path or not os.path.isfile(cfg_path):
        return None, None, None
    try:
        with open(cfg_path, "rb") as f:
            cfg = tomllib.load(f)
    except Exception:
        return None, None, None

    global_unproductive: Optional[int] = None
    u_top = cfg.get("max_unproductive_rounds")
    if u_top is not None:
        try:
            global_unproductive = int(u_top)
        except (ValueError, TypeError):
            pass

    models_dict = cfg.get("models", {})
    if not isinstance(models_dict, dict):
        return None, None, global_unproductive

    target = model_name or cfg.get("default")
    if not target or not isinstance(target, str):
        return None, None, global_unproductive

    target_clean = target.strip().lower()
    matched_data = None

    for k, v in models_dict.items():
        if k.lower() == target_clean and isinstance(v, dict):
            matched_data = v
            break

    if matched_data is None:
        for k, v in models_dict.items():
            if not isinstance(v, dict):
                continue
            m_field = str(v.get("model", "")).lower().strip()
            if (
                (m_field and (target_clean == m_field or target_clean in m_field or m_field in target_clean))
                or target_clean in k.lower()
            ):
                matched_data = v
                break

    if matched_data is None:
        return None, None, global_unproductive

    resolved_batch: Optional[int] = None
    b_val = matched_data.get("subagent_batch_size") or matched_data.get("batch_size")
    if b_val is not None:
        try:
            resolved_batch = int(b_val)
        except (ValueError, TypeError):
            pass

    resolved_tokens: Optional[int] = None
    t_val = matched_data.get("conversation_max_tokens")
    if t_val is not None:
        try:
            resolved_tokens = int(t_val)
        except (ValueError, TypeError):
            pass

    resolved_unproductive = global_unproductive
    u_val = matched_data.get("max_unproductive_rounds")
    if u_val is not None:
        try:
            resolved_unproductive = int(u_val)
        except (ValueError, TypeError):
            pass

    return resolved_batch, resolved_tokens, resolved_unproductive


_resolve_model_parameters = resolve_model_parameters


def _persist_batch_size(ws_dir: str, batch_size: int) -> None:
    """Updates batch_size in .cleanroom_role.json in the role workspace."""
    meta_p = os.path.join(ws_dir, ".cleanroom_role.json")
    if not os.path.isfile(meta_p):
        return
    try:
        with open(meta_p, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if isinstance(meta, dict):
            meta["batch_size"] = batch_size
            with open(meta_p, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
    except Exception:
        pass


class SubagentCoordinator(subagent_coordinator.SubagentCoordinator):
    """Realizes zero-execution multi-agent workspace coordination across execution waves."""

    tier = agent_session.agent_session

    # Contract: discover ready dirty roles unblocked by upstream prerequisites across directory scope
    # Contract: commission absent workspace directory via WorkspaceProvisioner
    # Contract: separate sequential specification roles into single-role waves
    # Contract: combine independent unblocked implementation roles into parallel waves
    # Contract: return sequence of execution waves containing role dispatch directives
    def compute_execution_waves(
        self,
        dir_scope: str,
        target_role: Optional[str] = None,
        repo_root: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> Sequence[Sequence[subagent_coordinator.RoleDispatch]]:
        """Evaluates DAG queues and groups unblocked ready roles into execution waves."""
        reg = get_singleton(role_registry.WorkspaceRegistry)
        work_mgr = get_singleton(work.WorkspaceWorkManager)

        root = repo_root or reg.discover_repository_root()
        all_roles = reg.list_roles(repo_root=root, dir_scope=dir_scope)
        if target_role:
            target_clean = target_role.strip().lower()
            matching_idx = None
            for idx, r_entry in enumerate(all_roles):
                r_name = r_entry.role_name if hasattr(r_entry, "role_name") else str(r_entry)
                if r_name.lower() == target_clean:
                    matching_idx = idx
                    break
            if matching_idx is not None:
                all_roles = all_roles[: matching_idx + 1]

        ready_dispatches: Dict[str, subagent_coordinator.RoleDispatch] = {}
        role_definitions: Dict[str, role_registry.RoleDefinition] = {}

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
                if not os.path.isdir(ws_dir) or not os.path.isdir(os.path.join(ws_dir, "bin")):
                    prov = get_singleton(provision.WorkspaceProvisioner)
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

    # Contract: dispatch each role directive through harness.dispatch_role
    # Contract: await completion of each dispatched role through harness.await_role
    # Contract: return sequence of role round results
    def run_wave(
        self,
        wave: Sequence[subagent_coordinator.RoleDispatch],
        harness: subagent_coordinator.HarnessAdapter,
    ) -> Sequence[subagent_coordinator.RoleRoundResult]:
        """Dispatches all roles in an execution wave through the harness and awaits results."""
        handles: List[str] = []
        for dispatch in wave:
            handle = harness.dispatch_role(dispatch)
            handles.append(handle)

        results: List[subagent_coordinator.RoleRoundResult] = []
        for handle in handles:
            res = harness.await_role(handle)
            results.append(res)

        return tuple(results)

    # Contract: reset preexisting role workspaces for declared roles upon initiating orchestration
    # Contract: iterate through execution waves until all units in scope evaluate clean, role fails, or max_waves reached
    # Contract: periodically poll active workers through harness.poll_role or harness.await_role at configurable interval (default 10s)
    # Contract: when role round reports status failed, stop execution and return non-converged summary with failure details
    # Contract: when consecutive unproductive rounds exceed threshold (default 2), stop execution and return non-converged summary
    # Contract: emit real-time progress notifications detailing role dispatch, round outcomes, token consumption, and work queue state
    # Contract: when all units evaluate clean across all roles, automatically delete all provisioned role workspaces in scope and return converged summary
    # Contract: aggregate cumulative token usage and monetary expenditure in orchestration summary
    def orchestrate(
        self,
        dir_scope: str,
        harness: subagent_coordinator.HarnessAdapter,
        target_role: Optional[str] = None,
        max_waves: int = 50,
        batch_size: Optional[int] = None,
        repo_root: Optional[str] = None,
        model_name: Optional[str] = None,
        poll_interval: Optional[float] = None,
        max_unproductive_turns: Optional[int] = None,
        target_node: Optional[str] = None,
        max_unproductive_rounds: Optional[int] = None,
    ) -> subagent_coordinator.OrchestrationSummary:
        """Orchestrates iterative multi-agent execution until DAG convergence or failure."""
        reg = get_singleton(role_registry.WorkspaceRegistry)
        work_mgr = get_singleton(work.WorkspaceWorkManager)
        root = repo_root or reg.discover_repository_root()

        # Resolve model parameters from model_configs.toml
        resolved_batch, _, resolved_unproductive = _resolve_model_parameters(root, model_name=model_name)
        effective_batch_size = batch_size if batch_size is not None else resolved_batch
        user_unproductive = max_unproductive_rounds if max_unproductive_rounds is not None else max_unproductive_turns
        effective_max_unproductive = (
            user_unproductive
            if user_unproductive is not None
            else (resolved_unproductive if resolved_unproductive is not None else 5)
        )
        unproductive_rounds: Dict[str, int] = {}
        unresolved_reminders: Dict[str, str] = {}

        print(f"[ORCHESTRATE] Starting orchestration: scope='{dir_scope}', max_waves={max_waves}", flush=True)

        # Reset and recommission role workspaces for declared roles in scope to ensure clean initial state with model binding
        all_scope_roles = reg.list_roles(repo_root=root, dir_scope=dir_scope)
        for r_entry in all_scope_roles:
            r_name = r_entry.role_name if hasattr(r_entry, "role_name") else str(r_entry)
            ws_dir = reg.compute_workspace_dir(r_name, dir_scope=dir_scope, repo_root=root)
            if os.path.isdir(ws_dir):
                shutil.rmtree(ws_dir, ignore_errors=True)
            try:
                prov = get_singleton(provision.WorkspaceProvisioner)
                prov.commission(
                    role_name=r_name,
                    dir_scope=dir_scope,
                    repo_root=root,
                    reset=True,
                    model=model_name,
                )
            except Exception:
                pass

        # Filter roles up to target_role if specified
        roles_to_evaluate = all_scope_roles
        if target_role:
            target_clean = target_role.strip().lower()
            matching_idx = None
            for idx, r_entry in enumerate(roles_to_evaluate):
                r_name = r_entry.role_name if hasattr(r_entry, "role_name") else str(r_entry)
                if r_name.lower() == target_clean:
                    matching_idx = idx
                    break
            if matching_idx is not None:
                roles_to_evaluate = roles_to_evaluate[: matching_idx + 1]

        wave_count = 0
        submitted_count = 0
        blamed_count = 0
        cumulative_input = 0
        cumulative_cached = 0
        cumulative_output = 0
        cumulative_cost = 0.0
        failure_msg: Optional[str] = None
        active_workers: Dict[str, str] = {}  # role_name -> task_handle
        assigned_targets_map: Dict[str, Sequence[str]] = {}  # role_name -> assigned targets
        try:
            # Continuous dynamic queue-driven process supervision loop
            queue_dirty = True
            sleep_interval = poll_interval if poll_interval is not None else 10.0

            while wave_count < max_waves:
                # 1. Harvest finished workers (non-blocking)
                worker_finished = False
                for role_name, handle in list(active_workers.items()):
                    if hasattr(harness, "poll_role"):
                        res = harness.poll_role(handle)
                    else:
                        res = harness.await_role(handle)
                    if res is not None:
                        del active_workers[role_name]
                        assigned_for_role = assigned_targets_map.pop(role_name, ())
                        worker_finished = True
                        submitted_count += len(res.submitted_targets)
                        blamed_count += len(res.blamed_targets)
                        if res.telemetry:
                            cumulative_input += res.telemetry.input_tokens
                            cumulative_cached += res.telemetry.cached_tokens
                            cumulative_output += res.telemetry.output_tokens
                            cumulative_cost += res.telemetry.cost_usd
                        tok_info = f", tokens={res.telemetry.total_tokens} (${res.telemetry.cost_usd:.4f})" if res.telemetry else ""
                        print(
                            f"[ORCHESTRATE] Worker '{role_name}' finished [{res.status}]: "
                            f"submitted={len(res.submitted_targets)}, blamed={len(res.blamed_targets)}{tok_info}, "
                            f"elapsed={res.wall_clock_seconds:.1f}s",
                            flush=True,
                        )
                        if res.status == "failed":
                            failure_msg = res.failure_reason or f"Role {role_name} failed execution."
                            break
                        if len(res.submitted_targets) == 0 and len(res.blamed_targets) == 0:
                            # Verify whether assigned targets transitioned to clean or were resolved in active work queue
                            ready_now, _ = work_mgr.compute_role_work_queue(
                                role_name,
                                dir_scope=dir_scope,
                                repo_root=root,
                                target_unit=target_node,
                            )
                            ready_targets_now = {item.target_file for item in ready_now}
                            is_resolved = False
                            if assigned_for_role:
                                is_resolved = any(t not in ready_targets_now for t in assigned_for_role)
                            elif not ready_now:
                                is_resolved = True

                            if is_resolved:
                                unproductive_rounds[role_name] = 0
                                unresolved_reminders.pop(role_name, None)
                            else:
                                unproductive_rounds[role_name] = unproductive_rounds.get(role_name, 0) + 1
                                unresolved_reminders[role_name] = (
                                    f"CRITICAL REMINDER: The previous round for role '{role_name}' concluded without submitting, blaming, or failing any assigned targets.\n"
                                    f"Conversational commentary without tool execution is strictly prohibited.\n"
                                    f"You must verify your work with `bin/check_files <target>` and immediately conclude the round by running:\n"
                                    f"  - `bin/submit <target> \"<summary>\"` (to certify valid targets),\n"
                                    f"  - `bin/blame <culprit_target> \"<critique>\"` (if an upstream dependency has defects), or\n"
                                    f"  - `bin/fail` (if encountering an unrecoverable failure).\n"
                                    f"Execute the appropriate tools now to complete and conclude the round."
                                )
                                if unproductive_rounds[role_name] >= effective_max_unproductive:
                                    failure_msg = (
                                        f"Role '{role_name}' made no progress (0 submitted, 0 blamed) "
                                        f"for {unproductive_rounds[role_name]} consecutive rounds."
                                    )
                                    print(f"[ORCHESTRATE] Circuit breaker tripped: {failure_msg}", flush=True)
                                    break
                        else:
                            unproductive_rounds[role_name] = 0
                            unresolved_reminders.pop(role_name, None)

                if worker_finished:
                    queue_dirty = True

                if failure_msg is not None:
                    for h in active_workers.values():
                        harness.interrupt_role(h)
                    break

                # 2. Check work queues only if queue is dirty or no active workers
                if queue_dirty or not active_workers:
                    all_clean = True
                    blocked_count = 0
                    ready_roles_map: Dict[str, Sequence[str]] = {}

                    for r_entry in roles_to_evaluate:
                        r_name = r_entry.role_name if hasattr(r_entry, "role_name") else str(r_entry)
                        ready, blocked = work_mgr.compute_role_work_queue(
                            r_name,
                            dir_scope=dir_scope,
                            repo_root=root,
                            target_unit=target_node,
                        )
                        if ready:
                            all_clean = False
                            ready_roles_map[r_name] = [item.target_file for item in ready]
                        if blocked:
                            all_clean = False
                            blocked_count += len(blocked)

                    queue_dirty = False

                    # 3. Clean convergence check
                    if not active_workers and all_clean:
                        for r_entry in all_scope_roles:
                            r_name = r_entry.role_name if hasattr(r_entry, "role_name") else str(r_entry)
                            ws_dir = reg.compute_workspace_dir(r_name, dir_scope=dir_scope, repo_root=root)
                            if os.path.isdir(ws_dir):
                                shutil.rmtree(ws_dir, ignore_errors=True)

                        total_tokens = cumulative_input + cumulative_cached + cumulative_output
                        telemetry = subagent_coordinator.TokenUsage(
                            input_tokens=cumulative_input,
                            cached_tokens=cumulative_cached,
                            output_tokens=cumulative_output,
                            total_tokens=total_tokens,
                            cost_usd=cumulative_cost,
                        )
                        print(
                            f"[ORCHESTRATE] Clean convergence achieved across all roles in scope '{dir_scope}'!",
                            flush=True,
                        )
                        return subagent_coordinator.OrchestrationSummary(
                            is_converged=True,
                            total_waves=wave_count,
                            submitted_count=submitted_count,
                            blamed_count=blamed_count,
                            total_telemetry=telemetry,
                            status_message="All units converged cleanly across all roles.",
                        )

                    # 4. Deadlock check: no active workers, no ready roles, but blocked units remain
                    if not active_workers and not ready_roles_map:
                        total_tokens = cumulative_input + cumulative_cached + cumulative_output
                        telemetry = subagent_coordinator.TokenUsage(
                            input_tokens=cumulative_input,
                            cached_tokens=cumulative_cached,
                            output_tokens=cumulative_output,
                            total_tokens=total_tokens,
                            cost_usd=cumulative_cost,
                        )
                        print(
                            f"[ORCHESTRATE] Deadlocked: {blocked_count} units blocked on unresolved prerequisites.",
                            flush=True,
                        )
                        return subagent_coordinator.OrchestrationSummary(
                            is_converged=False,
                            total_waves=wave_count,
                            submitted_count=submitted_count,
                            blamed_count=blamed_count,
                            total_telemetry=telemetry,
                            status_message=f"Orchestration deadlocked: {blocked_count} units blocked on unresolved prerequisites.",
                        )

                    # 5. Dispatch unblocked ready roles concurrently
                    dispatched_any = False
                    for r_name, target_paths in ready_roles_map.items():
                        if r_name not in active_workers:
                            if effective_batch_size is not None and effective_batch_size > 0:
                                target_paths = target_paths[:effective_batch_size]

                            ws_dir = reg.compute_workspace_dir(r_name, dir_scope=dir_scope, repo_root=root)
                            if not os.path.isdir(ws_dir) or not os.path.isdir(os.path.join(ws_dir, "bin")):
                                prov = get_singleton(provision.WorkspaceProvisioner)
                                prov.commission(r_name, dir_scope=dir_scope, repo_root=root, model=model_name)

                            if effective_batch_size is not None:
                                _persist_batch_size(ws_dir, effective_batch_size)

                            reminder = unresolved_reminders.pop(r_name, "")
                            dispatch = subagent_coordinator.RoleDispatch(
                                role_name=r_name,
                                workspace_dir=ws_dir,
                                dir_scope=dir_scope,
                                ready_targets=tuple(target_paths),
                                batch_size=effective_batch_size,
                                task_prompt=reminder,
                            )
                            handle = harness.dispatch_role(dispatch)
                            active_workers[r_name] = handle
                            assigned_targets_map[r_name] = tuple(target_paths)
                            dispatched_any = True
                            print(
                                f"[ORCHESTRATE] Dispatched role '{r_name}' on {len(target_paths)} target(s): {', '.join(target_paths)}",
                                flush=True,
                            )

                    if dispatched_any:
                        wave_count += 1
                        if wave_count >= max_waves:
                            break

                # 6. Sleep if active workers are still running
                if active_workers:
                    time.sleep(sleep_interval)
        except (KeyboardInterrupt, SystemExit):
            print(
                f"[ORCHESTRATE] Interruption received; interrupting {len(active_workers)} active worker(s) and cleaning up workspaces...",
                flush=True,
            )
            for h in active_workers.values():
                try:
                    harness.interrupt_role(h)
                except Exception:
                    pass
            for r_entry in all_scope_roles:
                r_name = r_entry.role_name if hasattr(r_entry, "role_name") else str(r_entry)
                ws_dir = reg.compute_workspace_dir(r_name, dir_scope=dir_scope, repo_root=root)
                if os.path.isdir(ws_dir):
                    shutil.rmtree(ws_dir, ignore_errors=True)
            raise

        total_tokens = cumulative_input + cumulative_cached + cumulative_output
        telemetry = subagent_coordinator.TokenUsage(
            input_tokens=cumulative_input,
            cached_tokens=cumulative_cached,
            output_tokens=cumulative_output,
            total_tokens=total_tokens,
            cost_usd=cumulative_cost,
        )

        if failure_msg is not None:
            print(f"[ORCHESTRATE] Execution halted: {failure_msg}", flush=True)
            return subagent_coordinator.OrchestrationSummary(
                is_converged=False,
                total_waves=wave_count,
                submitted_count=submitted_count,
                blamed_count=blamed_count,
                total_telemetry=telemetry,
                status_message=f"Orchestration failed: {failure_msg}",
            )

        print(f"[ORCHESTRATE] Maximum wave limit ({max_waves}) reached before convergence.", flush=True)
        return subagent_coordinator.OrchestrationSummary(
            is_converged=False,
            total_waves=wave_count,
            submitted_count=submitted_count,
            blamed_count=blamed_count,
            total_telemetry=telemetry,
            status_message=f"Maximum wave limit ({max_waves}) reached before convergence.",
        )

    # Contract: Resolves the canonical repository logs directory for a role workspace.
    def resolve_cleanroom_log_dir(self, workspace_dir: str) -> str:
        """Resolves the canonical repository logs directory for a role workspace."""
        return subagent_coordinator.resolve_cleanroom_log_dir(workspace_dir)

    def resolve_model_parameters(
        self,
        repo_root: str,
        model_name: Optional[str] = None,
    ) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """Dynamically resolves subagent batch sizes, token limits, and unproductive round thresholds."""
        return _resolve_model_parameters(repo_root, model_name=model_name)
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-18T19:13:51Z
# LAST_CHANGED: 2026-10-20T23:55:00Z
# CHANGE: Suppress unproductive rounds and scolding reminders when assigned targets are resolved or cleaned in repository
# COVERAGE_AUDIT: 2026-10-18T19:13:51Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


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
