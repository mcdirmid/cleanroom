"""Low-level implementation for dsh_harness_impl."""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.subagent.lib import subagent_coordinator, subagent_harness
from update_with_ai.parts.workspace_cli.lib import work
from update_with_ai.parts.workspace.lib import role_registry
from . import dsh_harness, dsh_telemetry, dsh_workspace


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
            res_any = data.get("targets") or data.get("blamed_targets") or []
            return [str(x) for x in res_any]
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        pass
    return []


def _discover_cleanroom_logs(workspace_dir: str) -> List[str]:
    """Discovers root and scoped .cleanroom.log files in a workspace directory."""
    logs: List[str] = []
    root_log = os.path.join(workspace_dir, ".cleanroom.log")
    if os.path.isfile(root_log):
        logs.append(root_log)
    if os.path.isdir(workspace_dir):
        for root, dirs, files in os.walk(workspace_dir):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("venv", "node_modules", "bazel-bin", "bazel-out", "bazel-testlogs")
            ]
            for f in files:
                if f == ".cleanroom.log":
                    p = os.path.join(root, f)
                    if p not in logs:
                        logs.append(p)
    return logs


def _resolve_default_sessions_dir() -> str:
    """Discovers DeepSeek Harness sessions directory across environment and OS candidates."""
    if "DSH_SESSIONS_DIR" in os.environ and os.environ["DSH_SESSIONS_DIR"].strip():
        return os.environ["DSH_SESSIONS_DIR"].strip()

    dsh_home = os.environ.get("DSH_HOME")
    if dsh_home and dsh_home.strip():
        h_cand = os.path.join(dsh_home.strip(), "harness", "sessions")
        if os.path.isdir(h_cand):
            return h_cand
        s_cand = os.path.join(dsh_home.strip(), "sessions")
        if os.path.isdir(s_cand):
            return s_cand
        return h_cand

    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Library", "Application Support", "dsh-desktop", "harness", "sessions"),
        os.path.join(home, ".config", "dsh-desktop", "harness", "sessions"),
        os.path.join(home, ".local", "share", "dsh-desktop", "harness", "sessions"),
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(os.path.join(appdata, "dsh-desktop", "harness", "sessions"))

    for cand in candidates:
        if os.path.isdir(cand):
            return cand

    # Platform default fallback
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "dsh-desktop", "harness", "sessions")
    elif sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA", home), "dsh-desktop", "harness", "sessions")
    return os.path.join(home, ".config", "dsh-desktop", "harness", "sessions")


@dataclass
class _ActiveDshTask:
    handle: str
    dispatch: subagent_coordinator.RoleDispatch
    process: Optional[subprocess.Popen[Any]]
    pending_before: Sequence[str]
    start_time: float
    prompt_file: str
    log_file: str
    is_rpc: bool = False
    rpc_handle: Optional[str] = None
    had_disk_pending: bool = False


