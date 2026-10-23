from __future__ import annotations
from support.lib.lifecycle import Singleton, SystemTier
from typing import NewType, Protocol
from dataclasses import dataclass
import update_with_ai.parts.dag.lib.dag_storage as dag_storage

# Requirements specified in node_storage.pyi

TaskPrompt = NewType('TaskPrompt', str)

@dataclass(frozen=True)
class NodeDefinition:
    task_prompt: TaskPrompt


class AgentStorage(dag_storage.DagStorage, Singleton[SystemTier], Protocol):
    # Contract: Provides the node definition encapsulating execution config and task prompt for a declared node.
    def get_node_definition(self, node: dag_storage.DagNode) -> NodeDefinition:
        ...

    # Contract: Provides the task prompt instruction describing work required to clean a declared node.
    def get_task_prompt(self, node: dag_storage.DagNode) -> TaskPrompt:
        ...

    # Contract: Evaluates whether a node is dirty from in-band metadata and change state of non-silent dependencies.
    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:59:28Z
# CHANGE: Add the declared is_dirty narrowing member and remove the generated scaffold markers
# --- END CLEANROOM METADATA ---
