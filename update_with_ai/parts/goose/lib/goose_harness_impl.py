# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T09:50:00Z
# CHANGE: author goose_harness_impl implementation library
# CODE_HASH: 197050ac7f04
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for goose_harness_impl."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import sqlite3
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
from update_with_ai.parts.subagent.lib import subagent_coordinator
from update_with_ai.parts.workspace.lib import workspace_work
from . import goose_harness


def _compute_rate_card_cost(
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    model_name: Optional[str] = None,
) -> float:
    """Computes monetary token expenditure based on model rate cards."""
    uncached_rate = 0.0000025
    cached_rate = 0.000000625
    output_rate = 0.000010
    if model_name:
        m = model_name.lower()
        if "gpt-4o-mini" in m or "flash" in m:
            uncached_rate = 0.00000015
            cached_rate = 0.000000075
            output_rate = 0.0000006
        elif "opus" in m:
            uncached_rate = 0.000015
            cached_rate = 0.00000375
            output_rate = 0.000075
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


class GooseTelemetryParser(goose_harness.GooseTelemetryParser):
    """Realizes SQLite session database parsing and Goose pricing calculation."""

    def parse_session_db(
        self,
        sessions_db_path: str,
        session_name: str,
        model_name: Optional[str] = None,
    ) -> goose_harness.GooseSessionTokenMetrics:
        """Queries the SQLite sessions database and returns token metrics."""
        if not os.path.isfile(sessions_db_path):
            return goose_harness.GooseSessionTokenMetrics(model_name=model_name or "")

        try:
            with sqlite3.connect(sessions_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, input_tokens, cache_read_tokens, output_tokens, accumulated_cost "
                    "FROM sessions WHERE name = ? ORDER BY id DESC LIMIT 1",
                    (session_name,),
                )
                row = cursor.fetchone()
                if not row:
                    return goose_harness.GooseSessionTokenMetrics(model_name=model_name or "")

                session_id = str(row[0])
                in_tok = int(row[1] or 0)
                cached_tok = int(row[2] or 0)
                out_tok = int(row[3] or 0)
                cost = float(row[4] or 0.0)

                # Check usage_ledger for granular token records
                try:
                    cursor.execute(
                        "SELECT SUM(input_tokens), SUM(cache_read_tokens), SUM(output_tokens), SUM(cost) "
                        "FROM usage_ledger WHERE session_id = ?",
                        (session_id,),
                    )
                    ledger_row = cursor.fetchone()
                    if ledger_row and ledger_row[0] is not None:
                        ledger_in = int(ledger_row[0] or 0)
                        ledger_cached = int(ledger_row[1] or 0)
                        ledger_out = int(ledger_row[2] or 0)
                        ledger_cost = float(ledger_row[3] or 0.0)
                        if ledger_in > in_tok:
                            in_tok = ledger_in
                        if ledger_cached > cached_tok:
                            cached_tok = ledger_cached
                        if ledger_out > out_tok:
                            out_tok = ledger_out
                        if ledger_cost > cost:
                            cost = ledger_cost
                except sqlite3.Error:
                    pass

                if cost <= 0.0 and (in_tok > 0 or cached_tok > 0 or out_tok > 0):
                    cost = _compute_rate_card_cost(in_tok, cached_tok, out_tok, model_name)

                total = in_tok + cached_tok + out_tok
                return goose_harness.GooseSessionTokenMetrics(
                    input_tokens=in_tok,
                    cached_tokens=cached_tok,
                    output_tokens=out_tok,
                    total_tokens=total,
                    cost_usd=cost,
                    model_name=model_name or "",
                )
        except (sqlite3.Error, OSError, ValueError):
            return goose_harness.GooseSessionTokenMetrics(model_name=model_name or "")

    def parse_log_text(
        self,
        log_text: str,
        model_name: Optional[str] = None,
    ) -> goose_harness.GooseSessionTokenMetrics:
        """Parses stdout log text for token metrics when database records are unavailable."""
        input_tokens = 0
        cached_tokens = 0
        output_tokens = 0
        cost_parsed: Optional[float] = None

        for line in log_text.splitlines():
            m_in = re.search(r"(?:input_tokens|Input tokens|Prompt tokens):\s*(\d+)", line, re.IGNORECASE)
            if m_in:
                input_tokens += int(m_in.group(1))

            m_cached = re.search(r"(?:cached_tokens|Cached tokens|Cache read tokens):\s*(\d+)", line, re.IGNORECASE)
            if m_cached:
                cached_tokens += int(m_cached.group(1))

            m_out = re.search(r"(?:output_tokens|Output tokens|Completion tokens):\s*(\d+)", line, re.IGNORECASE)
            if m_out:
                output_tokens += int(m_out.group(1))

            m_cost = re.search(r"(?:accumulated_cost|cost):\s*\$?([\d.]+)", line, re.IGNORECASE)
            if m_cost:
                cost_parsed = float(m_cost.group(1))

        if cost_parsed is not None and cost_parsed > 0.0:
            cost = cost_parsed
        else:
            cost = _compute_rate_card_cost(input_tokens, cached_tokens, output_tokens, model_name)

        total = input_tokens + cached_tokens + output_tokens
        return goose_harness.GooseSessionTokenMetrics(
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            cost_usd=cost,
            model_name=model_name or "",
        )


