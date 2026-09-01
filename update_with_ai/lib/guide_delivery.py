"""Guide delivery interface and progress models."""

from typing import Protocol, TypeAlias, Sequence, Optional
from dataclasses import dataclass
from .tool_provider import ToolResult

GuideSummary: TypeAlias = str
StepIndex: TypeAlias = int
StepTitle: TypeAlias = str
StepContent: TypeAlias = str


@dataclass(frozen=True)
class StepSection:
    index: StepIndex
    title: StepTitle
    content: StepContent


@dataclass(frozen=True)
class TaskGuide:
    summary: GuideSummary
    sections: Sequence[StepSection]


Guide = TaskGuide
StepDelivery: TypeAlias = ToolResult


class GuideDelivery(Protocol):
    def get_summary_delivery(self) -> StepDelivery:
        ...

    def advance_step(self, verification_passed: bool) -> Optional[StepDelivery]:
        ...

    def has_steps_remaining(self) -> bool:
        ...


class GuideDeliveryFactory(Protocol):
    def create_guide_delivery(self, guide: TaskGuide) -> GuideDelivery:
        ...
