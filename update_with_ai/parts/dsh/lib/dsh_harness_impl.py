# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:55:00Z
# CHANGE: Delegate telemetry parsing and desktop sync to dsh_telemetry
# CODE_HASH: 577918af8d17
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for dsh_harness_impl."""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
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
from update_with_ai.parts.subagent.lib import subagent_coordinator, subagent_harness
from update_with_ai.parts.tools.lib import workspace_work
from update_with_ai.parts.workspace.lib import workspace_registry
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
        parser: Optional[dsh_telemetry.DshTelemetryParser] = None,
    ) -> None:
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._max_context_tokens = max_context_tokens
        self._custom_cmd = custom_cmd
        self._sessions_dir = sessions_dir or os.path.expanduser(
            "~/Library/Application Support/dsh-desktop/harness/sessions"
        )
        self._simulation_mode = simulation_mode
        self._parser = parser
        self._tasks: Dict[str, _ActiveDshTask] = {}

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
        targets_str = (
            "\n".join(f"- {t}" for t in dispatch.ready_targets)
            if dispatch.ready_targets
            else "- (no explicit targets)"
        )
        is_auditor = False
        try:
            reg = get_singleton(workspace_registry.WorkspaceRegistry)
            r_def = reg.resolve_role_definition(dispatch.role_name, dir_scope=dispatch.dir_scope)
            is_auditor = not r_def.writable_file_patterns
        except Exception:
            pass

        if is_auditor:
            return (
                f"# Role Task Instructions\n"
                f"Role: {dispatch.role_name} (Auditor)\n"
                f"Scope: {dispatch.dir_scope}\n"
                f"Workspace: {dispatch.workspace_dir}\n\n"
                f"## Assigned Targets\n"
                f"{targets_str}\n\n"
                "CRITICAL: DO NOT EDIT FILES. You are an auditor. All files in this workspace are strictly read-only. Never attempt to edit, write, or modify code or specifications.\n"
                "CRITICAL: DO NOT EDIT METADATA. Use only tools.\n\n"
                "## Workflow Directives\n"
                "1. Run `bin/get_work` to retrieve assigned targets.\n"
                "2. Run `bin/check_files <target>` to verify each target.\n"
                "3. If tests pass: run `bin/submit <target>` to certify the target.\n"
                "4. If tests fail: run `bin/blame <culprit_file> \"<actionable critique>\"` to attribute blame to the defect.\n"
                "5. If an unrecoverable failure occurs, signal it using `bin/fail`.\n"
            )

        return (
            f"# Role Task Instructions\n"
            f"Role: {dispatch.role_name}\n"
            f"Scope: {dispatch.dir_scope}\n"
            f"Workspace: {dispatch.workspace_dir}\n\n"
            f"## Assigned Targets\n"
            f"{targets_str}\n\n"
            "CRITICAL: DO NOT EDIT METADATA. Never touch `# --- CLEANROOM METADATA ---` or `<!-- CLEANROOM METADATA -->` headers. Use only tools.\n\n"
            "## Workflow Directives\n"
            "1. Run `bin/get_work` to retrieve assigned targets.\n"
            "2. Align and edit code or specifications within your role to satisfy contracts.\n"
            "3. Run `bin/check_files <target>` to verify your changes.\n"
            "4. Run `bin/submit <target> \"<summary>\"` to submit clean work.\n"
            "5. If an upstream contract has defects, record them using `bin/blame`.\n"
            "6. If an unrecoverable failure occurs, signal it using `bin/fail`.\n"
        )

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace."""
        task_handle = f"dsh_{dispatch.role_name}_{int(time.time() * 1000)}"
        work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
        pending_before = list(work_mgr.get_pending_work(dispatch.workspace_dir))

        log_dir = subagent_coordinator.resolve_cleanroom_log_dir(dispatch.workspace_dir)
        prompt_text = self._format_task_prompt(dispatch)
        prompt_file = os.path.join(log_dir, f".dsh_prompt_{task_handle}.md")
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt_text)

        log_path = os.path.join(log_dir, f".cleanroom_turn_{task_handle}.log")

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
            env.setdefault("OMLX_API_KEY", "abcd")

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
        elif submitted:
            status = "clean"
        else:
            status = "unresolved"

        # Telemetry parsing
        metrics = dsh_telemetry.DshSessionTokenMetrics()
        if os.path.isfile(task.log_file):
            try:
                with open(task.log_file, "r", encoding="utf-8", errors="replace") as lf:
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
            self._telemetry_parser.sync_desktop_session(
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

    def initialize(self) -> None:
        """Initializes the manager and installs the adapter factory into the harness registry."""
        try:
            registry = get_singleton(subagent_harness.HarnessRegistry)
            registry.install_harness("dsh", self.create_harness_adapter)
        except Exception:
            pass

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

    def get_telemetry_parser(self) -> dsh_telemetry.DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service."""
        try:
            return get_singleton(dsh_telemetry.DshTelemetryParser)
        except Exception:
            from . import dsh_asm
            dsh_asm.__initialize__()
            return get_singleton(dsh_telemetry.DshTelemetryParser)


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
