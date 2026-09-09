from typing import Optional, Set
from . import agent_conversation_history
from . import agent_node_cleaner
from . import agent_runner
from . import bazel_graph_storage
from . import dag_node_cleaner
from . import dag_storage
from . import sandbox
from .lifecycle import LifecycleRegistry, Singleton, enter_phase, get_default_registry, get_singleton

class CleanedNode(dag_node_cleaner.CleanedNode, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._node: Optional[dag_storage.Node] = None

    @property
    def node(self) -> dag_storage.Node:
        # Invariant: Presents the node currently being cleaned in the agent session
        if self._node is None:
            raise RuntimeError("CleanedNode has not been configured with a node.")
        return self._node

    def set_node(self, node: dag_storage.Node) -> None:
        # Requirement: Configures the cleaned node with the target node in the session
        self._node = node

class AgentNodeCleaner(agent_node_cleaner.AgentNodeCleaner, Singleton):
    tier = "system"

    def __init__(self) -> None:
        pass

    def clean_node(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        # Requirement: Node cleaning executes within an agent session phase
        with enter_phase("agent_session") as session:
            # Requirement: Configures the cleaned node with the active dirty node
            cleaned_node = session.get_singleton(CleanedNode)
            cleaned_node.set_node(node)

            storage = session.get_singleton(bazel_graph_storage.BazelGraphStorage)
            defn = storage.get_node_definition(node)

            # Requirement: Materializes sandbox startup templates for missing read-write files
            sb = session.get_singleton(sandbox.Sandbox)
            sb.materialize_startup_templates()

            hist = session.get_singleton(agent_conversation_history.ConversationHistory)
            # Requirement: Seeds conversation history with task prompt and node definition
            if defn is not None and defn.task_prompt:
                hist.append_message(
                    agent_conversation_history.Message(role="user", content=str(defn.task_prompt))
                )

            # Requirement: Seeds conversation history with incoming pending messages
            for msg in storage.get_messages(node):
                hist.append_message(
                    agent_conversation_history.Message(role="user", content=f"Incoming message: {type(msg).__name__}")
                )

            # Requirement: Seeds conversation history with startup tool executions
            for i, startup_exec in enumerate(sb.get_startup_tool_executions()):
                hist.append_tool_response(
                    response=startup_exec.response,
                    tool_name=startup_exec.tool_name,
                    tool_call_id=f"startup_{i}_{startup_exec.tool_name}",
                )

            # Requirement: Executes agent runner within the session phase
            runner = session.get_singleton(agent_runner.AgentRunner)
            outcome = runner.run()

            messages: Set[dag_storage.Message] = set()
            # Requirement: When outcome indicates failure, no propagating messages are produced
            if not outcome.is_success:
                return messages

            content = outcome.response.content if outcome.response else ""
            # Requirement: Produces feedback messages when blame is indicated
            if content.startswith("Blamed "):
                messages.add(dag_storage.Feedback())
            # Requirement: Produces change messages when workspace file modifications occur
            elif sb.has_modifications:
                messages.add(dag_storage.Change())

            return messages

    def clean(self, node: dag_storage.Node) -> bool:
        storage = get_singleton(bazel_graph_storage.BazelGraphStorage)
        # Requirement: Clears prior messages before cleaning dirty node
        storage.clear_messages(node)
        msgs = self.clean_node(node)

        # Requirement: Delivers change messages to dependents and feedback to dependencies
        for m in msgs:
            if isinstance(m, dag_storage.Change):
                for dependent in storage.get_dependents(node):
                    storage.add_message(m, to=dependent)
            elif isinstance(m, dag_storage.Feedback):
                for dependency in storage.get_dependencies(node):
                    storage.add_message(m, to=dependency.node)

        # Requirement: Communicates whether DAG cleaning should continue
        return True

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AgentNodeCleaner,
        keys=[AgentNodeCleaner, agent_node_cleaner.AgentNodeCleaner, dag_node_cleaner.NodeCleaner],
        tier="system",
    )
    reg.register_singleton(
        CleanedNode,
        keys=[CleanedNode, dag_node_cleaner.CleanedNode],
        tier="agent_session",
    )
