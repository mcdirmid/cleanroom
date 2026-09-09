"""Sandbox guide delivery interface and data types."""

from dataclasses import dataclass
from typing import List, Optional, Protocol
from . import file_alias, tool_provider


@dataclass(frozen=True)
class StepSection:
    index: int
    title: str
    content: str


@dataclass(frozen=True)
class Guide:
    summary: str
    sections: List[StepSection]


class GuideDelivery(Protocol):
    @property
    def has_steps_remaining(self) -> bool: ...

    def parse_guide(self, content: file_alias.FileContent) -> Guide: ...

    def advance_step(self, verification_passed: bool) -> Optional[tool_provider.Response]: ...
