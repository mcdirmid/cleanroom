"""Build graph storage implementation storing targets and sandbox configs."""

from typing import Dict, Sequence, Optional, List
from .dag_storage import NodeId, DagMessage, PendingMessage, NodeData
from .sandbox import SandboxConfig
from .build_graph_storage import BuildGraphStorage, NodeDefinition
from .build_message_store import BuildMessageStore


class BuildGraphStorageImpl(BuildGraphStorage):
    def __init__(self, message_store: BuildMessageStore) -> None:
        self.message_store = message_store
        self._sandbox_configs: Dict[NodeId, SandboxConfig] = {}
        self._task_prompts: Dict[NodeId, str] = {}
        self._node_definitions: Dict[NodeId, NodeDefinition] = {}
        self._deps: Dict[NodeId, List[NodeId]] = {}

    def set_sandbox_config(self, node: NodeId, config: SandboxConfig) -> None:
        self._sandbox_configs[node] = config

    def get_sandbox_config(self, node: NodeId) -> SandboxConfig:
        return self._sandbox_configs[node]

    def set_task_prompt(self, node: NodeId, prompt: str) -> None:
        self._task_prompts[node] = prompt

    def get_task_prompt(self, node: NodeId) -> Optional[str]:
        return self._task_prompts.get(node)

    def set_node_definition(self, node: NodeId, definition: NodeDefinition) -> None:
        self._node_definitions[node] = definition
        self._sandbox_configs[node] = definition.sandbox_config
        if definition.prompt:
            self._task_prompts[node] = definition.prompt

    def get_node_definition(self, node: NodeId) -> Optional[NodeDefinition]:
        if node in self._node_definitions:
            return self._node_definitions[node]
        if node in self._sandbox_configs:
            return NodeDefinition(
                sandbox_config=self._sandbox_configs[node],
                prompt=self._task_prompts.get(node),
            )
        return None

    def set_dependencies(self, node: NodeId, deps: Sequence[NodeId]) -> None:
        self._deps[node] = list(deps)

    def get_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return self._deps.get(node, [])

    def get_reverse_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return self.message_store.get_reverse_dependencies(node)

    def get_pending_messages(self, node: NodeId) -> Sequence[PendingMessage]:
        return self.message_store.get_pending_messages(node)

    def queue_pending_messages(
        self, node: NodeId, messages: Sequence[DagMessage]
    ) -> None:
        self.message_store.queue_pending_messages(node, messages)

    def clear_pending_messages(self, node: NodeId) -> None:
        self.message_store.clear_pending_messages(node)

    def record_node_data(self, node: NodeId, data: NodeData) -> None:
        self.message_store.record_node_data(node, data)

    def get_node_data(self, node: NodeId) -> Optional[NodeData]:
        return self.message_store.get_node_data(node)

    def mark_dirty(self, node: NodeId) -> None:
        self.message_store.mark_dirty(node)

    def is_dirty(self, node: NodeId) -> bool:
        return self.message_store.is_dirty(node)
