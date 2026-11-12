"""Low-level implementation for dsh_harness_impl."""

from __future__ import annotations

from dataclasses import dataclass, field
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from support.lib.lifecycle import auto_initialize, get_singleton, singleton
from autofab.parts.agent.lib import session as agent_session
from autofab.parts.subagent.lib import subagent_coordinator, subagent_harness
from autofab.parts.workspace_cli.lib import work
from autofab.parts.workspace.lib import role_registry

try:
    from support.lib import app_info
except ImportError:
    import app_info  # type: ignore
from . import dsh_harness, dsh_telemetry, dsh_workspace

try:
    from . import dsh_telemetry_impl
except ImportError:
    from autofab.parts.dsh.lib import dsh_telemetry_impl


def _read_blame_buffer(workspace_dir: str) -> List[str]:
    """Reads blamed culprit files from the workspace blame buffer."""
    candidate_names = (app_info.DEFAULT_BLAME_BUFFER_FILE,)
    for cand in candidate_names:
        p = os.path.join(workspace_dir, cand)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                res: List[str] = []
                for item in data:
                    if isinstance(item, str):
                        res.append(item)
                    elif isinstance(item, dict):
                        t = (
                            item.get("culprit_target")
                            or item.get("target")
                            or item.get("file")
                        )
                        if t:
                            res.append(str(t))
                if res:
                    return res
            elif isinstance(data, dict):
                res_any = data.get("targets") or data.get("blamed_targets") or []
                if res_any:
                    return [str(x) for x in res_any]
        except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass
    return []


