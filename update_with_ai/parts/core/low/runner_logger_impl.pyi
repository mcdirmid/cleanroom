# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-06T12:45:00Z
# CHANGE: add grounding sections
# CODE_HASH: e705ed6a816c
# --- END CLEANROOM METADATA ---

"""Runner logger implementation low-level specification."""

from framework import operation, override, singleton_type
import runner_logger


@singleton_type("system")
class RunnerLogger(runner_logger.RunnerLogger):
    """Realizes live terminal logging and unbuffered transcript file output.

    GROUNDING:
    - Implements execution logging by formatting timestamped summaries to stdout
      and streaming unbuffered JSON-serialized event records to a transcript log file.
    """

    @operation
    @override
    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        """Writes compact summary to terminal and unbuffered verbose entry to transcript file.

        Args:
            event: The execution event record to consume.

        GROUNDING:
        - Formats timestamp and event name to sys.stdout and appends raw transcript
          text followed by immediate flush to ensure durability.

        POSTCONDITIONS:
        - MUST format single-line summaries with timestamps on standard output lines.
        - MUST include event names on standard output lines for live terminal visibility.
        - MUST append verbose records to transcript log entries.
        - MUST flush transcript log entries immediately after each write.
        - MUST guarantee unbuffered persistence across unexpected crashes through immediate flushing.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for runner logger implementation.

    GROUNDING:
    - Resolves log file path from environment and truncates file at startup.

    POSTCONDITIONS:
    - MUST truncate the transcript log file at opening.
    - MUST default the transcript log file destination to 'agent_loop.log'.
    - MUST resolve the transcript log file destination from configured environment variables when present.
    """
    ...
