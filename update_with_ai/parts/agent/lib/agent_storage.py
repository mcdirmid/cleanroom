from typing import Optional, Protocol, Set
from dataclasses import dataclass
from update_with_ai.parts.dag.lib import dag_storage


class TaskPrompt(str):
    pass


@dataclass(frozen=True)
class NodeDefinition:
    node: dag_storage.Node
    task_prompt: TaskPrompt


class AgentStorage(dag_storage.DagStorage, Protocol):
    def get_node_definition(
        self, node: dag_storage.Node
    ) -> Optional[NodeDefinition]: ...
