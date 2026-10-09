# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:21:31Z
# CHANGE: Implement RunnerLogger in runner_logger_impl.py
# CODE_HASH: fced6abf1715
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

import datetime
import os
import sys
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import runner_logger

# Requirements specified in runner_logger_impl.pyi

class RunnerLogger(runner_logger.RunnerLogger, Singleton):
    tier = system

    def __init__(self, log_path: Optional[str] = None) -> None:
        if log_path is None:
            log_path = (
                os.environ.get("RUNNER_LOG_FILE")
                or os.environ.get("AGENT_LOOP_LOG")
                or os.environ.get("TRANSCRIPT_LOG")
                or os.environ.get("RUNNER_LOG")
                or "agent_loop.log"
            )
        self._log_path = log_path
        with open(self._log_path, "w", encoding="utf-8") as f:
            pass

    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sys.stdout.write(f"[{timestamp}] [{event.event_name}] {event.summary}\n")
        sys.stdout.flush()
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(f"{event.transcript}\n")
            f.flush()


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RunnerLogger,
        keys=[RunnerLogger, runner_logger.RunnerLogger],
        tier=system,
    )

_initialize_ = __initialize__
