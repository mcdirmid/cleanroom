# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:04Z
# LAST_CHANGED: 2026-10-12T12:35:00Z
# CHANGE: Present single-line event summaries to standard output without timestamps or event names
# CODE_HASH: 8046df110732
# COVERAGE_AUDIT: 2026-10-12T18:21:04Z
# QA_AUDIT: 2026-10-12T18:21:04Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import os
import sys
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, system
from . import runner_logger

# Requirements specified in runner_logger_impl.pyi

_DEFAULT_LOG_PATH = "agent_loop.log"
_LOG_PATH_ENV_VARS = (
    "RUNNER_LOG_FILE",
    "AGENT_LOOP_LOG",
    "TRANSCRIPT_LOG",
    "RUNNER_LOG",
)


class RunnerLogger(runner_logger.RunnerLogger, Singleton):
    """Realizes live terminal logging and unbuffered transcript file output."""

    tier = system

    def __init__(self, log_path: Optional[str] = None) -> None:
        if log_path is None:
            log_path = _DEFAULT_LOG_PATH
            for env_var in _LOG_PATH_ENV_VARS:
                configured = os.environ.get(env_var)
                if configured:
                    log_path = configured
                    break
        self._log_path = log_path
        # Truncate the transcript log file at opening so each run starts fresh.
        with open(self._log_path, "w", encoding="utf-8"):
            pass

    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        sys.stdout.write(f"{event.summary}\n")
        sys.stdout.flush()
        with open(self._log_path, "a", encoding="utf-8") as transcript:
            transcript.write(f"{event.transcript}\n")
            transcript.flush()


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RunnerLogger,
        keys=[RunnerLogger, runner_logger.RunnerLogger],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
