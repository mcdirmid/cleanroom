# Requirements specified in cleanroom_mcp_runner.pyi
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class RunnerOptions:
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765
    batch_size: int = 10


class McpRunner(Protocol):
    def run(self, options: RunnerOptions) -> None:
        ...

    def parse_arguments(self, arguments: Sequence[str]) -> RunnerOptions:
        ...
