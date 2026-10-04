"""Agent storage grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Protocol, Set
from support.lib.grounding_support import InTier, SystemTier, only_elem
from parts.dag.grounding import dag_storage

TaskPrompt = NewType("TaskPrompt", str)


@dataclass(frozen=True)
class NodeDefinition:
    """Metadata describing task prompts for a node.

    COVERED:
    - Encapsulates task_prompt attribute.
    """
    task_prompt: TaskPrompt


class AgentStorage(dag_storage.DagStorage, InTier[SystemTier], Protocol):
    """System service extending dag storage with manifest-backed node definitions and prompts."""

    def get_node_definition(self, node: dag_storage.DagNode) -> NodeDefinition:
        """
        DEFERRED:
        - MUST provide node definitions for declared nodes.
        - Deferred to refining subtype in agent_storage_impl.py (requires manifest storage).
        """
        raise NotImplementedError

    def get_task_prompt(self, node: dag_storage.DagNode) -> TaskPrompt:
        """
        COVERED:
        - MUST provide task prompts for declared nodes.
          - Condition knowledge: look up node definition via self.get_node_definition(node).
          - Consequent knowledge: return node_def.task_prompt.
        """
        node_def: NodeDefinition = self.get_node_definition(node)
        _prompt: TaskPrompt = node_def.task_prompt
        raise NotImplementedError

    def mark_dependents_dirty(self, node: dag_storage.DagNode) -> None:
        """
        COVERED:
        - MUST mark dependent nodes dirty when propagating dependencies change.
          - Condition knowledge: query dependents via self.get_dependents(node).
          - Consequent knowledge: construct ChangeMessage and record via self.add_message.        """
        dependents: Set[dag_storage.DagNode] = self.get_dependents(node)
        sample_dep: dag_storage.DagNode = only_elem(dependents)
        change_msg: dag_storage.ChangeMessage = dag_storage.ChangeMessage(
            content=dag_storage.MessageContent(f"Dependency {node.unit_address} changed")
        )
        self.add_message(change_msg, to=sample_dep)
        raise NotImplementedError
