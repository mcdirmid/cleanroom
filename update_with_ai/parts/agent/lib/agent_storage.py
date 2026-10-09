# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:18:23Z
# CHANGE: Fix bare import of cross-part module dag_storage
# CODE_HASH: 6050dbfd2763
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol
from dataclasses import dataclass
import update_with_ai.parts.dag.lib.dag_storage as dag_storage

# Requirements specified in agent_storage.pyi

TaskPrompt = NewType('TaskPrompt', str)

@dataclass(frozen=True)
class NodeDefinition:
    # TODO_NodeDefinition_body
    task_prompt: TaskPrompt


class AgentStorage(dag_storage.DagStorage, Protocol):
    def get_node_definition(self, node: dag_storage.DagNode) -> NodeDefinition:
        # TODO_get_node_definition_body
        ...

    def get_task_prompt(self, node: dag_storage.DagNode) -> TaskPrompt:
        # TODO_get_task_prompt_body
        ...
