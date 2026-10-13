# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_harness_impl implementation library
# CODE_HASH: 6c2389e8cab2
# COVERAGE_AUDIT: 2026-10-13T01:05:05Z
# QA_AUDIT: 2026-10-13T01:05:05Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for subagent_harness_impl."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Sequence

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.workspace.lib import workspace_work
from . import subagent_coordinator, subagent_harness


PLATFORM_TEMPLATES: Dict[str, str] = {
    "antigravity": "agy run --cwd {workspace_dir} --file {prompt_file}",
    "goose": "goose run --instruction-file {prompt_file}",
    "dsh": "dsh --dir {workspace_dir} --instruction {prompt_file}",
    "simulation": "echo simulation",
}


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
        timeout_seconds: float = 600.0,
        model_name: Optional[str] = None,
        simulation_mode: bool = False,
    ) -> None:
        self.cmd_template = cmd_template
        self.timeout_seconds = timeout_seconds
        self.model_name = model_name
        self.simulation_mode = simulation_mode
        self._active_tasks: Dict[str, _ActiveTask] = {}
        self._task_counter = 0

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

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a subagent bound to the role workspace."""
        self._task_counter += 1
        handle = f"task_{dispatch.role_name}_{self._task_counter}_{int(time.time())}"

        work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
        pre_pending = list(work_mgr.get_pending_work(dispatch.workspace_dir))
        if not pre_pending:
            pre_pending = list(dispatch.ready_targets)
            work_mgr.set_pending_work(dispatch.workspace_dir, pre_pending)

        prompt_text = self.format_task_prompt(dispatch)
        prompt_file = os.path.join(dispatch.workspace_dir, ".cleanroom_task_prompt.md")
        try:
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt_text)
        except OSError:
            pass

        log_file = os.path.join(dispatch.workspace_dir, f".cleanroom_turn_{handle}.log")
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
            try:
                proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=dispatch.workspace_dir,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
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
                task.proc.wait(timeout=self.timeout_seconds)
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

        blamed = _read_blame_buffer(task.dispatch.workspace_dir)
        if blamed and status != "failed":
            status = "blamed"

        work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
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

    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or loop limit."""
        task = self._active_tasks.get(task_handle)
        if task and task.proc is not None:
            try:
                task.proc.kill()
                task.proc.wait()
            except OSError:
                pass


class HarnessResolver(
    subagent_harness.HarnessResolver,
    Singleton,
):
    """Realizes harness resolution for external agent platforms."""

    tier = agent_session.agent_session

    def resolve_harness(
        self,
        platform_name: str,
        model_name: Optional[str] = None,
        timeout_seconds: float = 600.0,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
    ) -> subagent_coordinator.HarnessAdapter:
        """Resolves a harness adapter for a platform name or custom command template."""
        if simulation_mode or platform_name.lower() == "simulation":
            return CommandHarnessAdapter(
                cmd_template="simulation",
                timeout_seconds=timeout_seconds,
                model_name=model_name,
                simulation_mode=True,
            )

        if custom_cmd:
            return CommandHarnessAdapter(
                cmd_template=custom_cmd,
                timeout_seconds=timeout_seconds,
                model_name=model_name,
                simulation_mode=simulation_mode,
            )

        plat_key = platform_name.lower()
        template = PLATFORM_TEMPLATES.get(plat_key)
        if template is None:
            avail = ", ".join(sorted(PLATFORM_TEMPLATES.keys()))
            raise ValueError(
                f"Unknown platform '{platform_name}'. Available platforms: {avail}"
            )

        return CommandHarnessAdapter(
            cmd_template=template,
            timeout_seconds=timeout_seconds,
            model_name=model_name,
            simulation_mode=simulation_mode,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        HarnessResolver,
        keys=[subagent_harness.HarnessResolver, HarnessResolver],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