@dataclass
class _ActiveGooseTask:
    handle: str
    dispatch: subagent_coordinator.RoleDispatch
    process: Optional[subprocess.Popen[Any]]
    pending_before: Sequence[str]
    start_time: float
    instructions_file: str
    log_file: str


class GooseHarnessAdapter(goose_harness.GooseHarnessAdapter):
    """Realizes subagent execution in Goose role workspaces."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        sessions_db_path: Optional[str] = None,
        simulation_mode: bool = False,
        parser: Optional[goose_harness.GooseTelemetryParser] = None,
    ) -> None:
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._max_context_tokens = max_context_tokens
        self._custom_cmd = custom_cmd
        self._sessions_db_path = sessions_db_path
        self._simulation_mode = simulation_mode
        self._parser = parser or GooseTelemetryParser()
        self._tasks: Dict[str, _ActiveGooseTask] = {}

    def _format_task_prompt(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        targets_str = "\n".join(f"- {t}" for t in dispatch.ready_targets) if dispatch.ready_targets else "- (no explicit targets)"
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
        """Dispatches work directive to a Goose role workspace."""
        task_handle = f"goose_{dispatch.role_name}_{int(time.time() * 1000)}"
        work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
        pending_before = list(work_mgr.get_pending_work(dispatch.workspace_dir))

        prompt_text = self._format_task_prompt(dispatch)
        inst_file = os.path.join(dispatch.workspace_dir, f".goose_instructions_{task_handle}.md")
        with open(inst_file, "w", encoding="utf-8") as f:
            f.write(prompt_text)

        log_path = os.path.join(dispatch.workspace_dir, f".cleanroom_turn_{task_handle}.log")

        if self._simulation_mode:
            proc = None
        else:
            if self._custom_cmd:
                cmd = self._custom_cmd.format(
                    workspace_dir=dispatch.workspace_dir,
                    instructions_file=inst_file,
                    prompt_file=inst_file,
                    role_name=dispatch.role_name,
                )
            else:
                cmd = f"goose run --instructions {inst_file}"
            log_f = open(log_path, "w", encoding="utf-8")
            env = os.environ.copy()
            if self._max_context_tokens is not None and self._max_context_tokens > 0:
                env["GOOSE_AUTO_COMPACT_TOKEN_LIMIT"] = str(self._max_context_tokens)
            proc = subprocess.Popen(
                cmd,
                shell=True,
                cwd=dispatch.workspace_dir,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                env=env,
            )

        self._tasks[task_handle] = _ActiveGooseTask(
            handle=task_handle,
            dispatch=dispatch,
            process=proc,
            pending_before=pending_before,
            start_time=time.time(),
            instructions_file=inst_file,
            log_file=log_path,
        )
        return task_handle

    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits Goose subagent turn completion and returns outcome result."""
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
        metrics = goose_harness.GooseSessionTokenMetrics()
        if self._sessions_db_path and os.path.isfile(self._sessions_db_path):
            metrics = self._parser.parse_session_db(
                sessions_db_path=self._sessions_db_path,
                session_name=task_handle,
                model_name=self._model_name,
            )
        elif os.path.isfile(task.log_file):
            try:
                with open(task.log_file, "r", encoding="utf-8", errors="replace") as lf:
                    log_text = lf.read()
                metrics = self._parser.parse_log_text(log_text=log_text, model_name=self._model_name)
            except OSError:
                pass

        token_usage = subagent_coordinator.TokenUsage(
            input_tokens=metrics.input_tokens,
            cached_tokens=metrics.cached_tokens,
            output_tokens=metrics.output_tokens,
            total_tokens=metrics.total_tokens,
            cost_usd=metrics.cost_usd,
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
        """Polls Goose subagent turn execution without blocking."""
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
            return None

        return self.await_role(task_handle)

    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active Goose subagent task execution upon timeout or limit."""
        task = self._tasks.get(task_handle)
        if task and task.process:
            try:
                task.process.kill()
            except OSError:
                pass


class GooseHarnessManager(goose_harness.GooseHarnessManager, Singleton):
    """Realizes management of Goose execution adapters and telemetry parsing."""

    tier = agent_session.agent_session

    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        sessions_db_path: Optional[str] = None,
    ) -> goose_harness.GooseHarnessAdapter:
        """Constructs a Goose harness adapter instance."""
        return GooseHarnessAdapter(
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            max_context_tokens=max_context_tokens,
            custom_cmd=custom_cmd,
            sessions_db_path=sessions_db_path,
            parser=self.get_telemetry_parser(),
        )

    def get_telemetry_parser(self) -> goose_harness.GooseTelemetryParser:
        """Returns the Goose telemetry parser service."""
        return GooseTelemetryParser()


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        GooseHarnessManager,
        keys=[goose_harness.GooseHarnessManager, GooseHarnessManager],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
