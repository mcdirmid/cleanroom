"""Runner logger implementation low-level specification."""

from framework import operation, override, singleton_type
import runner_logger


@singleton_type("system")
class RunnerLogger(runner_logger.RunnerLogger):
    """Realizes live terminal logging and unbuffered transcript file output."""

    @operation
    def initialize(self) -> None:
        """Initializes the log destination and clears previous transcripts.

        POSTCONDITIONS:
        - MUST resolve the transcript log destination from configured environment variables when present, defaulting to 'agent_loop.log'.
        - MUST clear any existing transcript log file at initialization.
        """
        ...

    @operation
    @override
    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        """Writes compact summary to terminal and unbuffered verbose entry to transcript file.

        Args:
            event: The execution event record to consume.

        POSTCONDITIONS:
        - MUST write unbuffered verbose entries to the transcript log file.
        """
        ...
