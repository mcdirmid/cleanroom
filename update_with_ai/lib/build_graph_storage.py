"""Build graph storage interface providing node sandbox configurations."""

from typing import Protocol, TypeAlias, Optional
from dataclasses import dataclass
from .dag_storage import DagStorage, NodeId
from .sandbox import SandboxConfig
from .build_agent_config import ConfigTarget

TaskPrompt: TypeAlias = str


@dataclass(frozen=True)
class NodeDefinition:
    sandbox_config: SandboxConfig
    prompt: Optional[TaskPrompt] = None
    config_target: Optional[ConfigTarget] = None


class BuildGraphStorage(DagStorage, Protocol):
    def get_sandbox_config(self, node: NodeId) -> SandboxConfig:
        ...

    def get_task_prompt(self, node: NodeId) -> Optional[TaskPrompt]:
        ...

    def get_node_definition(self, node: NodeId) -> Optional[NodeDefinition]:
        ...
