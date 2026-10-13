# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-12T12:35:00Z
# CHANGE: Present single-line event summaries to standard output without timestamps or event names
# CODE_HASH: 6879e46c3a9e
# SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Runner logger implementation low-level specification."""

import sys
from framework import operation, override, singleton_type
import runner_logger


@singleton_type("system")
class RunnerLogger(runner_logger.RunnerLogger):
    """Realizes live terminal logging and unbuffered transcript file output.

    GROUNDING:
    - Implements execution logging by writing event summaries to sys.stdout
      and streaming unbuffered verbose transcript text to a transcript log file.
    """

    @operation
    @override
    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        """Writes compact summary to terminal and unbuffered verbose entry to transcript file.

        Args:
            event: The execution event record to consume.

        GROUNDING:
        - Writes event summary text to sys.stdout and appends raw transcript
          text followed by immediate flush to ensure durability.

        POSTCONDITIONS:
        - MUST present single-line event summaries on standard output lines without timestamps or event names.
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
