# Requirements specified in antigravity_run_logger.pyi
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AntigravityLogEvent:
    event_name: str
    source: str
    summary: str


class AntigravityRunLogger:
    def log_event(self, event_name: str, source: str, summary: str) -> None:
        raise NotImplementedError

    def register_transcript(self, identifier: str, slug: str) -> None:
        raise NotImplementedError

    def sanitize_slug(self, label: str) -> str:
        raise NotImplementedError
