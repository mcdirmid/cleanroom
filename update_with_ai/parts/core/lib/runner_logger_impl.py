# Requirements specified in runner_logger_impl.pyi
import os
from typing import Optional
from . import runner_logger
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, system


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
