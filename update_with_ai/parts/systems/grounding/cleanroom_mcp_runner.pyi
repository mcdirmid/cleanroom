from dataclasses import dataclass
from framework import data_type, operation, singleton_type
from typing import Sequence

@data_type
@dataclass(frozen=True)
class RunnerOptions:
    """
PURPOSE:
Provides execution parameters for running the server, exposing a transport, a host, a port, and a batch size.

FRESH_REQUIREMENTS:
- A runner options record provides execution parameters for running the server, exposing a transport, a host, a port, and a batch size.
"""

    def __init__(self, transport: str='stdio', host: str='127.0.0.1', port: int=8765, batch_size: int=10) -> None:
        ...

    @property
    def transport(self) -> str:
        """
PURPOSE:
Exposes configured transport mechanism
"""
        ...

    @property
    def host(self) -> str:
        """
PURPOSE:
Exposes server listening host
"""
        ...

    @property
    def port(self) -> int:
        """
PURPOSE:
Exposes server listening port
"""
        ...

    @property
    def batch_size(self) -> int:
        """
PURPOSE:
Exposes batch size limit for dirty node processing
"""
        ...

@singleton_type('system')
class McpRunner:
    """
PURPOSE:
System service that executes the Cleanroom Model Context Protocol server.
"""

    @operation
    def run(self, options: RunnerOptions) -> None:
        """
PURPOSE:
Executes the server using runner options.

FRESH_REQUIREMENTS:
- The cleanroom mcp runner executes the server using runner options.
"""
        ...

    @operation
    def parse_arguments(self, arguments: Sequence[str]) -> RunnerOptions:
        """
PURPOSE:
Parses command-line arguments into runner options.

FRESH_REQUIREMENTS:
- The cleanroom mcp runner parses command-line arguments into runner options.
"""
        ...
