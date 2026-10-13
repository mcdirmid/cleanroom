# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_harness_impl implementation library
# CODE_HASH: 6a2e5ad315c3
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for dsh_harness_impl."""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Sequence
import uuid
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.subagent.lib import subagent_coordinator
from update_with_ai.parts.workspace.lib import workspace_work
from . import dsh_harness, dsh_workspace


def _compute_dsh_rate_card_cost(
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    model_name: Optional[str] = None,
) -> float:
    """Computes monetary token expenditure based on model rate cards."""
    # Default rates for frontier DeepSeek models (DeepSeek-V4.1-Flash)
    # $0.14 per 1M uncached input tokens, $0.014 per 1M cached input tokens, $0.28 per 1M output tokens
    uncached_rate = 0.00000014
    cached_rate = 0.000000014
    output_rate = 0.00000028

    if model_name:
        m = model_name.lower()
        if any(local_k in m for local_k in ("qwen", "reap", "gemma", "mlx", "local")):
            # Local models run with zero marginal cloud API cost
            return 0.0
        elif "opus" in m:
            uncached_rate = 0.000015
            cached_rate = 0.00000375
            output_rate = 0.000075
        elif "gpt-4o" in m:
            uncached_rate = 0.0000025
            cached_rate = 0.000000625
            output_rate = 0.000010

    return (input_tokens * uncached_rate) + (cached_tokens * cached_rate) + (output_tokens * output_rate)


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


def _sync_desktop_session(
    sessions_dir: Optional[str],
    workspace_dir: str,
    role_name: str,
    dir_scope: str,
    start_time: float,
) -> None:
    """Synchronizes sessions into DeepSeekHarness Desktop App workspace and session storage."""
    if not sessions_dir or not os.path.isdir(sessions_dir):
        return
    try:
        harness_dir = os.path.dirname(sessions_dir)
        ws_file = os.path.join(harness_dir, "storages", "workspace.json")
        projcache_dir = os.path.join(harness_dir, "storages", "session_projcache", "sessions")
        os.makedirs(projcache_dir, exist_ok=True)

        ws_data: Dict[str, Any] = {}
        if os.path.isfile(ws_file):
            with open(ws_file, "r", encoding="utf-8") as f:
                ws_data = json.load(f)

        tables = ws_data.setdefault("tables", {})
        workspaces = tables.setdefault("workspaces", {})
        global_info = ws_data.setdefault("global", {})
        ws_ids = global_info.setdefault("workspaceIds", [])

        # Find or create workspace entry
        target_ws_id = None
        for wid, winfo in workspaces.items():
            if os.path.realpath(winfo.get("path", "")) == os.path.realpath(workspace_dir):
                target_ws_id = wid
                break

        if not target_ws_id:
            target_ws_id = str(uuid.uuid4())
            workspaces[target_ws_id] = {
                "path": os.path.realpath(workspace_dir),
                "title": os.path.basename(workspace_dir),
                "sessionIds": [],
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
            if target_ws_id not in ws_ids:
                ws_ids.append(target_ws_id)

        ws_entry = workspaces[target_ws_id]
        existing_sess = set(ws_entry.setdefault("sessionIds", []))

        # Look up workspace sessions directory
        encoded_ws = "--" + os.path.realpath(workspace_dir).strip("/").replace("/", "-") + "--"
        ws_sess_dir = os.path.join(sessions_dir, encoded_ws)
        if os.path.isdir(ws_sess_dir):
            for entry in os.listdir(ws_sess_dir):
                if entry.startswith("."):
                    continue
                if entry not in existing_sess:
                    ws_entry["sessionIds"].append(entry)
                    existing_sess.add(entry)

                # Set title in projcache
                pc_file = os.path.join(projcache_dir, f"{entry}.json")
                title_val = f"[{role_name.upper()}] {dir_scope} Turn"
                if not os.path.isfile(pc_file):
                    rec = {
                        "version": 7,
                        "record": {
                            "identity": {
                                "formatVersion": 4,
                                "createdAt": int(start_time * 1000),
                                "cwd": workspace_dir,
                                "isSeeded": False,
                                "inheritedEventCount": 0,
                            },
                            "rows": {
                                "title": {"ver": 1, "seq": 1, "val": title_val},
                            },
                        },
                    }
                    with open(pc_file, "w", encoding="utf-8") as pf:
                        json.dump(rec, pf, indent=2)
                else:
                    try:
                        with open(pc_file, "r", encoding="utf-8") as pf:
                            pdata = json.load(pf)
                        rec = pdata.setdefault("record", {})
                        ident = rec.setdefault("identity", {})
                        ident.setdefault("formatVersion", 4)
                        ident.setdefault("cwd", workspace_dir)
                        ident.setdefault("isSeeded", False)
                        ident.setdefault("inheritedEventCount", 0)
                        if "createdAt" not in ident:
                            ident["createdAt"] = int(start_time * 1000)

                        rows = rec.setdefault("rows", {})
                        cur_title = rows.get("title", {}).get("val")
                        if not cur_title or cur_title == "Untitled":
                            rows["title"] = {"ver": 1, "seq": 1, "val": title_val}
                        with open(pc_file, "w", encoding="utf-8") as pf:
                            json.dump(pdata, pf, indent=2)
                    except Exception:
                        pass

        with open(ws_file, "w", encoding="utf-8") as f:
            json.dump(ws_data, f, indent=2)
    except Exception:
        pass


class DshTelemetryParser(dsh_harness.DshTelemetryParser):
    """Realizes event stream and session storage archive parsing for DeepSeek Harness."""

    def parse_stream_text(
        self,
        stream_text: str,
        model_name: Optional[str] = None,
    ) -> dsh_harness.DshSessionTokenMetrics:
        """Parses stdout JSON event stream or log text for token metrics."""
        input_tokens = 0
        cached_tokens = 0
        output_tokens = 0

        # Try parsing JSON stream lines from `dsh --profile headless --json`
        found_json_usage = False
        for line in stream_text.splitlines():
            line_str = line.strip()
            if not line_str.startswith("{"):
                continue
            try:
                ev = json.loads(line_str)
                # Look for usage object in root, data, or stream chunks
                usage = ev.get("usage")
                if not usage and isinstance(ev.get("data"), dict):
                    usage = ev["data"].get("usage")
                if isinstance(usage, dict):
                    in_t = int(usage.get("inputTokens") or 0)
                    cached_t = int(usage.get("cacheReadTokens") or 0)
                    out_t = int(usage.get("outputTokens") or 0)
                    if in_t > 0 or cached_t > 0 or out_t > 0:
                        input_tokens += in_t
                        cached_tokens += cached_t
                        output_tokens += out_t
                        found_json_usage = True
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

        # Fallback to regex pattern matching if JSON usage objects were absent
        if not found_json_usage:
            for line in stream_text.splitlines():
                m_in = re.search(r"(?:input_tokens|Input tokens|inputTokens):\s*(\d+)", line, re.IGNORECASE)
                if m_in:
                    input_tokens += int(m_in.group(1))

                m_cached = re.search(r"(?:cached_tokens|Cached tokens|cacheReadTokens):\s*(\d+)", line, re.IGNORECASE)
                if m_cached:
                    cached_tokens += int(m_cached.group(1))

                m_out = re.search(r"(?:output_tokens|Output tokens|outputTokens):\s*(\d+)", line, re.IGNORECASE)
                if m_out:
                    output_tokens += int(m_out.group(1))

        total_tokens = input_tokens + cached_tokens + output_tokens
        cost = _compute_dsh_rate_card_cost(input_tokens, cached_tokens, output_tokens, model_name)

        return dsh_harness.DshSessionTokenMetrics(
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            model_name=model_name or "",
        )

    def parse_session_storage(
        self,
        sessions_dir: str,
        workspace_dir: str,
        model_name: Optional[str] = None,
    ) -> dsh_harness.DshSessionTokenMetrics:
        """Queries session storage archives and returns token metrics."""
        if not os.path.isdir(sessions_dir):
            return dsh_harness.DshSessionTokenMetrics(model_name=model_name or "")

        slug = "-" + workspace_dir.strip("/").replace("/", "-") + "-"
        target_dir = os.path.join(sessions_dir, slug)
        if not os.path.isdir(target_dir):
            target_dir = os.path.join(sessions_dir, f"-{slug}-")
            if not os.path.isdir(target_dir):
                # Search directory names containing the basename of the workspace
                ws_base = os.path.basename(workspace_dir.rstrip("/"))
                matches = [
                    d for d in os.listdir(sessions_dir)
                    if os.path.isdir(os.path.join(sessions_dir, d)) and ws_base in d
                ]
                if matches:
                    target_dir = os.path.join(sessions_dir, sorted(matches)[-1])
                else:
                    return dsh_harness.DshSessionTokenMetrics(model_name=model_name or "")

        # Find newest session subdirectory
        subdirs = [
            os.path.join(target_dir, s)
            for s in os.listdir(target_dir)
            if os.path.isdir(os.path.join(target_dir, s))
        ]
        if not subdirs:
            return dsh_harness.DshSessionTokenMetrics(model_name=model_name or "")

        newest_session = max(subdirs, key=os.path.getmtime)
        jsonl_zstd = os.path.join(newest_session, "session.v4.jsonl.zstd")
        jsonl_plain = os.path.join(newest_session, "session.v4.jsonl")

        decompressed_text = ""
        if os.path.isfile(jsonl_zstd):
            try:
                proc = subprocess.run(
                    ["zstd", "-dc", jsonl_zstd],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0:
                    decompressed_text = proc.stdout
            except (OSError, subprocess.SubprocessError):
                pass
        elif os.path.isfile(jsonl_plain):
            try:
                with open(jsonl_plain, "r", encoding="utf-8", errors="replace") as f:
                    decompressed_text = f.read()
            except OSError:
                pass

        if decompressed_text:
            return self.parse_stream_text(decompressed_text, model_name=model_name)

        return dsh_harness.DshSessionTokenMetrics(model_name=model_name or "")


@dataclass
class _ActiveDshTask:
    handle: str
    dispatch: subagent_coordinator.RoleDispatch
    process: Optional[subprocess.Popen[Any]]
    pending_before: Sequence[str]
    start_time: float
    prompt_file: str
    log_file: str


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
        parser: Optional[dsh_harness.DshTelemetryParser] = None,
    ) -> None:
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._max_context_tokens = max_context_tokens
        self._custom_cmd = custom_cmd
        self._sessions_dir = sessions_dir or os.path.expanduser(
            "~/Library/Application Support/dsh-desktop/harness/sessions"
        )
        self._simulation_mode = simulation_mode
        self._parser = parser or DshTelemetryParser()
        self._tasks: Dict[str, _ActiveDshTask] = {}

    def _format_task_prompt(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        targets_str = (
            "\n".join(f"- {t}" for t in dispatch.ready_targets)
            if dispatch.ready_targets
            else "- (no explicit targets)"
        )
        return (
            f"# Role Task Instructions\n"
            f"Role: {dispatch.role_name}\n"
            f"Scope: {dispatch.dir_scope}\n"
            f"Workspace: {dispatch.workspace_dir}\n\n"
            f"## Ready Targets\n"
            f"{targets_str}\n\n"
            "## Workflow Directives\n"
            "1. Retrieve assigned work targets using `bin/get_work`.\n"
            "2. Verify and lint your changes using `bin/check_files`.\n"
            "3. Submit clean, validated work targets using `bin/submit`.\n"
            "4. If upstream specifications or artifacts contain defects, record them using `bin/blame`.\n"
            "5. If an unrecoverable failure occurs, signal it using `bin/fail`.\n"
        )

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace."""
        task_handle = f"dsh_{dispatch.role_name}_{int(time.time() * 1000)}"
        work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
        pending_before = list(work_mgr.get_pending_work(dispatch.workspace_dir))

        prompt_text = self._format_task_prompt(dispatch)
        prompt_file = os.path.join(dispatch.workspace_dir, f".dsh_prompt_{task_handle}.md")
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt_text)

        log_path = os.path.join(dispatch.workspace_dir, f".cleanroom_turn_{task_handle}.log")

        # Ensure Cordis overlay patch exists
        patch_file = os.path.join(dispatch.workspace_dir, ".cleanroom", "dsh_patch.yml")
        if not os.path.isfile(patch_file):
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
            session_file = os.path.join(dispatch.workspace_dir, ".cleanroom", "dsh_session_id.txt")
            session_arg = ""
            if os.path.isfile(session_file):
                try:
                    with open(session_file, "r", encoding="utf-8") as sf:
                        saved_sid = sf.read().strip()
                    if saved_sid:
                        # Verify that session.lock is not held by another process (e.g. DSH Desktop)
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
                    _sync_desktop_session(
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
        )
        return task_handle

    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits DeepSeek Harness subagent turn completion and returns outcome result."""
        task = self._tasks.get(task_handle)
        if task is None:
            return subagent_coordinator.RoleTurnResult(
                role="",
                status="failed",
                failure_reason=f"Unknown task handle '{task_handle}'",
            )

        wall_clock = time.time() - task.start_time

        if task.process is not None:
            try:
                if self._timeout_seconds is not None and self._timeout_seconds > 0:
                    task.process.wait(timeout=self._timeout_seconds)
                else:
                    task.process.wait()
            except subprocess.TimeoutExpired:
                task.process.kill()
                task.process.wait()
                return subagent_coordinator.RoleTurnResult(
                    role=task.dispatch.role_name,
                    status="failed",
                    failure_reason="Process execution timed out",
                    wall_clock_seconds=time.time() - task.start_time,
                )
            if task.process.returncode != 0:
                return subagent_coordinator.RoleTurnResult(
                    role=task.dispatch.role_name,
                    status="failed",
                    failure_reason=f"Process exited with code {task.process.returncode}",
                    wall_clock_seconds=time.time() - task.start_time,
                )

        blamed = _read_blame_buffer(task.dispatch.workspace_dir)
        work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
        pending_after = work_mgr.get_pending_work(task.dispatch.workspace_dir)
        submitted = tuple(t for t in task.pending_before if t not in pending_after)

        if blamed:
            status = "blamed"
        else:
            status = "clean"

        # Telemetry parsing
        metrics = dsh_harness.DshSessionTokenMetrics()
        if os.path.isfile(task.log_file):
            try:
                with open(task.log_file, "r", encoding="utf-8", errors="replace") as lf:
                    log_text = lf.read()
                metrics = self._parser.parse_stream_text(stream_text=log_text, model_name=self._model_name)
            except OSError:
                pass

        if metrics.total_tokens == 0 and self._sessions_dir and os.path.isdir(self._sessions_dir):
            metrics = self._parser.parse_session_storage(
                sessions_dir=self._sessions_dir,
                workspace_dir=task.dispatch.workspace_dir,
                model_name=self._model_name,
            )

        token_usage = subagent_coordinator.TokenUsage(
            input_tokens=metrics.input_tokens,
            cached_tokens=metrics.cached_tokens,
            output_tokens=metrics.output_tokens,
            total_tokens=metrics.total_tokens,
            cost_usd=metrics.cost_usd,
        )

        # Persist session ID if not already saved
        session_file = os.path.join(task.dispatch.workspace_dir, ".cleanroom", "dsh_session_id.txt")
        if not os.path.isfile(session_file) and os.path.isfile(task.log_file):
            try:
                with open(task.log_file, "r", encoding="utf-8", errors="replace") as lf:
                    for line in lf:
                        line_str = line.strip()
                        if line_str.startswith("{"):
                            ev = json.loads(line_str)
                            sid = ev.get("sessionId")
                            if sid:
                                os.makedirs(os.path.dirname(session_file), exist_ok=True)
                                with open(session_file, "w", encoding="utf-8") as sf:
                                    sf.write(sid)
                                break
            except Exception:
                pass

        if not self._simulation_mode:
            _sync_desktop_session(
                sessions_dir=self._sessions_dir,
                workspace_dir=task.dispatch.workspace_dir,
                role_name=task.dispatch.role_name,
                dir_scope=task.dispatch.dir_scope,
                start_time=task.start_time,
            )

        return subagent_coordinator.RoleTurnResult(
            role=task.dispatch.role_name,
            status=status,
            submitted_targets=submitted,
            blamed_targets=tuple(blamed),
            telemetry=token_usage,
            wall_clock_seconds=wall_clock,
        )

    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls DeepSeek Harness subagent turn execution without blocking."""
        task = self._tasks.get(task_handle)
        if task is None:
            return subagent_coordinator.RoleTurnResult(
                role="",
                status="failed",
                failure_reason=f"Unknown task handle '{task_handle}'",
            )

        if self._simulation_mode or task.process is None:
            return self.await_role(task_handle)

        poll_res = task.process.poll()
        if poll_res is None:
            if self._timeout_seconds is not None and self._timeout_seconds > 0:
                elapsed = time.time() - task.start_time
                if elapsed >= self._timeout_seconds:
                    return self.await_role(task_handle)
            if not self._simulation_mode and self._sessions_dir:
                try:
                    _sync_desktop_session(
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

    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active DeepSeek Harness subagent task execution upon timeout or limit."""
        task = self._tasks.get(task_handle)
        if task and task.process:
            try:
                task.process.kill()
            except OSError:
                pass


class DshHarnessManager(dsh_harness.DshHarnessManager, Singleton):
    """Realizes management of DeepSeek Harness execution adapters and telemetry parsing."""

    tier = agent_session.agent_session

    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        sessions_dir: Optional[str] = None,
    ) -> dsh_harness.DshHarnessAdapter:
        """Constructs a DeepSeek Harness adapter instance."""
        return DshHarnessAdapter(
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            max_context_tokens=max_context_tokens,
            custom_cmd=custom_cmd,
            sessions_dir=sessions_dir,
            parser=self.get_telemetry_parser(),
        )

    def get_telemetry_parser(self) -> dsh_harness.DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service."""
        return DshTelemetryParser()


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
