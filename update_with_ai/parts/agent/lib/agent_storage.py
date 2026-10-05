# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 21902dc933a3
# --- END CLEANROOM METADATA ---

# Requirements specified in agent_storage.pyi
from dataclasses import dataclass
from typing import Protocol
from update_with_ai.parts.dag.lib import dag_storage

TaskPrompt = str


@dataclass(frozen=True)
class NodeDefinition:
    task_prompt: TaskPrompt


class AgentStorage(dag_storage.DagStorage, Protocol):
    def get_node_definition(self, node: dag_storage.DagNode) -> NodeDefinition: ...

    def get_task_prompt(self, node: dag_storage.DagNode) -> TaskPrompt: ...
