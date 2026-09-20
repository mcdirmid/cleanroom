from typing import Protocol, Sequence, Set, Tuple
from . import tool_provider
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config


class RunController(Protocol):
    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]: ...

    @property
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]: ...


class AdvanceTool(tool_provider.Tool, Protocol):
    pass


class SubmitTool(tool_provider.Tool, Protocol):
    @property
    def target(self) -> tool_provider.Parameter: ...

    @property
    def change_summary(self) -> tool_provider.Parameter: ...


FinishTool = SubmitTool


class FailTool(tool_provider.Tool, Protocol):
    @property
    def target(self) -> tool_provider.Parameter: ...

    @property
    def explanation(self) -> tool_provider.Parameter: ...


class BlameTool(tool_provider.Tool, Protocol):
    @property
    def target(self) -> tool_provider.Parameter: ...

    @property
    def blame_target(self) -> tool_provider.Parameter: ...

    @property
    def explanation(self) -> tool_provider.Parameter: ...


class CheckFileTool(tool_provider.Tool, Protocol):
    @property
    def path(self) -> tool_provider.Parameter: ...

    @property
    def src(self) -> tool_provider.Parameter: ...


RunTestsTool = CheckFileTool


class GetWorkTool(tool_provider.Tool, Protocol):
    @property
    def max_batch_size(self) -> tool_provider.Parameter: ...

