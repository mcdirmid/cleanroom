"""Runner logger implementation formatting to stdout and transcript files."""

import sys
from typing import Optional, TypeAlias
from .runner_logger import RunnerLogger, LogEvent

TranscriptPath: TypeAlias = str


class RunnerLoggerImpl(RunnerLogger):
    def __init__(self, transcript_file_path: Optional[TranscriptPath] = None) -> None:
        self.transcript_file_path = transcript_file_path or "agent_loop.log"
        try:
            with open(self.transcript_file_path, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

    def log(self, event: LogEvent) -> None:
        if event.summary:
            print(event.summary, flush=True)
        if event.transcript:
            with open(self.transcript_file_path, "a", encoding="utf-8") as f:
                f.write(event.transcript + "\n")
