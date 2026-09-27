# Requirements specified in antigravity_run_logger.pyi
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class AntigravityLogEvent:
    event_name: str
    source: str
    summary: str


class AntigravityRunLogger(Protocol):
    def log_event(self, event_name: str, source: str, summary: str) -> None: ...

    def register_transcript(self, identifier: str, slug: str) -> None: ...

    def sanitize_slug(self, label: str) -> str: ...
