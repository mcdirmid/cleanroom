from framework import operation, override, singleton_type
from typing import Sequence
import cleanroom_mcp_runner
import runner_logger
import mcp_server

@singleton_type('system')
class McpRunner(cleanroom_mcp_runner.McpRunner):
    """
PURPOSE:
Realizes the cleanroom mcp runner service to parse execution parameters and launch the server.

GROUNDING_ARGUMENT:
- Operates as a system singleton interacting with imported mcp_server.McpServer and runner_logger.RunnerLogger to parse parameters and execute transport loops.
"""

    @operation
    @override
    def run(self, options: cleanroom_mcp_runner.RunnerOptions) -> None:
        """
PURPOSE:
Validates runner options and starts the server using the configured transport.

FRESH_REQUIREMENTS:
- Executing the runner validates runner options and executes the server using the configured transport.
- When standard input/output transport is requested, the runner executes the server over standard input/output.
- When Server-Sent Events transport is requested, the runner configures server host and port parameters, logs startup progress, and executes the server over Server-Sent Events.
- The runner sets the batch size in the execution environment.

INHERITED_REQUIREMENTS:
- [McpRunner] The cleanroom mcp runner executes the server using runner options.

GROUNDING_ARGUMENT:
- Resolves imported mcp_server.McpServer, sets environment or parameters for host, port, and batch size, logs startup via imported runner_logger.RunnerLogger, and dispatches start with transport.
"""
        ...

    @operation
    @override
    def parse_arguments(self, arguments: Sequence[str]) -> cleanroom_mcp_runner.RunnerOptions:
        """
PURPOSE:
Parses command-line argument tokens into a runner options record.

FRESH_REQUIREMENTS:
- The transport resolves from `--transport`, accepting `stdio` or `sse`, defaulting to `stdio`.
- The host resolves from `--host`, defaulting to `127.0.0.1`.
- The port resolves from `--port` as an integer, defaulting to 8765.
- The batch size resolves from `--batch-size` as an integer, defaulting to 10.
- Parsing arguments signals an error when invalid or unknown options are provided.

INHERITED_REQUIREMENTS:
- [McpRunner] The cleanroom mcp runner parses command-line arguments into runner options.

GROUNDING_ARGUMENT:
- Uses an argument parser to validate flag parameters, converting to cleanroom_mcp_runner.RunnerOptions and raising ValueError on unhandled arguments.
"""
        ...