def _discover_logs(workspace_dir: str) -> List[str]:
    """Discovers root and scoped log files in a workspace directory."""
    logs: List[str] = []
    log_filenames = app_info.get_log_filenames()
    for log_name in log_filenames:
        root_log = os.path.join(workspace_dir, log_name)
        if os.path.isfile(root_log) and root_log not in logs:
            logs.append(root_log)
    if os.path.isdir(workspace_dir):
        for root, dirs, files in os.walk(workspace_dir):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d
                not in (
                    "venv",
                    "node_modules",
                    "bazel-bin",
                    "bazel-out",
                    "bazel-testlogs",
                )
            ]
            for f in files:
                if f in log_filenames:
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
        s_cand = os.path.join(dsh_home.strip(), "sessions")
        if os.path.isdir(s_cand):
            return s_cand
        h_cand = os.path.join(dsh_home.strip(), "harness", "sessions")
        if os.path.isdir(h_cand):
            return h_cand
        return s_cand

    home = os.path.expanduser("~")
    return os.path.join(home, ".dsh", "sessions")


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
    is_interrupted: bool = False
    log_offsets: Dict[str, int] = field(default_factory=dict)


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
        max_rounds_per_worker: int = 8,
    ) -> None:
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._max_context_tokens = max_context_tokens
        self._custom_cmd = custom_cmd
        self._sessions_dir = sessions_dir or _resolve_default_sessions_dir()
        self._simulation_mode = simulation_mode
        self._parser = parser
        self._max_rounds_per_worker = max_rounds_per_worker
        self._tasks: Dict[str, _ActiveDshTask] = {}
        self._session_baselines: Dict[str, dsh_telemetry.DshSessionTokenMetrics] = {}
        self._worker_round_counts: Dict[str, int] = {}
        self._active_role_sessions: Dict[Tuple[str, str], str] = {}
        self._dead_role_sessions: Dict[str, List[Dict[str, Any]]] = {}

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
        lines = [
            "1. Read `AGENTS.md` if not already in context.",
            "2. Run `bin/get_work`.",
        ]
        if dispatch.task_prompt:
            lines.extend(["", f"Directive:\n{dispatch.task_prompt}"])
        return "\n".join(lines) + "\n"

    # Contract: Dispatches work directive to a DeepSeek Harness role workspace.
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace."""
        try:
            from autofab.parts.workspace.lib import provision
            prov = get_singleton(provision.WorkspaceProvisioner)
            prov.lock_workspace_directories(
                dispatch.workspace_dir,
                role_name=dispatch.role_name,
                dir_scope=dispatch.dir_scope,
            )
        except Exception:
            pass

        task_handle = f"dsh_{dispatch.role_name}_{int(time.time() * 1000)}"
        work_mgr = get_singleton(work.WorkspaceWorkManager)
        disk_pending = tuple(work_mgr.get_pending_work(dispatch.workspace_dir))
        pending_before = disk_pending or tuple(dispatch.ready_targets)
        had_disk_pending = bool(disk_pending)

        log_offsets: Dict[str, int] = {}
        for cl in _discover_logs(dispatch.workspace_dir):
            if os.path.isfile(cl):
                try:
                    log_offsets[cl] = os.path.getsize(cl)
                except OSError:
                    pass

        log_dir = subagent_coordinator.resolve_log_dir(dispatch.workspace_dir)
        prompt_text = self._format_task_prompt(dispatch)
        prompt_file = os.path.join(log_dir, f".dsh_prompt_{task_handle}.md")
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt_text)

        log_path = os.path.join(
            log_dir, f".{app_info.APP_NAME}_round_{task_handle}.log"
        )

        # Ensure Cordis overlay patch exists
        patch_file = os.path.join(
            app_info.resolve_state_dir(dispatch.workspace_dir), "dsh_patch.yml"
        )
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
            server_available = self._telemetry_parser.is_server_available(
                self._sessions_dir
            )
            if not server_available:
                if self._custom_cmd:
                    cmd = self._custom_cmd.format(
                        workspace_dir=dispatch.workspace_dir,
                        prompt_file=prompt_file,
                        task_prompt=prompt_text,
                        patch_file=patch_file,
                        role_name=dispatch.role_name,
                    )
                    log_f = open(log_path, "w", encoding="utf-8")
                    env = os.environ.copy()
                    env["DSH_HOME"] = os.environ.get("DSH_HOME") or os.path.dirname(
                        self._sessions_dir
                    )
                    env["DSH_PERMISSION_MODE"] = "danger-full-access"
                    proc = subprocess.Popen(
                        cmd,
                        shell=True,
                        cwd=dispatch.workspace_dir,
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        env=env,
                    )
                    self._tasks[task_handle] = _ActiveDshTask(
                        handle=task_handle,
                        dispatch=dispatch,
                        process=proc,
                        pending_before=pending_before,
                        start_time=time.time(),
                        prompt_file=prompt_file,
                        log_file=log_path,
                        had_disk_pending=had_disk_pending,
                        log_offsets=log_offsets,
                    )
                    return task_handle
                else:
                    err_msg = (
                        "DeepSeek Harness server is unreachable (DSH Web bridge is not available). "
                        "Headless execution is strictly banned."
                    )
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
                        log_offsets=log_offsets,
                    )
                    return task_handle

            session_file = os.path.join(
                app_info.resolve_state_dir(dispatch.workspace_dir), "dsh_session_id.txt"
            )
            saved_sid: Optional[str] = None
            if os.path.isfile(session_file):
                try:
                    with open(session_file, "r", encoding="utf-8") as sf:
                        saved_sid = sf.read().strip() or None
                except OSError:
                    pass

            # Retry up to 3 times with backoff on transient connection failures when server is available
            rpc_handle = None
            for attempt in range(3):
                rpc_handle = self._telemetry_parser.dispatch_turn_rpc(
                    workspace_dir=dispatch.workspace_dir,
                    role_name=dispatch.role_name,
                    prompt_text=prompt_text,
                    session_id=saved_sid,
                    sessions_dir=self._sessions_dir,
                    model_name=self._model_name,
                    dir_scope=dispatch.dir_scope,
                )
                if rpc_handle:
                    break
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))

            if not rpc_handle:
                err_msg = (
                    "DeepSeek Harness Web RPC is unavailable after retries (server restarting or unreachable). "
                    "Headless execution is strictly banned."
                )
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
                    log_offsets=log_offsets,
                )
                return task_handle

            if rpc_handle.startswith(("dsh_rpc::", "dsh_rpc_web::")):
                parts = rpc_handle.split("::")
                if len(parts) >= 2 and parts[1]:
                    new_session_id = parts[1]
                    clean_scope = (
                        dispatch.dir_scope.strip("/").strip()
                        if dispatch.dir_scope
                        else ""
                    )
                    display_scope = os.path.basename(clean_scope) if clean_scope else ""
                    role = dispatch.role_name.strip() if dispatch.role_name else ""
                    role_key = (clean_scope, role)
                    prev_session_id = (
                        self._active_role_sessions.get(role_key)
                        or self._active_role_sessions.get((display_scope, role))
                        or saved_sid
                    )
                    if prev_session_id and prev_session_id != new_session_id:
                        dead_title = (
                            f"[{display_scope}] dead - {role}"
                            if display_scope
                            else (f"dead - {role}" if role else "dead")
                        )
                        try:
                            self._telemetry_parser.rename_session(
                                prev_session_id,
                                dead_title,
                                sessions_dir=self._sessions_dir,
                            )
                        except Exception:
                            pass
                        dead_entry = {
                            "sessionId": prev_session_id,
                            "role": role,
                            "reason": "superseded",
                        }
                        for sc in {clean_scope, display_scope}:
                            if sc:
                                dead_list = self._dead_role_sessions.setdefault(sc, [])
                                if not any(
                                    d.get("sessionId") == prev_session_id for d in dead_list
                                ):
                                    dead_list.append(dead_entry)
                    self._active_role_sessions[role_key] = new_session_id
                    if display_scope:
                        self._active_role_sessions[(display_scope, role)] = new_session_id
                    os.makedirs(os.path.dirname(session_file), exist_ok=True)
                    try:
                        with open(session_file, "w", encoding="utf-8") as sf:
                            sf.write(new_session_id)
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

        self._tasks[task_handle] = _ActiveDshTask(
            handle=task_handle,
            dispatch=dispatch,
            process=proc,
            pending_before=pending_before,
            start_time=time.time(),
            prompt_file=prompt_file,
            log_file=log_path,
            had_disk_pending=had_disk_pending,
            log_offsets=log_offsets,
        )
        return task_handle

    def _unlock_task_workspace(self, task: Optional[_ActiveDshTask]) -> None:
        if task is None:
            return
        try:
            from autofab.parts.workspace.lib import provision
            prov = get_singleton(provision.WorkspaceProvisioner)
            prov.unlock_workspace_directories(task.dispatch.workspace_dir)
        except Exception:
            pass

    def _finalize_round(
        self,
        task: _ActiveDshTask,
        rpc_status: Optional[dsh_telemetry.DshRpcRoundStatus] = None,
    ) -> subagent_coordinator.RoleRoundResult:
        wall_clock = time.time() - task.start_time

        if rpc_status and rpc_status.error:
            session_file = os.path.join(
                app_info.resolve_state_dir(task.dispatch.workspace_dir, create=False),
                "dsh_session_id.txt",
            )
            if os.path.isfile(session_file):
                try:
                    os.remove(session_file)
                except OSError:
                    pass
            self._session_baselines.pop(task.dispatch.workspace_dir, None)
            if (
                task.is_rpc
                and task.rpc_handle
                and task.rpc_handle.startswith(("dsh_rpc::", "dsh_rpc_web::"))
            ):
                parts = task.rpc_handle.split("::")
                if len(parts) >= 2 and parts[1]:
                    self._session_baselines.pop(parts[1], None)
            self._worker_round_counts[task.dispatch.workspace_dir] = 0
            self._unlock_task_workspace(task)
            return subagent_coordinator.RoleRoundResult(
                role=task.dispatch.role_name,
                status="failed",
                failure_reason=rpc_status.error,
                wall_clock_seconds=wall_clock,
            )

        if not self._simulation_mode and not task.is_rpc and task.process is None:
            failure_reason = "DeepSeek Harness server is unreachable. Headless execution is strictly banned."
            if os.path.isfile(task.log_file):
                try:
                    with open(
                        task.log_file, "r", encoding="utf-8", errors="replace"
                    ) as lf:
                        for line in lf:
                            line_str = line.strip()
                            if line_str.startswith("{"):
                                ev = json.loads(line_str)
                                if ev.get("type") == "error":
                                    failure_reason = ev.get("message", failure_reason)
                                    break
                except Exception:
                    pass
            self._unlock_task_workspace(task)
            return subagent_coordinator.RoleRoundResult(
                role=task.dispatch.role_name,
                status="failed",
                failure_reason=failure_reason,
                wall_clock_seconds=wall_clock,
            )

        log_file = task.log_file
        if not os.path.isfile(log_file):
            alt_log = log_file.replace(
                f".{app_info.APP_NAME}_round_", f".{app_info.APP_NAME}_step_"
            )
            if os.path.isfile(alt_log):
                log_file = alt_log

        cand_logs: List[str] = [log_file] if os.path.isfile(log_file) else []
        for cl in _discover_logs(task.dispatch.workspace_dir):
            if cl not in cand_logs:
                cand_logs.append(cl)

        blamed = list(_read_blame_buffer(task.dispatch.workspace_dir))
        for cand in (app_info.DEFAULT_BLAME_BUFFER_FILE,):
            p = os.path.join(task.dispatch.workspace_dir, cand)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        for cand_log in cand_logs:
            if os.path.isfile(cand_log):
                try:
                    with open(cand_log, "r", encoding="utf-8", errors="replace") as lf:
                        offset = task.log_offsets.get(cand_log, 0)
                        if offset > 0:
                            lf.seek(offset)
                        for line in lf:
                            m = re.search(r"\[BLAME\]\s*([^\r\n]+?)(?::\s+|$)", line)
                            if m:
                                culprit = m.group(1).strip()
                                if culprit and culprit not in blamed:
                                    blamed.append(culprit)
                except OSError:
                    pass

        pending_file = os.path.join(
            task.dispatch.workspace_dir, app_info.DEFAULT_PENDING_WORK_FILE
        )
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
                        offset = task.log_offsets.get(cand_log, 0)
                        if offset > 0:
                            lf.seek(offset)
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
        elif submitted and not task.is_interrupted:
            status = "clean"
        else:
            status = "unresolved"

        # Resolve session identifier
        session_file = os.path.join(
            app_info.resolve_state_dir(task.dispatch.workspace_dir, create=False),
            "dsh_session_id.txt",
        )
        session_id: Optional[str] = None
        if (
            task.is_rpc
            and task.rpc_handle
            and task.rpc_handle.startswith(("dsh_rpc::", "dsh_rpc_web::"))
        ):
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
                metrics = self._telemetry_parser.parse_stream_text(
                    stream_text=log_text, model_name=self._model_name
                )
            except OSError:
                pass

        if (
            metrics.total_tokens == 0
            and self._sessions_dir
            and os.path.isdir(self._sessions_dir)
        ):
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

        if (
            prev_baseline is not None
            and metrics.total_tokens >= prev_baseline.total_tokens
        ):
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

        ws_key = task.dispatch.workspace_dir
        cur_rounds = self._worker_round_counts.get(ws_key, 0) + 1

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
            self._worker_round_counts[ws_key] = 0
        elif cur_rounds >= self._max_rounds_per_worker:
            # Recycle session after N completed rounds for a clean slate
            if os.path.isfile(session_file):
                try:
                    os.remove(session_file)
                except OSError:
                    pass
            self._session_baselines.pop(sess_key, None)
            if session_id:
                self._session_baselines.pop(session_id, None)
            self._session_baselines.pop(task.dispatch.workspace_dir, None)
            self._worker_round_counts[ws_key] = 0
            print(
                f"[DSH Harness] Worker '{task.dispatch.role_name}' completed {cur_rounds} rounds. "
                f"Recycling session for a clean slate on next dispatch.",
                flush=True,
            )
        else:
            self._worker_round_counts[ws_key] = cur_rounds
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

        self._unlock_task_workspace(task)

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

        try:
            if task.is_rpc:
                while True:
                    rpc_status = self._telemetry_parser.poll_round_rpc(
                        task.rpc_handle or "", sessions_dir=self._sessions_dir
                    )
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
                                if (
                                    '"type":"error"' in line
                                    and "DeepSeek Harness Desktop RPC is unavailable"
                                    in line
                                ):
                                    data = json.loads(line)
                                    failure_reason = data.get("message", failure_reason)
                                    self._session_baselines.pop(
                                        task.dispatch.workspace_dir, None
                                    )
                                    return subagent_coordinator.RoleRoundResult(
                                        role=task.dispatch.role_name,
                                        status="failed",
                                        failure_reason=failure_reason,
                                        wall_clock_seconds=time.time() - task.start_time,
                                    )
                    except Exception:
                        pass

            return self._finalize_round(task, rpc_status=None)
        finally:
            self._unlock_task_workspace(task)

    # Contract: MUST return role round result when terminated, or None when still running without blocking.
    def poll_role(
        self, task_handle: str
    ) -> Optional[subagent_coordinator.RoleRoundResult]:
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

        if task.is_interrupted:
            return self._finalize_round(task, rpc_status=None)

        if task.is_rpc:
            rpc_status = self._telemetry_parser.poll_round_rpc(
                task.rpc_handle or "", sessions_dir=self._sessions_dir
            )
            if rpc_status.is_active:
                if self._timeout_seconds is not None and self._timeout_seconds > 0:
                    elapsed = time.time() - task.start_time
                    if elapsed >= self._timeout_seconds:
                        self._unlock_task_workspace(task)
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
            return None

        return self.await_role(task_handle)

    # Contract: MUST terminate active DeepSeek Harness subagent process associated with task handle.
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active DeepSeek Harness subagent task execution upon timeout or limit."""
        task = self._tasks.get(task_handle)
        if not task:
            return
        task.is_interrupted = True
        if task.process:
            try:
                task.process.kill()
            except OSError:
                pass
        if task.is_rpc and task.rpc_handle:
            try:
                if task.rpc_handle.startswith(("dsh_web::", "dsh_rpc_web::")):
                    parts = task.rpc_handle.split("::")
                    actual_sid = parts[1] if len(parts) >= 2 else ""
                    task_name = parts[2] if len(parts) >= 3 else actual_sid
                    bridge = dsh_telemetry_impl._discover_web_bridge()
                    if bridge:
                        dsh_telemetry_impl._call_web_bridge(
                            bridge, "dsh_close", {"worker": task_name}, timeout=2.0
                        )
            except Exception:
                pass

    # Contract: MUST persist authoritative orchestration state snapshot capturing active scopes, running workers with session IDs, and dead sessions to external coordination storage.
    def update_orchestration_state(
        self,
        dir_scope: str,
        wave_count: int,
        active_workers: Mapping[str, str],
        assigned_targets: Mapping[str, Sequence[str]],
        all_scope_roles: Sequence[str],
        converged: bool = False,
        failed: bool = False,
    ) -> None:
        """Persists authoritative orchestration state snapshot to external coordination storage."""
        clean_scope = dir_scope.strip("/").strip() if dir_scope else ""
        if not clean_scope:
            return
        display_scope = os.path.basename(clean_scope) if clean_scope else ""

        state_file = os.environ.get("AUTOFAB_STATE_FILE")
        if not state_file:
            dsh_home = os.environ.get("DSH_HOME") or os.path.expanduser("~/.dsh")
            state_file = os.path.join(dsh_home, "autofab_state.json")

        existing_data: Dict[str, Any] = {
            "scopes": {},
            "activeScope": display_scope,
            "updatedAt": time.time(),
        }
        if os.path.isfile(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict) and "scopes" in loaded:
                        existing_data = loaded
            except Exception:
                pass

        existing_data["activeScope"] = display_scope
        existing_data["updatedAt"] = time.time()
        scopes_map = existing_data.setdefault("scopes", {})

        scope_obj = scopes_map.setdefault(display_scope, {})
        scope_obj["scope"] = display_scope
        scope_obj["path"] = clean_scope
        scope_obj["wave"] = wave_count
        scope_obj["converged"] = converged
        scope_obj["status"] = (
            "converged" if converged else ("failed" if failed else "running")
        )

        roles_dict: Dict[str, Any] = {}
        for r_name in all_scope_roles:
            role_key = (clean_scope, r_name)
            sid = self._active_role_sessions.get(role_key) or self._active_role_sessions.get((display_scope, r_name))
            is_running = r_name in active_workers
            if not sid and not is_running:
                continue
            status = "running" if is_running else "idle"
            targets = list(assigned_targets.get(r_name, ()))
            role_entry: Dict[str, Any] = {
                "role": r_name,
                "status": status,
            }
            if sid:
                role_entry["sessionId"] = sid
            if targets:
                role_entry["targets"] = targets
            roles_dict[r_name] = role_entry
        scope_obj["roles"] = roles_dict

        dead_list = self._dead_role_sessions.get(display_scope, []) or self._dead_role_sessions.get(clean_scope, [])
        scope_obj["deadSessions"] = list(dead_list)

        if clean_scope != display_scope and clean_scope in scopes_map:
            scopes_map.pop(clean_scope, None)

        try:
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            tmp_file = f"{state_file}.tmp.{os.getpid()}"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2)
            os.replace(tmp_file, state_file)
        except Exception:
            pass


# Contract: Realizes management of DeepSeek Harness execution adapters and telemetry parsing in agent_session tier.
@singleton
class DshHarnessManager(dsh_harness.DshHarnessManager):
    """Realizes management of DeepSeek Harness execution adapters and telemetry parsing."""


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
            max_rounds_per_worker=kwargs.get("max_rounds_per_worker", 8),
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
# LAST_CHANGED: 2026-11-11T16:30:00Z
# CHANGE: Support Web RPC task handles (dsh_rpc_web::) for session ID extraction and round continuity
# COVERAGE_AUDIT: 2026-10-18T19:13:51Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

__initialize__ = auto_initialize()
_initialize_ = __initialize__
