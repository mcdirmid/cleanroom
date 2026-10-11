# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:02Z
# LAST_CHANGED: 2026-10-11T03:08:11Z
# CHANGE: Ground log mechanics in local provisions and replace ungrounded JSON serialization with transcript text
# CODE_HASH: 9a1df7a50285
# SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
# --- END CLEANROOM METADATA ---

"""Runner logger implementation low-level specification."""

import sys
from framework import operation, override, singleton_type
import runner_logger


@singleton_type("system")
class RunnerLogger(runner_logger.RunnerLogger):
    """Realizes live terminal logging and unbuffered transcript file output.

    GROUNDING:
    - Implements execution logging by formatting timestamped summaries to sys.stdout
      and streaming unbuffered verbose transcript text to a transcript log file.
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
