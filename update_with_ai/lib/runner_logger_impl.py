# lib/runner_logger_impl.py
"""
Implementation of the LLS RunnerLogger interface.
"""

from __future__ import annotations

import os
import signal
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from .conversation_history import LogEvent, LoggerCallback
from .runner_logger import RunnerLogger

def _sigint_handler(signum, frame):
    """Honor ctrl-C: raise KeyboardInterrupt so the run's cleanup (the log
    file close, per-run state) completes and the process exits with the
    interruption status — the interrupt is never ignored or continued past."""
    raise KeyboardInterrupt


# Register only from the main thread; signal.signal() raises ValueError if
# called from a worker thread. The explicit handler guarantees SIGINT is
# honored even if a dependency (e.g. a library) sets it to SIG_IGN.
if threading.current_thread() is threading.main_thread():
    signal.signal(signal.SIGINT, _sigint_handler)


def _format_compact_log(event: LogEvent, data: Dict[str, Any]) -> Optional[str]:
    """Format a one-line event summary for stdout; None skips the event."""
    node = data.get("node_id", "?")

    if event == "tool_called":
        names = [tc.get("function", {}).get("name", "unknown") for tc in data.get("tool_calls", [])]
        return f"[agent {node}] tool calls: {', '.join(names)}"

    if event == "api_response":
        return None

    if event == "run_terminated":
        session = data.get("cumulative_usage", {})
        s_in = session.get("input_tokens", session.get("prompt_tokens", 0))
        s_cached = session.get("cached_input_tokens", session.get("cached_prompt_tokens", 0))
        s_out = session.get("output_tokens", session.get("completion_tokens", 0))
        s_reqs = session.get("request_count", 0)
        s_dur = session.get("total_duration_seconds", 0.0)
        s_pct = int(round((s_cached / s_in) * 100)) if s_in > 0 else 0

        cum = data.get("runner_cumulative_usage", session)
        c_in = cum.get("input_tokens", cum.get("prompt_tokens", 0))
        c_cached = cum.get("cached_input_tokens", cum.get("cached_prompt_tokens", 0))
        c_out = cum.get("output_tokens", cum.get("completion_tokens", 0))
        c_reqs = cum.get("request_count", 0)
        c_dur = cum.get("total_duration_seconds", 0.0)
        c_pct = int(round((c_cached / c_in) * 100)) if c_in > 0 else 0

        return (
            f"[agent {node}] terminated ({data.get('termination_value', '?')}); "
            f"session: input {s_in} ({s_pct}% cached), output {s_out} "
            f"({s_reqs} requests, {s_dur:.2f}s) | "
            f"cumulative: input {c_in} ({c_pct}% cached), output {c_out} "
            f"({c_reqs} requests, {c_dur:.2f}s)"
        )

    if event == "error":
        return f"[agent {node}] ERROR: {data.get('error', 'unknown error')}"

    return None


