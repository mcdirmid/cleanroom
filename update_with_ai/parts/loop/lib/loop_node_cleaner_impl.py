# Requirements specified in loop_node_cleaner_impl.pyi

from typing import Optional, Sequence, Set
from . import loop_conversation
from . import loop_driver
from . import loop_node_cleaner
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.sandbox.lib import sandbox
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleScope,
    Singleton,
    enter_phase,
    get_default_registry,
    get_singleton,
    system,
)


class RoleConfig(agent_node_config.RoleConfig, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._role: str = ""
        self._nodes: Sequence[dag_storage.Node] = ()
        self._version: int = 0

    @property
    def role(self) -> str:
        # Requirement: [RoleConfig] The role config provides the role of the session.
        return self._role

    @property
    def nodes(self) -> Sequence[dag_storage.Node]:
        # Requirement: [RoleConfig] The role config provides the sequence of nodes currently being cleaned in the agent session.
        return self._nodes

    @property
    def version(self) -> int:
        # Requirement: [RoleConfig] The role config provides an execution version that increments whenever the cleaned nodes change.
        return self._version

    def set_role(self, role: str) -> None:
        # Requirement: [RoleConfig] The role config can set role to configure the role of the agent session.
        self._role = role

    def set_nodes(self, nodes: Sequence[dag_storage.Node]) -> None:
        # Requirement: [RoleConfig] The role config can set nodes to configure the nodes currently being cleaned in the agent session and increment the execution version.
        self._nodes = tuple(nodes)
        if nodes:
            self._role = nodes[0].role_address
        self._version += 1


class NodeCleaner(loop_node_cleaner.NodeCleaner, Singleton):
    tier = system

    def __init__(self) -> None:
        self._last_outcome: Optional[loop_driver.LoopOutcome] = None

    def clean_nodes(
        self, nodes: Sequence[dag_storage.Node]
    ) -> Set[dag_storage.Message]:
        dirty_nodes = list(nodes)
        storage = get_singleton(agent_storage.AgentStorage)
        defns = [storage.get_node_definition(n) for n in dirty_nodes]

        # Requirement: When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.
        has_prompt = any(d is not None and bool(d.task_prompt) for d in defns)
        if not has_prompt:
            self._last_outcome = None
            has_changes = any(
                any(isinstance(m, dag_storage.Change) for m in storage.get_messages(n))
                for n in dirty_nodes
            )
            if has_changes:
                return {dag_storage.Change()}
            return set()

        role = dirty_nodes[0].role_address if dirty_nodes else ""

        def setup_session(session: LifecycleScope) -> None:
            # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the role config presents the role of the dirty nodes to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            role_config = session.get_singleton(RoleConfig)
            role_config.set_role(role)

        def _execute_session() -> Set[dag_storage.Message]:
            # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the role config presents the role of the dirty nodes to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            with enter_phase(agent_session, setup=setup_session) as session:
                hist = session.get_singleton(loop_conversation.Conversation)

                # Requirement: The conversation is initialized with instructions directing the agent to call the get work tool.
                hist.append_message(
                    loop_conversation.Message(
                        role="user",
                        content="Call get_work to retrieve your work.",
                    )
                )

                runner = session.get_singleton(loop_driver.LoopDriver)
                outcome = runner.run()
                self._last_outcome = outcome

                messages: Set[dag_storage.Message] = set()
                # Requirement: Resolving dirty nodes produces no propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.
                if not outcome.is_success:
                    return messages

                content = outcome.response.content if outcome.response else ""
                # Requirement: Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
                if content.startswith("Blamed "):
                    blame_target_str = ""
                    blame_exp = ""
                    after_blamed = content[len("Blamed ") :]
                    if ": " in after_blamed:
                        blame_target_str, blame_exp = after_blamed.split(": ", 1)
                        blame_target_str = blame_target_str.strip()
                        blame_exp = blame_exp.strip()
                    else:
                        blame_target_str = after_blamed.strip()

                    n_cfg = session.get_singleton(agent_node_config.NodeConfig)
                    blamed_node: Optional[dag_storage.Node] = None
                    for bt in n_cfg.blame_targets:
                        bt_alias = getattr(
                            bt, "relative_path", getattr(bt, "short_name", str(bt))
                        )
                        if (
                            bt_alias == blame_target_str
                            or str(bt) == blame_target_str
                        ):
                            blamed_node = bt.owning_node
                            break
                        if (
                            hasattr(bt, "owning_node")
                            and bt.owning_node is not None
                            and (
                                bt.owning_node.unit_address == blame_target_str
                                or f"{bt.owning_node.unit_address}#{bt.owning_node.role_address}"
                                == blame_target_str
                            )
                        ):
                            blamed_node = bt.owning_node
                            break

                    if blamed_node is None:
                        if "#" in blame_target_str:
                            u, r = blame_target_str.split("#", 1)
                            blamed_node = dag_storage.Node(
                                unit_address=u, role_address=r
                            )
                        else:
                            blamed_node = dag_storage.Node(
                                unit_address=blame_target_str, role_address=""
                            )

                    messages.add(
                        dag_storage.Feedback(
                            content=blame_exp or content, target=blamed_node
                        )
                    )
                else:
                    sb = session.get_singleton(sandbox.Sandbox)
                    # Requirement: Resolving dirty nodes produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
                    if sb.has_modifications:
                        messages.add(dag_storage.Change())

                return messages

        # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the role config presents the role of the dirty nodes to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
        for attempt in range(2):
            try:
                return _execute_session()
            except Exception:
                if attempt == 1:
                    raise
        return set()

    def clean(self, nodes: Sequence[dag_storage.Node]) -> bool:
        storage = get_singleton(agent_storage.AgentStorage)
        msgs = self.clean_nodes(nodes)
        if self._last_outcome is not None and not self._last_outcome.is_success:
            # Requirement: Resolving dirty nodes produces no propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.
            # Requirement: [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node.
            for node in nodes:
                if not storage.is_dirty(node):
                    storage.add_message(dag_storage.Feedback(), to=node)
            return False

        # Requirement: Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
        for node in nodes:
            storage.register_dependent(node)
            storage.clear_messages(node)

        # Requirement: Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
        for m in msgs:
            if isinstance(m, dag_storage.Change):
                for node in nodes:
                    for dependent in storage.get_dependents(node):
                        storage.add_message(m, to=dependent)
            elif isinstance(m, dag_storage.Feedback):
                if m.target is not None:
                    storage.add_message(m, to=m.target)
                else:
                    for node in nodes:
                        for dependency in storage.get_dependencies(node):
                            storage.add_message(m, to=dependency.node)

        # Requirement: [NodeCleaner] Cleaning dirty nodes communicates whether processing should continue.
        return True


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        NodeCleaner,
        keys=[NodeCleaner, loop_node_cleaner.NodeCleaner],
        tier=system,
    )
    reg.register_singleton(
        RoleConfig,
        keys=[RoleConfig, agent_node_config.RoleConfig],
        tier=agent_session,
    )