# Contract: Realizes subagent execution in DeepSeek Harness role workspaces conforming to dsh_ext.
class DshHarnessAdapter(dsh_harness.DshHarnessAdapter):
    """Realizes subagent execution in DeepSeek Harness role workspaces."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        simulation_mode: bool = False,
        parser: Optional[dsh_telemetry.DshTelemetryParser] = None,
    ) -> None:
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._max_context_tokens = max_context_tokens
        self._custom_cmd = custom_cmd
        self._sessions_dir = sessions_dir or _resolve_default_sessions_dir()
        self._simulation_mode = simulation_mode
        self._parser = parser
        self._tasks: Dict[str, _ActiveDshTask] = {}
        self._session_baselines: Dict[str, dsh_telemetry.DshSessionTokenMetrics] = {}

    @property
    def _telemetry_parser(self) -> dsh_telemetry.DshTelemetryParser:
        if self._parser is not None:
            return self._parser
        try:
            return get_singleton(dsh_telemetry.DshTelemetryParser)
        except Exception:
            from . import dsh_asm
            dsh_asm.__initialize__()
            return get_singleton(dsh_telemetry.DshTelemetryParser)

    def _format_task_prompt(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        role_label = dispatch.role_name
        try:
            reg = get_singleton(role_registry.WorkspaceRegistry)
            r_def = reg.resolve_role_definition(dispatch.role_name, dir_scope=dispatch.dir_scope)
            if not r_def.writable_file_patterns:
                role_label = f"{dispatch.role_name} (Auditor)"
        except Exception:
            pass

        reminder_section = (
            f"\n## Coordinator Directive / Action Required\n{dispatch.task_prompt}\n"
            if dispatch.task_prompt
            else ""
        )

        return (
            f"# Cleanroom Role Dispatch\n"
            f"Role: {role_label}\n"
            f"Scope: {dispatch.dir_scope}\n"
            f"Workspace: {dispatch.workspace_dir}\n\n"
            f"CRITICAL DIRECTIVES:\n"
            f"1. Read `AGENTS.md` in your workspace root first for your role instructions, boundary constraints, and workflow directives.\n"
            f"2. Run `bin/get_work` to acquire your assigned pending targets, contract files, companion guide, and actionable next steps.\n"
            f"{reminder_section}"
        )

    # Contract: Dispatches work directive to a DeepSeek Harness role workspace.
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace."""
        task_handle = f"dsh_{dispatch.role_name}_{int(time.time() * 1000)}"
        work_mgr = get_singleton(work.WorkspaceWorkManager)
        disk_pending = tuple(work_mgr.get_pending_work(dispatch.workspace_dir))
        pending_before = disk_pending or tuple(dispatch.ready_targets)
        had_disk_pending = bool(disk_pending)

        log_dir = subagent_coordinator.resolve_cleanroom_log_dir(dispatch.workspace_dir)
        prompt_text = self._format_task_prompt(dispatch)
        prompt_file = os.path.join(log_dir, f".dsh_prompt_{task_handle}.md")
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt_text)

        log_path = os.path.join(log_dir, f".cleanroom_round_{task_handle}.log")

        # Ensure Cordis overlay patch exists
        patch_file = os.path.join(dispatch.workspace_dir, ".cleanroom", "dsh_patch.yml")
        if not os.path.isfile(patch_file) or self._model_name is not None:
            try:
                ws_cfg = get_singleton(dsh_workspace.DshWorkspaceConfigurer)
                ws_cfg.configure_role_workspace(
                    workspace_dir=dispatch.workspace_dir,
                    role_name=dispatch.role_name,
                    model_name=self._model_name,
                )
            except Exception:
                pass

        if self._simulation_mode:
            proc = None
        else:
            server_available = self._telemetry_parser.is_desktop_server_available(self._sessions_dir)
            if server_available:
                session_file = os.path.join(dispatch.workspace_dir, ".cleanroom", "dsh_session_id.txt")
                saved_sid: Optional[str] = None
                if os.path.isfile(session_file):
                    try:
                        with open(session_file, "r", encoding="utf-8") as sf:
                            saved_sid = sf.read().strip() or None
                    except OSError:
                        pass

                # Retry up to 3 times with backoff on transient connection failures when desktop server is available
                rpc_handle = None
                for attempt in range(3):
                    rpc_handle = self._telemetry_parser.dispatch_turn_rpc(
                        workspace_dir=dispatch.workspace_dir,
                        role_name=dispatch.role_name,
                        prompt_text=prompt_text,
                        session_id=saved_sid,
                        sessions_dir=self._sessions_dir,
                        model_name=self._model_name,
                    )
                    if rpc_handle:
                        break
                    if attempt < 2:
                        time.sleep(1.0 * (attempt + 1))

                if rpc_handle:
                    if rpc_handle.startswith("dsh_rpc::"):
                        parts = rpc_handle.split("::")
                        if len(parts) >= 2 and parts[1]:
                            os.makedirs(os.path.dirname(session_file), exist_ok=True)
                            try:
                                with open(session_file, "w", encoding="utf-8") as sf:
                                    sf.write(parts[1])
                            except OSError:
                                pass

                    self._tasks[task_handle] = _ActiveDshTask(
                        handle=task_handle,
                        dispatch=dispatch,
                        process=None,
                        pending_before=pending_before,
                        start_time=time.time(),
                        prompt_file=prompt_file,
                        log_file=log_path,
                        is_rpc=True,
                        rpc_handle=rpc_handle,
                        had_disk_pending=had_disk_pending,
                    )
                    return task_handle
                else:
                    # When Desktop server is present, do NOT fall back to incompatible headless CLI runner.
                    # Desktop sessions run under standard preset, which one-shot CLI cannot compose.
                    err_msg = "DeepSeek Harness Desktop RPC is unavailable after retries (desktop server restarting or unreachable)"
                    with open(log_path, "w", encoding="utf-8") as lf:
                        lf.write(f'{{"type":"error","message":"{err_msg}"}}\n')
                    self._tasks[task_handle] = _ActiveDshTask(
                        handle=task_handle,
                        dispatch=dispatch,
                        process=None,
                        pending_before=pending_before,
                        start_time=time.time(),
                        prompt_file=prompt_file,
                        log_file=log_path,
                        is_rpc=False,
                        had_disk_pending=had_disk_pending,
                    )
                    return task_handle

            session_file = os.path.join(dispatch.workspace_dir, ".cleanroom", "dsh_session_id.txt")
            session_arg = ""
            if os.path.isfile(session_file):
                try:
                    with open(session_file, "r", encoding="utf-8") as sf:
                        saved_sid = sf.read().strip()
                    if saved_sid:
                        encoded_ws = "--" + os.path.realpath(dispatch.workspace_dir).strip("/").replace("/", "-") + "--"
                        lock_path = os.path.join(self._sessions_dir, encoded_ws, saved_sid, "session.lock")
                        is_locked = False
                        if os.path.exists(lock_path):
                            try:
                                with open(lock_path, "r+") as lf:
                                    fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                                    fcntl.flock(lf, fcntl.LOCK_UN)
                            except (BlockingIOError, OSError):
                                is_locked = True
                        if not is_locked:
                            session_arg = f'--session-id "{saved_sid}" '
                except Exception:
                    pass

            if self._custom_cmd:
                cmd = self._custom_cmd.format(
                    workspace_dir=dispatch.workspace_dir,
                    prompt_file=prompt_file,
                    task_prompt=prompt_text,
                    patch_file=patch_file,
                    role_name=dispatch.role_name,
                )
            else:
                cmd = f'cat "{prompt_file}" | dsh --patch "{patch_file}" --profile headless {session_arg}--json -'

            log_f = open(log_path, "w", encoding="utf-8")
            env = os.environ.copy()
            env["DSH_HOME"] = os.environ.get("DSH_HOME") or os.path.dirname(self._sessions_dir)
            env["DSH_PERMISSION_MODE"] = "danger-full-access"

            proc = subprocess.Popen(
                cmd,
                shell=True,
                cwd=dispatch.workspace_dir,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                env=env,
            )

            # Sync desktop session immediately so the new session is placed under its workspace in the UI
            if self._sessions_dir:
                try:
                    time.sleep(0.3)
                    self._telemetry_parser.sync_desktop_session(
                        sessions_dir=self._sessions_dir,
                        workspace_dir=dispatch.workspace_dir,
                        role_name=dispatch.role_name,
                        dir_scope=dispatch.dir_scope,
                        start_time=time.time(),
                    )
                except Exception:
                    pass

        self._tasks[task_handle] = _ActiveDshTask(
            handle=task_handle,
            dispatch=dispatch,
            process=proc,
            pending_before=pending_before,
            start_time=time.time(),
            prompt_file=prompt_file,
            log_file=log_path,
            had_disk_pending=had_disk_pending,
        )
        return task_handle

    def _finalize_round(
        self,
        task: _ActiveDshTask,
        rpc_status: Optional[dsh_telemetry.DshRpcRoundStatus] = None,
    ) -> subagent_coordinator.RoleRoundResult:
        wall_clock = time.time() - task.start_time

        if rpc_status and rpc_status.error:
            session_file = os.path.join(task.dispatch.workspace_dir, ".cleanroom", "dsh_session_id.txt")
            if os.path.isfile(session_file):
                try:
                    os.remove(session_file)
                except OSError:
                    pass
            self._session_baselines.pop(task.dispatch.workspace_dir, None)
            if task.is_rpc and task.rpc_handle and task.rpc_handle.startswith("dsh_rpc::"):
                parts = task.rpc_handle.split("::")
                if len(parts) >= 2 and parts[1]:
                    self._session_baselines.pop(parts[1], None)
            return subagent_coordinator.RoleRoundResult(
                role=task.dispatch.role_name,
                status="failed",
                failure_reason=rpc_status.error,
                wall_clock_seconds=wall_clock,
            )

        log_file = task.log_file
        if not os.path.isfile(log_file):
            alt_log = log_file.replace(".cleanroom_round_", ".cleanroom_turn_")
            if os.path.isfile(alt_log):
                log_file = alt_log

        cand_logs: List[str] = [log_file] if os.path.isfile(log_file) else []
        for cl in _discover_cleanroom_logs(task.dispatch.workspace_dir):
            if cl not in cand_logs:
                cand_logs.append(cl)

        blamed = list(_read_blame_buffer(task.dispatch.workspace_dir))
        for cand_log in cand_logs:
            if os.path.isfile(cand_log):
                try:
                    with open(cand_log, "r", encoding="utf-8", errors="replace") as lf:
                        for line in lf:
                            m = re.search(r"\[BLAME\]\s*([^\r\n]+?)(?::\s+|$)", line)
                            if m:
                                culprit = m.group(1).strip()
                                if culprit and culprit not in blamed:
                                    blamed.append(culprit)
                except OSError:
                    pass

        pending_file = os.path.join(task.dispatch.workspace_dir, ".cleanroom_pending_work.json")
        has_pending_file_after = os.path.isfile(pending_file)

        work_mgr = get_singleton(work.WorkspaceWorkManager)
        pending_after = work_mgr.get_pending_work(task.dispatch.workspace_dir)
        submitted_list: List[str] = []

        if task.pending_before and (has_pending_file_after or task.had_disk_pending):
            submitted_list = [t for t in task.pending_before if t not in pending_after]

        for cand_log in cand_logs:
            if os.path.isfile(cand_log):
                try:
                    with open(cand_log, "r", encoding="utf-8", errors="replace") as lf:
                        for line in lf:
                            for pfx in (
                                r"\[SUBMITTED\]\s*([^\r\n]+?)(?::\s+|$)",
                                r"\[AUDIT\]\s*([^\r\n]+?)(?::\s+|$)",
                                r"\[CHANGE\]\s*([^\r\n]+?)(?::\s+|$)",
                                r"\[CLEAN\]\s*([^\r\n]+?)(?::\s+|$)",
                            ):
                                m = re.search(pfx, line)
                                if m:
                                    target = m.group(1).strip()
                                    if target and target not in submitted_list:
                                        submitted_list.append(target)
                except OSError:
                    pass
        submitted = tuple(submitted_list)

        if blamed:
            status = "blamed"
        elif submitted:
            status = "clean"
        else:
            status = "unresolved"

        # Resolve session identifier
        session_file = os.path.join(task.dispatch.workspace_dir, ".cleanroom", "dsh_session_id.txt")
        session_id: Optional[str] = None
        if task.is_rpc and task.rpc_handle and task.rpc_handle.startswith("dsh_rpc::"):
            parts = task.rpc_handle.split("::")
            if len(parts) >= 2 and parts[1]:
                session_id = parts[1]
        elif os.path.isfile(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as sf:
                    session_id = sf.read().strip() or None
            except OSError:
                pass

        if not session_id and os.path.isfile(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as lf:
                    for line in lf:
                        line_str = line.strip()
                        if line_str.startswith("{"):
                            ev = json.loads(line_str)
                            sid = ev.get("sessionId")
                            if sid:
                                session_id = sid
                                break
            except Exception:
                pass

        # Telemetry parsing
        metrics = dsh_telemetry.DshSessionTokenMetrics()
        if rpc_status and rpc_status.metrics:
            metrics = rpc_status.metrics
        elif os.path.isfile(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as lf:
                    log_text = lf.read()
                metrics = self._telemetry_parser.parse_stream_text(stream_text=log_text, model_name=self._model_name)
            except OSError:
                pass

        if metrics.total_tokens == 0 and self._sessions_dir and os.path.isdir(self._sessions_dir):
            metrics = self._telemetry_parser.parse_session_storage(
                sessions_dir=self._sessions_dir,
                workspace_dir=task.dispatch.workspace_dir,
                model_name=self._model_name,
            )

        # Calculate incremental round token delta against session baseline
        sess_key = session_id or task.dispatch.workspace_dir
        prev_baseline = self._session_baselines.get(sess_key)
        if prev_baseline is None and session_id:
            prev_baseline = self._session_baselines.get(task.dispatch.workspace_dir)

        if prev_baseline is not None and metrics.total_tokens >= prev_baseline.total_tokens:
            delta_input = max(0, metrics.input_tokens - prev_baseline.input_tokens)
            delta_cached = max(0, metrics.cached_tokens - prev_baseline.cached_tokens)
            delta_output = max(0, metrics.output_tokens - prev_baseline.output_tokens)
            delta_total = delta_input + delta_cached + delta_output
            delta_cost = max(0.0, metrics.cost_usd - prev_baseline.cost_usd)
        else:
            delta_input = metrics.input_tokens
            delta_cached = metrics.cached_tokens
            delta_output = metrics.output_tokens
            delta_total = metrics.total_tokens
            delta_cost = metrics.cost_usd

        token_usage = subagent_coordinator.TokenUsage(
            input_tokens=delta_input,
            cached_tokens=delta_cached,
            output_tokens=delta_output,
            total_tokens=delta_total,
            cost_usd=delta_cost,
        )

        if status == "failed":
            # Reset session ID on failed rounds to prevent context contamination loops
            if os.path.isfile(session_file):
                try:
                    os.remove(session_file)
                except OSError:
                    pass
            self._session_baselines.pop(sess_key, None)
            if session_id:
                self._session_baselines.pop(session_id, None)
            self._session_baselines.pop(task.dispatch.workspace_dir, None)
        else:
            if session_id and not os.path.isfile(session_file):
                try:
                    os.makedirs(os.path.dirname(session_file), exist_ok=True)
                    with open(session_file, "w", encoding="utf-8") as sf:
                        sf.write(session_id)
                except OSError:
                    pass
            if metrics.total_tokens > 0:
                self._session_baselines[sess_key] = metrics
                if session_id:
                    self._session_baselines[session_id] = metrics
                self._session_baselines[task.dispatch.workspace_dir] = metrics

        if not self._simulation_mode:
            self._telemetry_parser.sync_desktop_session(
                sessions_dir=self._sessions_dir,
                workspace_dir=task.dispatch.workspace_dir,
                role_name=task.dispatch.role_name,
                dir_scope=task.dispatch.dir_scope,
                start_time=task.start_time,
            )

        return subagent_coordinator.RoleRoundResult(
            role=task.dispatch.role_name,
            status=status,
            submitted_targets=submitted,
            blamed_targets=tuple(blamed),
            telemetry=token_usage,
            wall_clock_seconds=wall_clock,
        )

    # Backward compatibility alias
    _finalize_turn = _finalize_round

    # Contract: MUST await round completion, compute buffer differences via work, assign unresolved status when zero targets submitted/blamed, parse telemetry, and return RoleRoundResult.
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleRoundResult:
        """Awaits DeepSeek Harness subagent round completion and returns outcome result."""
        task = self._tasks.get(task_handle)
        if task is None:
            return subagent_coordinator.RoleRoundResult(
                role="",
                status="failed",
                failure_reason=f"Unknown task handle '{task_handle}'",
            )

        if task.is_rpc:
            while True:
                rpc_status = self._telemetry_parser.poll_round_rpc(task.rpc_handle or "", sessions_dir=self._sessions_dir)
                if rpc_status.is_completed:
                    return self._finalize_round(task, rpc_status=rpc_status)
                if self._timeout_seconds is not None and self._timeout_seconds > 0:
                    elapsed = time.time() - task.start_time
                    if elapsed >= self._timeout_seconds:
                        return subagent_coordinator.RoleRoundResult(
                            role=task.dispatch.role_name,
                            status="failed",
                            failure_reason="RPC round execution timed out",
                            wall_clock_seconds=elapsed,
                        )
                time.sleep(0.1)

        if task.process is not None:
            try:
                if self._timeout_seconds is not None and self._timeout_seconds > 0:
                    task.process.wait(timeout=self._timeout_seconds)
                else:
                    task.process.wait()
            except subprocess.TimeoutExpired:
                task.process.kill()
                task.process.wait()
                self._session_baselines.pop(task.dispatch.workspace_dir, None)
                return subagent_coordinator.RoleRoundResult(
                    role=task.dispatch.role_name,
                    status="failed",
                    failure_reason="Process execution timed out",
                    wall_clock_seconds=time.time() - task.start_time,
                )
            if task.process.returncode != 0:
                self._session_baselines.pop(task.dispatch.workspace_dir, None)
                return subagent_coordinator.RoleRoundResult(
                    role=task.dispatch.role_name,
                    status="failed",
                    failure_reason=f"Process exited with code {task.process.returncode}",
                    wall_clock_seconds=time.time() - task.start_time,
                )
        elif not self._simulation_mode and not task.is_rpc:
            failure_reason = "No subprocess or RPC task active"
            if os.path.isfile(task.log_file):
                try:
                    with open(task.log_file, "r", encoding="utf-8") as lf:
                        for line in lf:
                            if '"type":"error"' in line and "DeepSeek Harness Desktop RPC is unavailable" in line:
                                data = json.loads(line)
                                failure_reason = data.get("message", failure_reason)
                                self._session_baselines.pop(task.dispatch.workspace_dir, None)
                                return subagent_coordinator.RoleRoundResult(
                                    role=task.dispatch.role_name,
                                    status="failed",
                                    failure_reason=failure_reason,
                                    wall_clock_seconds=time.time() - task.start_time,
                                )
                except Exception:
                    pass

        return self._finalize_round(task, rpc_status=None)

    # Contract: MUST return role round result when terminated, or None when still running without blocking.
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
        """Polls DeepSeek Harness subagent round execution without blocking."""
        task = self._tasks.get(task_handle)
        if task is None:
            return subagent_coordinator.RoleRoundResult(
                role="",
                status="failed",
                failure_reason=f"Unknown task handle '{task_handle}'",
            )

        if self._simulation_mode:
            return self.await_role(task_handle)

        if task.is_rpc:
            rpc_status = self._telemetry_parser.poll_round_rpc(task.rpc_handle or "", sessions_dir=self._sessions_dir)
            if rpc_status.is_active:
                if self._timeout_seconds is not None and self._timeout_seconds > 0:
                    elapsed = time.time() - task.start_time
                    if elapsed >= self._timeout_seconds:
                        return subagent_coordinator.RoleRoundResult(
                            role=task.dispatch.role_name,
                            status="failed",
                            failure_reason="RPC round execution timed out",
                            wall_clock_seconds=elapsed,
                        )
                return None
            return self._finalize_round(task, rpc_status=rpc_status)

        if task.process is None:
            return self.await_role(task_handle)

        poll_res = task.process.poll()
        if poll_res is None:
            if self._timeout_seconds is not None and self._timeout_seconds > 0:
                elapsed = time.time() - task.start_time
                if elapsed >= self._timeout_seconds:
                    return self.await_role(task_handle)
            if not self._simulation_mode and self._sessions_dir:
                try:
                    self._telemetry_parser.sync_desktop_session(
                        sessions_dir=self._sessions_dir,
                        workspace_dir=task.dispatch.workspace_dir,
                        role_name=task.dispatch.role_name,
                        dir_scope=task.dispatch.dir_scope,
                        start_time=task.start_time,
                    )
                except Exception:
                    pass
            return None

        return self.await_role(task_handle)

    # Contract: MUST terminate active DeepSeek Harness subagent process associated with task handle.
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active DeepSeek Harness subagent task execution upon timeout or limit."""
        task = self._tasks.get(task_handle)
        if task and task.process:
            try:
                task.process.kill()
            except OSError:
                pass


# Contract: Realizes management of DeepSeek Harness execution adapters and telemetry parsing in agent_session tier.
class DshHarnessManager(dsh_harness.DshHarnessManager):
    """Realizes management of DeepSeek Harness execution adapters and telemetry parsing."""

    tier = agent_session.agent_session

    # Contract: MUST install DeepSeek Harness adapter factory into subagent harness registry under 'dsh'.
    def initialize(self) -> None:
        """Initializes the manager and installs the adapter factory into the harness registry."""
        try:
            registry = get_singleton(subagent_harness.HarnessRegistry)
            registry.install_harness("dsh", self.create_harness_adapter)
        except Exception:
            pass

    # Contract: MUST construct and return configured DeepSeek Harness adapter instance.
    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
        sessions_dir: Optional[str] = None,
        **kwargs: Any,
    ) -> dsh_harness.DshHarnessAdapter:
        """Constructs a DeepSeek Harness adapter instance."""
        return DshHarnessAdapter(
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            max_context_tokens=max_context_tokens,
            custom_cmd=custom_cmd,
            sessions_dir=sessions_dir,
            simulation_mode=simulation_mode,
            parser=self.get_telemetry_parser(),
        )

    # Contract: MUST return DeepSeek Harness telemetry parser instance.
    def get_telemetry_parser(self) -> dsh_telemetry.DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service."""
        try:
            return get_singleton(dsh_telemetry.DshTelemetryParser)
        except Exception:
            from . import dsh_asm
            dsh_asm.__initialize__()
            return get_singleton(dsh_telemetry.DshTelemetryParser)
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-18T19:13:51Z
# LAST_CHANGED: 2026-10-20T23:55:00Z
# CHANGE: Derive pending_before from ready targets or disk, search scoped cleanroom logs, and match change and clean action records
# COVERAGE_AUDIT: 2026-10-18T19:13:51Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DshHarnessManager,
        keys=[dsh_harness.DshHarnessManager, DshHarnessManager],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
