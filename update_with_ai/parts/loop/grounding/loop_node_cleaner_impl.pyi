from typing import Sequence, Set, Self
from framework import operation, override, singleton_type
import agent_node_config
import agent_storage
import loop_node_cleaner
import dag_storage
import loop_conversation
import loop_driver
import runner_logger
import sandbox


@singleton_type('system')
class NodeCleaner(loop_node_cleaner.NodeCleaner):
    """Implements node cleaner orchestrating sandbox and loop driver.

    GROUNDING_ARGUMENT:
    - Through the agent session phase boundary, as a system singleton, NodeCleaner coordinates system singletons (agent_storage, dag_storage, runner_logger) in the same lifecycle. While system singletons cannot directly access narrower agent_session singletons under static lifecycle isolation, this service initiates and executes within an explicit agent session phase that instantiates and scopes session-level singletons (loop_driver, sandbox, loop_conversation, agent_node_config.RoleConfig), with defining modules all imported.
    """

    @operation
    def clean_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> Set[dag_storage.DagMessage]:
        """Cleans dirty nodes within an agent session phase and returns resulting messages.

        REQUIREMENTS:
        - The node cleaner cleans dirty nodes within an agent session phase where the role config presents the role of the dirty nodes to session services, logging unexpected execution failures to the runner logger and retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
        - The conversation is initialized with instructions directing the agent to call the get work tool.
        - Resolving dirty nodes produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
        - Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
        - Resolving dirty nodes produces no propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.
        - When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.

        GROUNDING_PROVISIONS:
        - action("clean_nodes", Set[dag_storage.DagMessage]): Cleans dirty nodes in session.

        GROUNDING_ARGUMENT:
        - action("clean_nodes", Self) :- action("get_node_definition", agent_storage.AgentStorage), action("set_nodes", agent_node_config.RoleConfig), action("append_message", loop_conversation.Conversation), action("run", loop_driver.LoopDriver), action("consume_log_event", runner_logger.RunnerLogger).
        """
        ...

    @operation
    @override
    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        """Cleans dirty nodes, communicating whether processing should continue.

        REQUIREMENTS:
        - Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.

        GROUNDING_PROVISIONS:
        - action("clean", bool): Cleans dirty nodes and registers dependents.

        GROUNDING_ARGUMENT:
        - action("clean", Self) :- action("clean_nodes", Self), action("register_dependent", dag_storage.DagStorage), action("add_message", dag_storage.DagStorage).
        """
        ...


@singleton_type('agent_session')
class RoleConfig(agent_node_config.RoleConfig):
    """Implements role config presenting the active role, nodes, and version.

    GROUNDING_ARGUMENT:
    - Maintains active node references, role, and version in self across the execution phase, requiring no external singleton dependencies.
    """

    @property
    @override
    def role(self) -> str:
        """Role of the agent session.

        GROUNDING_IMPLEMENTS:
        - knows("session_role", str): Tracks session role.
        """
        ...

    @property
    @override
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        """Sequence of nodes currently being cleaned in the agent session.

        GROUNDING_IMPLEMENTS:
        - knows("cleaned_nodes", Sequence[dag_storage.DagNode]): Tracks cleaned nodes.
        """
        ...

    @property
    @override
    def version(self) -> int:
        """Execution version that increments whenever the cleaned nodes change.

        GROUNDING_IMPLEMENTS:
        - knows("execution_version", int): Tracks execution version.
        """
        ...

    @operation
    def set_role(self, role: str) -> None:
        """Sets the role of the agent session.

        GROUNDING_IMPLEMENTS:
        - action("set_role", None): Configures session role.
        """
        ...

    @operation
    @override
    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Sets the nodes currently being cleaned in the agent session.

        GROUNDING_IMPLEMENTS:
        - action("set_nodes", Sequence[dag_storage.DagNode]): Configures active nodes and increments version.
        """
        ...
