import os
from typing import Optional
from . import runner_logger
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry

class RunnerLogger(runner_logger.RunnerLogger, Singleton):
    tier = "system"

    def __init__(self) -> None:
        self.transcript_file_path = os.environ.get("TRANSCRIPT_LOG_PATH", "agent_loop.log")

    def initialize(self) -> None:
        # Requirement: Clear existing transcript log file at initialization, resolving path from environment or defaulting to agent_loop.log
        with open(self.transcript_file_path, "w", encoding="utf-8") as f:
            f.write("")

    def consume(self, event: runner_logger.LogEvent) -> None:
        # Requirement: Consuming a log event writes a single-line compact summary to standard output
        if event.summary:
            print(event.summary, flush=True)
        # Requirement: Consuming a log event writes an unbuffered verbose record to the transcript log file
        if event.transcript_representation:
            with open(self.transcript_file_path, "a", encoding="utf-8") as f:
                f.write(event.transcript_representation + "\n")

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RunnerLogger,
        keys=[RunnerLogger, runner_logger.RunnerLogger],
        tier="system",
    )
