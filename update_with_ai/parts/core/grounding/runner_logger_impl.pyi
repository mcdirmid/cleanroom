from framework import operation, override, singleton_type
import runner_logger

@singleton_type('system')
class RunnerLogger(runner_logger.RunnerLogger):
    """
PURPOSE:
Implements runner logger to write compact summaries and verbose file logs

GROUNDING_ARGUMENT:
- As a system singleton, RunnerLogger handles telemetry logging to standard output and transcript log files without external singleton service dependencies.
"""

    @operation
    def initialize(self) -> None:
        """
PURPOSE:
Clears existing transcript log file at initialization

FRESH_REQUIREMENTS:
- The runner logger clears any existing transcript log file at initialization.
- The transcript log file destination defaults to `agent_loop.log` or is resolved from configured environment variables.

GROUNDING_ARGUMENT:
- Resolves destination log paths from environment variables and clears the transcript log file via standard filesystem operations.
"""
        ...

    @operation
    @override
    def consume(self, event: runner_logger.LogEvent) -> None:
        """
PURPOSE:
Writes single-line summary to stdout and unbuffered verbose entry to transcript file

FRESH_REQUIREMENTS:
- Consuming a log event writes a single-line compact summary to standard output.
- Consuming a log event writes an unbuffered verbose record to the transcript log file.

INHERITED_REQUIREMENTS:
- [RunnerLogger] The runner logger consumes log events, writing compact single-line summaries to standard output and full verbose records to a transcript log file.

GROUNDING_ARGUMENT:
- Receives event directly as a parameter and writes single-line summaries to standard output and full verbose records to the transcript log file.
"""
        ...
