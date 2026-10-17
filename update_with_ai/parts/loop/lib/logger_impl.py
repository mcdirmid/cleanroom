# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T12:35:00Z
# CHANGE: Present single-line event summaries to standard output without timestamps or event names
# CODE_HASH: 82e406be5544
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import os
import sys
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, system
from . import logger

# Requirements specified in logger_impl.pyi

# Contract: MUST default the transcript log file destination to 'agent_loop.log'.
_DEFAULT_LOG_PATH = "agent_loop.log"
# Contract: MUST resolve the transcript log file destination from configured environment variables when present.
_LOG_PATH_ENV_VAR = "RUNNER_LOG_FILE"


class RunnerLogger(logger.RunnerLogger, Singleton):
    """Realizes live terminal logging and unbuffered transcript file output."""

    tier = system

    def __init__(self) -> None:
        # Contract: MUST default destination to 'agent_loop.log' unless configured via environment variables.
        log_path = os.environ.get(_LOG_PATH_ENV_VAR) or _DEFAULT_LOG_PATH
        self._log_path = log_path
        # Contract: MUST truncate the transcript log file at opening.
        with open(self._log_path, "w", encoding="utf-8"):
            pass

    def consume(self, event: logger.RunnerLogEvent) -> None:
        # Contract: MUST present single-line event summaries on standard output lines without timestamps or event names.
        sys.stdout.write(f"{event.summary}\n")
        sys.stdout.flush()
        # Contract: MUST append verbose records to transcript log entries.
        with open(self._log_path, "a", encoding="utf-8") as transcript:
            transcript.write(f"{event.transcript}\n")
            # Contract: MUST flush transcript log entries immediately after each write to guarantee unbuffered persistence.
            transcript.flush()


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RunnerLogger,
        keys=[RunnerLogger, logger.RunnerLogger],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
