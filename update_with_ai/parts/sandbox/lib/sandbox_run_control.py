# Requirements specified in sandbox_run_control.pyi
from typing import Protocol, Sequence, Set
from . import tool_provider
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config


class RunController(Protocol):
    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]: ...

    @property
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]: ...


class CheckFilesTool(tool_provider.Tool, Protocol):
    pass


CheckFileTool = CheckFilesTool
RunTestsTool = CheckFilesTool


class AdvanceTool(tool_provider.Tool, Protocol):
    pass


class ResolveTool(tool_provider.Tool, Protocol):
    @property
    def resolve_target(self) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]: ...


class SubmitTool(ResolveTool, Protocol):
    @property
    def change_summary(self) -> tool_provider.Parameter[str, str]: ...


FinishTool = SubmitTool


class FailTool(ResolveTool, Protocol):
    @property
    def explanation(self) -> tool_provider.Parameter[str, str]: ...


class BlameTool(ResolveTool, Protocol):
    @property
    def blame_target(self) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]: ...

    @property
    def explanation(self) -> tool_provider.Parameter[str, str]: ...


class GetWorkTool(tool_provider.Tool, Protocol):
    @property
    def max_batch_size(self) -> tool_provider.Parameter[int, int]: ...
