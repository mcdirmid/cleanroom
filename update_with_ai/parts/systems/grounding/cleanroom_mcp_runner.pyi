from dataclasses import dataclass
from framework import data_type, operation, singleton_type
from typing import Sequence

@data_type
@dataclass(frozen=True)
class RunnerOptions:
    """Provides execution parameters for running the server.

    REQUIREMENTS:
    - A runner options record provides execution parameters for running the server, exposing a transport, a host, a port, and a batch size.

    GROUNDING_PROVISIONS:
    - knows("transport", Self)
    - knows("host", Self)
    - knows("port", Self)
    - knows("batch_size", Self)
    """

    def __init__(self, transport: str='stdio', host: str='127.0.0.1', port: int=8765, batch_size: int=10) -> None:
        ...

    @property
    def transport(self) -> str:
        ...

    @property
    def host(self) -> str:
        ...

    @property
    def port(self) -> int:
        ...

    @property
    def batch_size(self) -> int:
        ...

@singleton_type('system')
class McpRunner:
    """System service that executes the Cleanroom Model Context Protocol server.

    REQUIREMENTS:
    - The cleanroom mcp runner executes the server using runner options.
    - The cleanroom mcp runner parses command-line arguments into runner options.

    GROUNDING_PROVISIONS:
    - action("run", Self)
    - action("parse_arguments", Self)
    """

    @operation
    def run(self, options: RunnerOptions) -> None:
        ...

    @operation
    def parse_arguments(self, arguments: Sequence[str]) -> RunnerOptions:
        ...
