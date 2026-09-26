from typing import Self
from framework import operation, override, singleton_type
import runner_logger


@singleton_type("system")
class RunnerLogger(runner_logger.RunnerLogger):
    """Implements runner logger to write compact summaries and verbose file logs.

    GROUNDING_ARGUMENT:
    - As a system singleton, RunnerLogger handles telemetry logging to standard output and transcript log files without external singleton service dependencies.
    """

    @operation
    def initialize(self) -> None:
        """Clears existing transcript log file at initialization.

        REQUIREMENTS:
        - The runner logger clears any existing transcript log file at initialization.
        - The transcript log file destination defaults to `agent_loop.log` or is resolved from configured environment variables.

        GROUNDING_IMPLEMENTS:
        - action("initialize_logger", None): Clears existing transcript log file at initialization.
        """
        ...

    @operation
    @override
    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        """Writes single-line summary to stdout and unbuffered verbose entry to transcript file.

        Args:
            event: The log event to record.

        REQUIREMENTS:
        - Consuming a runner log event writes a single-line compact summary to standard output.
        - Consuming a runner log event writes an unbuffered verbose record to the transcript log file.

        GROUNDING_IMPLEMENTS:
        - action("consume_log_event", runner_logger.RunnerLogEvent): Records log event to stdout and transcript log to satisfy requirements 3 and 4.
        """
        ...