def _format_full_log(event: LogEvent, data: Dict[str, Any]) -> str:
    """Format a verbose transcript line for the agent log file."""
    node = data.get("node_id", "?")

    if event == "message_added":
        msg = data.get("message", {})
        role = msg.get("role", "unknown")
        content = msg.get("content")
        if content is not None:
            preview = str(content).replace("\n", "\\n")
            if len(preview) > 200:
                preview = preview[:200] + "..."
            return f"[{node}] message_added ({role}): {preview}"
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            names = [tc.get("function", {}).get("name", "unknown") for tc in tool_calls]
            return f"[{node}] message_added ({role}): tool_calls={', '.join(names)}"
        return f"[{node}] message_added ({role}): (no content)"

    if event == "message_stubbed":
        stubbed = data.get("stubbed_message", {})
        content = str(stubbed.get("content", "")).replace("\n", "\\n")[:80]
        return f"[{node}] message_stubbed: content={content!r}"

    if event == "tool_result":
        parts = []
        for r in data.get("results", []):
            supersedes = getattr(r, "supersedes", False)
            content = str(getattr(r, "content", "")).replace("\n", "\\n")[:80]
            parts.append(f"supersedes={supersedes!r} content={content!r}")
        return f"[{node}] tool_result ({len(parts)}): {'; '.join(parts)}"

    if event == "tool_called":
        parts = []
        for tc in data.get("tool_calls", []):
            name = tc.get("function", {}).get("name", "unknown")
            args = tc.get("function", {}).get("arguments", "{}")
            parts.append(f"{name}({str(args)[:100]})")
        return f"[{node}] tool_called: {'; '.join(parts)}"

    if event == "api_response":
        return f"[{node}] api_response"

    if event == "reminder_injected":
        return f"[{node}] reminder_injected: {data.get('message', '')}"

    if event == "run_terminated":
        session = data.get("cumulative_usage", {})
        s_in = session.get("input_tokens", session.get("prompt_tokens", 0))
        s_cached = session.get("cached_input_tokens", session.get("cached_prompt_tokens", 0))
        s_out = session.get("output_tokens", session.get("completion_tokens", 0))
        s_reqs = session.get("request_count", 0)
        s_dur = session.get("total_duration_seconds", 0.0)
        s_pct = int(round((s_cached / s_in) * 100)) if s_in > 0 else 0

        cum = data.get("runner_cumulative_usage", session)
        c_in = cum.get("input_tokens", cum.get("prompt_tokens", 0))
        c_cached = cum.get("cached_input_tokens", cum.get("cached_prompt_tokens", 0))
        c_out = cum.get("output_tokens", cum.get("completion_tokens", 0))
        c_reqs = cum.get("request_count", 0)
        c_dur = cum.get("total_duration_seconds", 0.0)
        c_pct = int(round((c_cached / c_in) * 100)) if c_in > 0 else 0

        return (
            f"[{node}] run_terminated: {data.get('termination_value', '?')} | "
            f"session: input {s_in} ({s_pct}% cached), output {s_out} "
            f"({s_reqs} requests, {s_dur:.2f}s) context {data.get('final_context_size', 0)} | "
            f"cumulative: input {c_in} ({c_pct}% cached), output {c_out} "
            f"({c_reqs} requests, {c_dur:.2f}s)"
        )

    if event == "error":
        return f"[{node}] error: {data.get('error', 'unknown error')}"

    return f"[{node}] {event}: {data}"



class RunnerLoggerImpl(RunnerLogger):
    """
    Implementation of RunnerLogger.
    """

    def resolve_log_path(self) -> str:
        log_dir = (
            os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            or os.environ.get("BUILD_WORKING_DIRECTORY")
            or os.getcwd()
        )
        log_override = os.environ.get("CLEANROOM_AGENT_LOG")
        if log_override:
            if os.path.isabs(log_override):
                return log_override
            return os.path.join(log_dir, log_override)
        return os.path.join(log_dir, "agent_loop.log")

    def format_compact_log(self, event: LogEvent, data: Dict[str, Any]) -> Optional[str]:
        return _format_compact_log(event, data)

    def format_full_log(self, event: LogEvent, data: Dict[str, Any]) -> str:
        return _format_full_log(event, data)

    def create_agent_logger(self, log_path: str) -> Tuple[LoggerCallback, Callable[[], None]]:
        log_file = open(log_path, "w", encoding="utf-8")

        runner_cumulative_usage: Dict[str, Any] = {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "request_count": 0,
            "total_duration_seconds": 0.0,
        }

        def _agent_logger(event: LogEvent, data: Dict[str, Any]) -> None:
            if event == "run_terminated":
                session = data.get("cumulative_usage", {})
                runner_cumulative_usage["input_tokens"] += session.get(
                    "input_tokens", session.get("prompt_tokens", 0)
                )
                runner_cumulative_usage["cached_input_tokens"] += session.get(
                    "cached_input_tokens", session.get("cached_prompt_tokens", 0)
                )
                runner_cumulative_usage["output_tokens"] += session.get(
                    "output_tokens", session.get("completion_tokens", 0)
                )
                runner_cumulative_usage["total_tokens"] += session.get(
                    "total_tokens", 0
                )
                runner_cumulative_usage["request_count"] += session.get(
                    "request_count", 0
                )
                runner_cumulative_usage["total_duration_seconds"] = round(
                    runner_cumulative_usage["total_duration_seconds"]
                    + session.get("total_duration_seconds", 0.0),
                    3,
                )
                data = dict(data)
                data["runner_cumulative_usage"] = dict(runner_cumulative_usage)

            line = self.format_compact_log(event, data)
            if line is not None:
                print(line)
            log_file.write(self.format_full_log(event, data) + chr(10))
            log_file.flush()

        def _closer() -> None:
            log_file.close()

        return _agent_logger, _closer
