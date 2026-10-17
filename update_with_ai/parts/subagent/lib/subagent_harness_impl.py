# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T11:00:00Z
# CHANGE: turn down support for goose, supporting only antigravity and dsh
# CODE_HASH: 7fd31d6b5b1d
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for subagent_harness_impl."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.workspace_cli.lib import work
from . import subagent_coordinator, subagent_harness


# Contract: inspect workspace blame buffer for reported defects (await_role)
def _read_blame_buffer(workspace_dir: str) -> List[str]:
    """Reads blamed culprit files from the workspace blame buffer."""
    p = os.path.join(workspace_dir, ".cleanroom_blame_buffer.json")
    if not os.path.isfile(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            res: List[str] = []
            for item in data:
                if isinstance(item, str):
                    res.append(item)
                elif isinstance(item, dict):
                    t = item.get("culprit_target") or item.get("target") or item.get("file")
                    if t:
                        res.append(str(t))
            return res
        elif isinstance(data, dict):
            res = data.get("targets") or data.get("blamed_targets") or []
            return [str(x) for x in res]
    except (OSError, json.JSONDecodeError):
        pass
    return []


# Contract: extract token usage metrics and return synthesized RoleTurnResult (await_role)
def _parse_token_usage_from_log(log_path: str) -> subagent_coordinator.TokenUsage:
    """Parses token telemetry and computes rate-card monetary costs."""
    if not os.path.isfile(log_path):
        return subagent_coordinator.TokenUsage()
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return subagent_coordinator.TokenUsage()

    input_tokens = 0
    cached_tokens = 0
    output_tokens = 0

    for m in re.finditer(r"(?:input_tokens|Input tokens)[:=]\s*(\d+)", content, re.IGNORECASE):
        input_tokens += int(m.group(1))
    for m in re.finditer(r"(?:cached_tokens|Cached tokens)[:=]\s*(\d+)", content, re.IGNORECASE):
        cached_tokens += int(m.group(1))
    for m in re.finditer(r"(?:output_tokens|Output tokens)[:=]\s*(\d+)", content, re.IGNORECASE):
        output_tokens += int(m.group(1))

    for m in re.finditer(r"Model request:\s*(\d+)(K)?\s*tokens,\s*(\d+)%\s*cached", content, re.IGNORECASE):
        val = int(m.group(1))
        if m.group(2):
            val *= 1000
        pct = int(m.group(3))
        cached = int(val * (pct / 100.0))
        uncached = val - cached
        cached_tokens += cached
        input_tokens += uncached

    total_tokens = input_tokens + cached_tokens + output_tokens
    cost = (input_tokens * 0.0000025) + (cached_tokens * 0.000000625) + (output_tokens * 0.000010)

    return subagent_coordinator.TokenUsage(
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
    )


@dataclass
class _ActiveTask:
    task_handle: str
    dispatch: subagent_coordinator.RoleDispatch
    proc: Optional[subprocess.Popen[str]]
    log_file: str
    pre_pending: Sequence[str]
    start_time: float


class CommandHarnessAdapter(
    subagent_harness.CommandHarnessAdapter,
):
    """Realizes subagent turn execution through process command templates."""

    tier = agent_session.agent_session

    def __init__(
        self,
        cmd_template: str = "agy run {prompt_file}",
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
        simulation_mode: bool = False,
    ) -> None:
        self.cmd_template = cmd_template
        self.timeout_seconds = timeout_seconds
        self.max_context_tokens = max_context_tokens
        self.model_name = model_name
        self.simulation_mode = simulation_mode
        self._active_tasks: Dict[str, _ActiveTask] = {}
        self._task_counter = 0

    # Contract: format instructional task prompt detailing role, directory scope, targets, verification commands, and submit or blame actions
    def format_task_prompt(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Constructs instructional task prompt for the role subagent."""
        targets_str = (
            "\n".join(f"- {t}" for t in dispatch.ready_targets)
            if dispatch.ready_targets
            else "(none)"
        )
        return (
            f"# Cleanroom Autonomous Role Execution\n\n"
            f"- Role: {dispatch.role_name}\n"
            f"- Scope: {dispatch.dir_scope}\n"
            f"- Workspace: {dispatch.workspace_dir}\n\n"
            f"## Assigned Targets\n{targets_str}\n\n"
            "CRITICAL: DO NOT EDIT METADATA. Never touch `# --- CLEANROOM METADATA ---` or `<!-- CLEANROOM METADATA -->` headers. Use only tools.\n\n"
            f"## Instructions\n"
            f"1. Align and verify your assigned targets according to your role guide.\n"
            f"2. Run verification commands to check consistency:\n"
            f"   `bin/check_files`\n"
            f"3. When targets are verified clean, submit them:\n"
            f"   `bin/submit <target_file> --summary \"...\"`\n"
            f"4. If you discover a defect in an upstream contract or specification:\n"
            f"   `bin/blame <culprit_file> --critique \"...\"`\n"
            f"5. If unresolvable blocker:\n"
            f"   `bin/fail <target_file> --reason \"...\"`\n"
        )

    # Contract: record initial pending targets from workspace pending work buffer
    # Contract: spawn subagent process matching configured command template within workspace directory
    # Contract: return unique task handle tracking the running turn
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a subagent bound to the role workspace."""
        self._task_counter += 1
        handle = f"task_{dispatch.role_name}_{self._task_counter}_{int(time.time())}"

        work_mgr = get_singleton(work.WorkspaceWorkManager)
        pre_pending = list(work_mgr.get_pending_work(dispatch.workspace_dir))
        if not pre_pending:
            pre_pending = list(dispatch.ready_targets)
            work_mgr.set_pending_work(dispatch.workspace_dir, pre_pending)

        log_dir = subagent_coordinator.resolve_cleanroom_log_dir(dispatch.workspace_dir)
        prompt_text = self.format_task_prompt(dispatch)
        prompt_file = os.path.join(log_dir, f".cleanroom_task_prompt_{handle}.md")
        try:
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt_text)
        except OSError:
            pass

        log_file = os.path.join(log_dir, f".cleanroom_turn_{handle}.log")
        start_time = time.time()

        proc: Optional[subprocess.Popen[str]] = None
        if not self.simulation_mode:
            cmd = self.cmd_template.format(
                workspace_dir=dispatch.workspace_dir,
                role_name=dispatch.role_name,
                dir_scope=dispatch.dir_scope,
                prompt_file=prompt_file,
                task_prompt=prompt_text,
                log_file=log_file,
            )
            log_f = open(log_file, "w", encoding="utf-8")
            env = os.environ.copy()
            try:
                proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=dispatch.workspace_dir,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                )
            except Exception as e:
                log_f.write(f"Failed to spawn process: {e}\n")
                log_f.close()

        self._active_tasks[handle] = _ActiveTask(
            task_handle=handle,
            dispatch=dispatch,
            proc=proc,
            log_file=log_file,
            pre_pending=pre_pending,
            start_time=start_time,
        )
        return handle

    # Contract: await process completion without mandatory timeout unless explicit limit configured
    # Contract: when process times out, terminate process and return failed result
    # Contract: inspect workspace blame buffer for reported defects
    # Contract: determine submitted targets by set difference with remaining pending items
    # Contract: extract token usage metrics and return synthesized RoleTurnResult
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result."""
        task = self._active_tasks.pop(task_handle, None)
        if task is None:
            return subagent_coordinator.RoleTurnResult(
                role="unknown",
                status="failed",
                failure_reason=f"Task handle '{task_handle}' not found.",
            )

        elapsed = time.time() - task.start_time
        failure_reason: Optional[str] = None
        status = "clean"

        if not self.simulation_mode and task.proc is not None:
            try:
                if self.timeout_seconds is not None and self.timeout_seconds > 0:
                    task.proc.wait(timeout=self.timeout_seconds)
                else:
                    task.proc.wait()
            except subprocess.TimeoutExpired:
                task.proc.kill()
                task.proc.wait()
                return subagent_coordinator.RoleTurnResult(
                    role=task.dispatch.role_name,
                    status="failed",
                    failure_reason=f"Subagent process timed out after {self.timeout_seconds} seconds.",
                    wall_clock_seconds=elapsed,
                )

            if task.proc.returncode != 0:
                tail_msg = ""
                if os.path.isfile(task.log_file):
                    try:
                        with open(task.log_file, "r", encoding="utf-8", errors="replace") as lf:
                            lines = lf.readlines()
                            tail_msg = "".join(lines[-10:])
                    except OSError:
                        pass
                status = "failed"
                failure_reason = f"Process exited with non-zero status {task.proc.returncode}.\n{tail_msg}".strip()

            # Note: await_role primarily relies on blame buffer and pending work difference per contract.

        blamed = _read_blame_buffer(task.dispatch.workspace_dir)
        if blamed and status != "failed":
            status = "blamed"

        work_mgr = get_singleton(work.WorkspaceWorkManager)
        post_pending = set(work_mgr.get_pending_work(task.dispatch.workspace_dir))
        submitted = [t for t in task.pre_pending if t not in post_pending]

        telemetry = _parse_token_usage_from_log(task.log_file)

        return subagent_coordinator.RoleTurnResult(
            role=task.dispatch.role_name,
            status=status,
            submitted_targets=tuple(submitted),
            blamed_targets=tuple(blamed),
            failure_reason=failure_reason,
            telemetry=telemetry,
            wall_clock_seconds=elapsed,
        )

    # Contract: when subagent process has terminated, return role turn result
    # Contract: when subagent process is still running, return None without blocking or termination
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls subagent turn execution without blocking."""
        task = self._active_tasks.get(task_handle)
        if task is None:
            return subagent_coordinator.RoleTurnResult(
                role="unknown",
                status="failed",
                failure_reason=f"Task handle '{task_handle}' not found.",
            )

        if self.simulation_mode or task.proc is None:
            return self.await_role(task_handle)

        poll_res = task.proc.poll()
        if poll_res is None:
            if self.timeout_seconds is not None and self.timeout_seconds > 0:
                elapsed = time.time() - task.start_time
                if elapsed >= self.timeout_seconds:
                    return self.await_role(task_handle)
            return None

        return self.await_role(task_handle)

    # Contract: terminate active subagent process associated with task handle
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or loop limit."""
        task = self._active_tasks.get(task_handle)
        if task and task.proc is not None:
            try:
                task.proc.kill()
                task.proc.wait()
            except OSError:
                pass


class HarnessRegistry(
    subagent_harness.HarnessRegistry,
    Singleton,
):
    """Realizes harness registry and resolution for external agent platforms."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._installed_harnesses: Dict[str, subagent_harness.HarnessAdapterFactory] = {}

    # Contract: return mapping of installed platform names to harness adapter factories
    @property
    def installed_harnesses(self) -> Mapping[str, subagent_harness.HarnessAdapterFactory]:
        return dict(self._installed_harnesses)

    # Contract: register adapter factory under platform name in installed harnesses mapping
    def install_harness(
        self,
        platform_name: str,
        adapter_factory: subagent_harness.HarnessAdapterFactory,
    ) -> None:
        """Installs a harness adapter factory for a designated platform name."""
        self._installed_harnesses[platform_name.lower()] = adapter_factory

    # Contract: return CommandHarnessAdapter configured with custom command or simulation mode when requested
    # Contract: when platform is installed, invoke installed adapter factory and return harness adapter
    # Contract: when platform is not installed, raise ValueError
    def resolve_harness(
        self,
        platform_name: str,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
    ) -> subagent_coordinator.HarnessAdapter:
        """Resolves a harness adapter for a platform name or custom command template."""
        if simulation_mode or platform_name.lower() == "simulation":
            return CommandHarnessAdapter(
                cmd_template="simulation",
                timeout_seconds=timeout_seconds,
                max_context_tokens=max_context_tokens,
                model_name=model_name,
                simulation_mode=True,
            )

        if custom_cmd:
            return CommandHarnessAdapter(
                cmd_template=custom_cmd,
                timeout_seconds=timeout_seconds,
                max_context_tokens=max_context_tokens,
                model_name=model_name,
                simulation_mode=simulation_mode,
            )

        plat_key = platform_name.lower()
        factory = self._installed_harnesses.get(plat_key)
        if factory is None:
            avail = ", ".join(sorted(self._installed_harnesses.keys()))
            raise ValueError(
                f"Unknown platform '{platform_name}'. Available platforms: {avail}"
            )

        return factory(
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            max_context_tokens=max_context_tokens,
            custom_cmd=custom_cmd,
            simulation_mode=simulation_mode,
        )


HarnessResolver = HarnessRegistry


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        HarnessRegistry,
        keys=[
            subagent_harness.HarnessRegistry,
            subagent_harness.HarnessResolver,
            HarnessRegistry,
        ],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
