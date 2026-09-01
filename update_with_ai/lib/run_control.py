"""Run control interface and outcome tools."""

from typing import Protocol, TypeAlias, Mapping, Optional
from dataclasses import dataclass
from .tool_provider import Tool, ToolProvider
from .virtual_file_name import VirtualFileName
from .dag_storage import NodeId
from .change_summary_validator import ChangeSummary, ChangeValidator

BlameTarget: TypeAlias = VirtualFileName
BlameTargetMapping: TypeAlias = Mapping[BlameTarget, NodeId]


@dataclass(frozen=True)
class RunControlConfig:
    blame_targets: Optional[BlameTargetMapping] = None
    change_summary_required: bool = True


class RunController(ToolProvider, Protocol):
    def get_advance_tool(self) -> Tool:
        ...

    def get_fail_tool(self) -> Tool:
        ...

    def get_blame_tool(self) -> Optional[Tool]:
        ...


class RunControlFactory(Protocol):
    def create_run_control(
        self,
        config: RunControlConfig,
        change_validator: Optional[ChangeValidator] = None,
    ) -> RunController:
        ...
