# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-11T04:59:28Z
# CHANGE: Add the declared is_dirty narrowing member and remove the generated scaffold markers
# CODE_HASH: 104647daf01b
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol
from dataclasses import dataclass
import update_with_ai.parts.dag.lib.dag_storage as dag_storage

# Requirements specified in agent_storage.pyi

TaskPrompt = NewType('TaskPrompt', str)

@dataclass(frozen=True)
class NodeDefinition:
    task_prompt: TaskPrompt


class AgentStorage(dag_storage.DagStorage, Protocol):
    def get_node_definition(self, node: dag_storage.DagNode) -> NodeDefinition:
        ...

    def get_task_prompt(self, node: dag_storage.DagNode) -> TaskPrompt:
        ...

    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        ...
