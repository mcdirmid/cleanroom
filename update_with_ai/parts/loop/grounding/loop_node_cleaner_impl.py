# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 1a638cedc342
# GROUNDING_QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

"""Loop node cleaner implementation grounding specification module."""

from __future__ import annotations
from typing import Mapping, Optional, Sequence, Set, cast
from support.lib.grounding_support import (
    InTier,
    SystemTier,
    AgentSessionTier,
    only_elem,
)
from parts.dag.grounding import dag_storage
from parts.agent.grounding import agent_file_alias, agent_node_config, agent_storage
from parts.core.grounding import runner_logger
from parts.sandbox.grounding import sandbox
from parts.loop.grounding import loop_conversation, loop_driver, loop_node_cleaner


class _RoleConfig(agent_node_config.RoleConfig, InTier[AgentSessionTier]):
    """Session-scoped role configuration backing dirty node execution."""

    def __init__(self) -> None:
        self._role: agent_node_config.RoleName = agent_node_config.RoleName("")
        self._nodes: Sequence[dag_storage.DagNode] = ()
        self._version: agent_node_config.ExecutionVersion = (
            agent_node_config.ExecutionVersion(0)
        )

    @property
    def role(self) -> agent_node_config.RoleName:
        """
        COVERED:
        - Returns role name.
        """
        _r = self._role
        raise NotImplementedError

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        """
        COVERED:
        - Returns sequence of nodes.
        """
        _n = self._nodes
        raise NotImplementedError

    @property
    def version(self) -> agent_node_config.ExecutionVersion:
        """
        COVERED:
        - Returns execution version.
        """
        _v = self._version
        raise NotImplementedError

    def set_role(self, role: agent_node_config.RoleName) -> None:
        """
        COVERED:
        - Updates role configuration with session role.
        """
        self._role = role
        raise NotImplementedError

    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """
        COVERED:
        - Updates role configuration from dirty nodes.
        """
        self._nodes = nodes
        sample_node: dag_storage.DagNode = only_elem(nodes)
        self._role = agent_node_config.RoleName(str(sample_node.role_address))
        self._version = agent_node_config.ExecutionVersion(self._version + 1)
        raise NotImplementedError


class NodeCleaner(loop_node_cleaner.NodeCleaner, InTier[SystemTier]):
    """Realizes node clean execution, session seeding, and message dispatch.

    DISCHARGED:
    - clean: Discharges session phase orchestration, prompt evaluation, blame routing, and change propagation obligations.
    """

    def __init__(self) -> None:
        self._last_outcome: Optional[loop_driver.LoopOutcome] = None

    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        """
        COVERED:
        - MUST clean dirty nodes within an agent session phase presenting the node role.
        - MUST retry the session phase once upon encountering an unexpected failure before propagating.
        - WHEN the outcome signals advancement with file modifications, MUST mark the nodes clean in graph storage with the change summary.
        - WHEN the outcome signals advancement without file modifications, MUST mark the nodes clean without advancing last changed timestamps.
        - WHEN the outcome signals blame attributed to a configured blame target, MUST deliver feedback messages strictly to the declared feedback dependency node owning the blamed file.
        - WHEN the outcome signals blame attributed to a target failing to match a configured blame target, MUST produce no propagating messages and leave nodes dirty.
        - MUST NOT deliver feedback messages to non-feedback dependencies, guides, or fixed node specifications.
        - WHEN the outcome signals run failure, MUST leave nodes dirty and return false.
        - WHEN dirty nodes define no task prompt, MUST resolve pass-through changes without establishing an agent session.
        """
        storage: agent_storage.AgentStorage = self.get_singleton(
            agent_storage.AgentStorage
        )
        logger: runner_logger.RunnerLogger = self.get_singleton(
            runner_logger.RunnerLogger
        )
        sample_node: dag_storage.DagNode = only_elem(nodes)

        # Prompt inspection knowledge
        node_def = storage.get_node_definition(sample_node)
        _has_prompt: bool = bool(node_def.task_prompt)

        # Pass-through inspection knowledge
        _existing_messages = storage.get_messages(sample_node)
        _sample_existing = only_elem(_existing_messages)
        _is_change = isinstance(_sample_existing, dag_storage.ChangeMessage)

        # Retry logging knowledge
        _err_event = runner_logger.RunnerLogEvent(
            event_name=runner_logger.EventName("session_execution_failure"),
            summary=runner_logger.EventSummary("Execution failure"),
            transcript=runner_logger.EventTranscript("Traceback details"),
        )
        logger.consume(_err_event)

        # Outcome evaluation knowledge
        sample_response = loop_driver.tool_provider.ToolResponse(
            content="Blamed upstream_unit: syntax error",
            is_failed=False,
            is_terminated=False,
        )
        outcome = loop_driver.LoopOutcome(
            response=sample_response,
            conversation=loop_conversation.ModelRequest(messages=[]),
        )
        self._last_outcome = outcome

        _is_failed: bool = outcome.response.is_failed
        _content: str = outcome.response.content
        _is_blame: bool = _content.startswith("Blamed ")

        # Configured blame target resolution knowledge
        _sample_bound_file: agent_file_alias.BoundFile = agent_file_alias.BoundFile(
            relative_path=agent_file_alias.RelativePath("spec.pyi"),
            workspace_path=agent_file_alias.file_paths.WorkspacePath(
                agent_file_alias.file_paths.PathString("parts/spec.pyi")
            ),
            owning_node=sample_node,
        )
        _node_cfg_blame_targets: Mapping[
            dag_storage.DagNode, Set[agent_file_alias.BoundFile]
        ] = {sample_node: {_sample_bound_file}}
        _sample_blame_set: Set[agent_file_alias.BoundFile] = (
            _node_cfg_blame_targets.get(sample_node, set())
        )
        _resolved_bound_file: agent_file_alias.BoundFile = only_elem(_sample_blame_set)
        _owning_node: dag_storage.DagNode = _resolved_bound_file.owning_node

        # Blame feedback strictly delivered to declared feedback dependency node owning blamed file
        feedback_msg = dag_storage.FeedbackMessage(
            content=dag_storage.MessageContent(_content),
            target=_owning_node,
        )
        storage.add_message(feedback_msg, to=_owning_node)

        # Unmatched blame produces no propagating messages and leaves nodes dirty
        _unmatched_blame: bool = True

        # Non-feedback dependencies, guides, and fixed specs receive no feedback messages
        _feedback_deps: Set[dag_storage.DagNode] = {_owning_node}
        _all_deps: Set[dag_storage.DagDependency] = storage.get_dependencies(
            sample_node
        )
        _dep_item: dag_storage.DagDependency = only_elem(_all_deps)
        _is_feedback_dep: bool = _dep_item.node in _feedback_deps

        # Advancement clean knowledge
        _advancement_with_mods: bool = True
        _advancement_without_mods: bool = False

        # Node cleanup knowledge
        storage.clear_messages(sample_node)

        _res: bool = True
        raise NotImplementedError


def __initialize__() -> None:
    """Initializes the NodeCleaner singleton in the system tier."""
    _instance: NodeCleaner = cast(NodeCleaner, None)
    _role_cfg: _RoleConfig = cast(_RoleConfig, None)
