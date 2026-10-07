# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: ab76c54f4175
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

# Requirements specified in runner_logger_impl.pyi
import os
from typing import Optional
from . import runner_logger
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)


class RunnerLogger(runner_logger.RunnerLogger, Singleton):
    tier = system

    def __init__(self) -> None:
        self.transcript_file_path = os.environ.get(
            "TRANSCRIPT_LOG_PATH", "agent_loop.log"
        )

    def initialize(self) -> None:
        self.transcript_file_path = os.environ.get(
            "TRANSCRIPT_LOG_PATH", "agent_loop.log"
        )
        dirname = os.path.dirname(self.transcript_file_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(self.transcript_file_path, "w", encoding="utf-8") as f:
            f.write("")

    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        print(event.summary, flush=True)
        dirname = os.path.dirname(self.transcript_file_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(self.transcript_file_path, "a", encoding="utf-8") as f:
            f.write(event.transcript + "\n")
            f.flush()


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RunnerLogger,
        keys=[RunnerLogger, runner_logger.RunnerLogger],
        tier=system,
    )
