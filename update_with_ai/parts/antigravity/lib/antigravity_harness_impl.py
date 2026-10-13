# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_harness_impl implementation library
# CODE_HASH: bc1d7ab763d1
# COVERAGE_AUDIT: 2026-10-12T23:37:36Z
# QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for antigravity_harness_impl."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.subagent.lib import subagent_coordinator
from . import antigravity_harness


# Rate card per 1,000,000 tokens from design-docs/subagent_driven_cleanroom_workspaces_todo.md Section 5.3
PRICING_RATES: Dict[str, Tuple[float, float, float]] = {
    # model_key: (cached_input_per_m, uncached_input_per_m, output_per_m)
    "gemini-3.8-flash": (0.025, 0.10, 0.40),
    "gemini-flash": (0.025, 0.10, 0.40),
    "gemini-3.8-pro": (0.3125, 1.25, 5.00),
    "gemini-pro": (0.3125, 1.25, 5.00),
    "default": (0.025, 0.10, 0.40),
}


def _read_blame_buffer(workspace_dir: str) -> List[str]:
    """Reads blamed culprit target paths from the workspace blame buffer."""
    buf_path = os.path.join(workspace_dir, ".cleanroom_blame_buffer.json")
    if not os.path.isfile(buf_path):
        return []
    try:
        with open(buf_path, "r", encoding="utf-8") as f:
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


def _resolve_pricing_rates(model_name: Optional[str] = None) -> Tuple[float, float, float]:
    """Resolves (cached_per_m, input_per_m, output_per_m) for model name."""
    if not model_name:
        return PRICING_RATES["default"]
    lower = model_name.lower()
    if "flash" in lower:
        return PRICING_RATES["gemini-flash"]
    elif "pro" in lower:
        return PRICING_RATES["gemini-pro"]
    return PRICING_RATES.get(lower, PRICING_RATES["default"])


class TranscriptTelemetryParser(antigravity_harness.TranscriptTelemetryParser):
    """Realizes JSONL transcript parsing and Gemini pricing calculation."""

    def parse_transcript_file(
        self,
        transcript_path: str,
        model_name: Optional[str] = None,
    ) -> antigravity_harness.TranscriptTokenMetrics:
        """Parses a transcript log file and returns token metrics."""
        if not os.path.isfile(transcript_path):
            return antigravity_harness.TranscriptTokenMetrics(
                model_name=model_name or "gemini-flash"
            )

        input_tokens = 0
        cached_tokens = 0
        output_tokens = 0
        resolved_model = model_name or ""

        try:
            with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line_s = line.strip()
                    if not line_s:
                        continue
                    try:
                        data = json.loads(line_s)
                        if isinstance(data, dict):
                            # Inspect usage or metadata objects
                            usage = data.get("usage") or data.get("metadata", {}).get("usage") or {}
                            if isinstance(usage, dict):
                                in_t = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                                cache_t = usage.get("cached_tokens") or usage.get("cache_read_tokens") or 0
                                out_t = usage.get("output_tokens") or usage.get("completion_tokens") or 0
                                input_tokens += int(in_t)
                                cached_tokens += int(cache_t)
                                output_tokens += int(out_t)

                            m_name = data.get("model") or data.get("metadata", {}).get("model")
                            if m_name and not resolved_model:
                                resolved_model = str(m_name)
                    except json.JSONDecodeError:
                        # Fallback regex parsing on line
                        for m in re.finditer(r"(?:input_tokens|Input tokens)[:=]\s*(\d+)", line_s, re.IGNORECASE):
                            input_tokens += int(m.group(1))
                        for m in re.finditer(r"(?:cached_tokens|Cached tokens)[:=]\s*(\d+)", line_s, re.IGNORECASE):
                            cached_tokens += int(m.group(1))
                        for m in re.finditer(r"(?:output_tokens|Output tokens)[:=]\s*(\d+)", line_s, re.IGNORECASE):
                            output_tokens += int(m.group(1))
        except OSError:
            pass

        if not resolved_model:
            resolved_model = model_name or "gemini-flash"

        cached_per_m, input_per_m, output_per_m = _resolve_pricing_rates(resolved_model)
        cost_usd = (
            (input_tokens * (input_per_m / 1_000_000.0))
            + (cached_tokens * (cached_per_m / 1_000_000.0))
            + (output_tokens * (output_per_m / 1_000_000.0))
        )

        total_tokens = input_tokens + cached_tokens + output_tokens
        return antigravity_harness.TranscriptTokenMetrics(
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            model_name=resolved_model,
        )


