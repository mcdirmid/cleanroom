from framework import operation, override, singleton_type
from typing import Sequence
import cleanroom_mcp_runner
import runner_logger
import mcp_server

@singleton_type('system')
class McpRunner(cleanroom_mcp_runner.McpRunner):
    """Realizes the cleanroom mcp runner service to parse execution parameters and launch the server.

    GROUNDING_ARGUMENT:
    - grounded_by: mcp_server.McpServer, runner_logger.RunnerLogger, cleanroom_mcp_runner.RunnerOptions
    """

    @operation
    @override
    def run(self, options: cleanroom_mcp_runner.RunnerOptions) -> None:
        """
        REQUIREMENTS:
        - Executing the runner validates runner options and executes the server using the configured transport.
        - When standard input/output transport is requested, the runner executes the server over standard input/output.
        - When Server-Sent Events transport is requested, the runner configures server host and port parameters, logs startup progress, and executes the server over Server-Sent Events.
        - The runner sets the batch size in the execution environment.

        GROUNDING_PROVISIONS:
        - action("run", None): Executes server using runner options.

        GROUNDING_ARGUMENT:
        - action("run", Self) :- action("start_server", mcp_server.McpServer), action("consume_log_event", runner_logger.RunnerLogger).
        """
        ...

    @operation
    @override
    def parse_arguments(self, arguments: Sequence[str]) -> cleanroom_mcp_runner.RunnerOptions:
        """
        REQUIREMENTS:
        - The transport resolves from `--transport`, accepting `stdio` or `sse`, defaulting to `stdio`.
        - The host resolves from `--host`, defaulting to `127.0.0.1`.
        - The port resolves from `--port` as an integer, defaulting to 8765.
        - The batch size resolves from `--batch-size` as an integer, defaulting to 10.
        - Parsing arguments signals an error when invalid or unknown options are provided.

        GROUNDING_PROVISIONS:
        - action("parse_arguments", cleanroom_mcp_runner.RunnerOptions): Parses arguments into options.

        GROUNDING_ARGUMENT:
        - action("parse_arguments", Self) :- knows("transport", cleanroom_mcp_runner.RunnerOptions), knows("host", cleanroom_mcp_runner.RunnerOptions), knows("port", cleanroom_mcp_runner.RunnerOptions), knows("batch_size", cleanroom_mcp_runner.RunnerOptions).
        """
        ...