class AntigravityHarnessAdapter(antigravity_harness.AntigravityHarnessAdapter):
    """Realizes subagent execution in Antigravity role workspaces."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: float = 600.0,
        custom_cmd: Optional[str] = None,
        transcript_parser: Optional[TranscriptTelemetryParser] = None,
    ) -> None:
        self.model_name = model_name or "gemini-flash"
        self.timeout_seconds = timeout_seconds
        self.custom_cmd = custom_cmd
        self.transcript_parser = transcript_parser or TranscriptTelemetryParser()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._handle_counter = 0

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to an Antigravity role workspace."""
        self._handle_counter += 1
        handle = f"antigravity-task-{self._handle_counter}-{dispatch.role_name}"

        prompt_dir = os.path.join(dispatch.workspace_dir, ".cleanroom")
        os.makedirs(prompt_dir, exist_ok=True)
        prompt_file = os.path.join(prompt_dir, "task_prompt.md")
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(dispatch.task_prompt)

        cmd_template = self.custom_cmd or "agy run --cwd {workspace_dir} --file {prompt_file}"
        formatted_cmd = cmd_template.format(
            workspace_dir=dispatch.workspace_dir,
            prompt_file=prompt_file,
            role_name=dispatch.role_name,
            dir_scope=dispatch.dir_scope,
        )

        proc = None
        if formatted_cmd.strip() != "simulation":
            try:
                proc = subprocess.Popen(
                    formatted_cmd,
                    shell=True,
                    cwd=dispatch.workspace_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except OSError:
                proc = None

        self._tasks[handle] = {
            "dispatch": dispatch,
            "proc": proc,
            "cmd": formatted_cmd,
            "start_time": time.time(),
            "prompt_file": prompt_file,
        }
        return handle

    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result."""
        task = self._tasks.get(task_handle)
        if not task:
            return subagent_coordinator.RoleTurnResult(
                role="",
                status="failed",
                failure_reason=f"Unknown task handle: {task_handle}",
            )

        dispatch: subagent_coordinator.RoleDispatch = task["dispatch"]
        proc: Optional[subprocess.Popen[str]] = task.get("proc")
        start_time: float = task.get("start_time", time.time())

        exit_code = 0
        stdout_txt = ""
        stderr_txt = ""

        if proc is not None:
            try:
                stdout_txt, stderr_txt = proc.communicate(timeout=self.timeout_seconds)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                exit_code = -9
                stderr_txt = f"Execution timed out after {self.timeout_seconds} seconds."

        elapsed = time.time() - start_time

        # Check for blamed culprit targets in workspace blame buffer
        blamed = _read_blame_buffer(dispatch.workspace_dir)

        # Look for submitted targets in stdout or ready_targets
        submitted: List[str] = []
        for m in re.finditer(r"\[SUBMITTED\]\s*([a-zA-Z0-9_\-/\.]+)", stdout_txt):
            submitted.append(m.group(1))

        # Check for transcript log
        transcript_path = os.path.join(dispatch.workspace_dir, ".cleanroom", "transcript.jsonl")
        metrics = self.transcript_parser.parse_transcript_file(transcript_path, self.model_name)
        telemetry = subagent_coordinator.TokenUsage(
            input_tokens=metrics.input_tokens,
            cached_tokens=metrics.cached_tokens,
            output_tokens=metrics.output_tokens,
            total_tokens=metrics.total_tokens,
            cost_usd=metrics.cost_usd,
        )

        status = "complete"
        failure_reason = None
        if exit_code != 0:
            status = "failed"
            failure_reason = f"Process exited with non-zero code {exit_code}: {stderr_txt.strip()}"
        elif blamed:
            status = "blamed"

        return subagent_coordinator.RoleTurnResult(
            role=dispatch.role_name,
            status=status,
            submitted_targets=submitted,
            blamed_targets=blamed,
            failure_reason=failure_reason,
            telemetry=telemetry,
            wall_clock_seconds=elapsed,
        )

    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or limit."""
        task = self._tasks.get(task_handle)
        if not task:
            return
        proc: Optional[subprocess.Popen[str]] = task.get("proc")
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass


class AntigravityHarnessManager(
    Singleton,
    antigravity_harness.AntigravityHarnessManager,
):
    """Realizes management of Antigravity execution adapters and transcript parsing."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._parser = TranscriptTelemetryParser()

    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: float = 600.0,
        custom_cmd: Optional[str] = None,
    ) -> antigravity_harness.AntigravityHarnessAdapter:
        """Constructs an Antigravity harness adapter instance."""
        return AntigravityHarnessAdapter(
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            custom_cmd=custom_cmd,
            transcript_parser=self._parser,
        )

    def get_transcript_parser(self) -> antigravity_harness.TranscriptTelemetryParser:
        """Returns the transcript telemetry parser service."""
        return self._parser


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AntigravityHarnessManager,
        keys=[
            antigravity_harness.AntigravityHarnessManager,
            AntigravityHarnessManager,
        ],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
