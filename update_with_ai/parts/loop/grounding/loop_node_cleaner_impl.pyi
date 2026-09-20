from typing import Sequence, Set
from framework import operation, override, singleton_type
import agent_node_config
import agent_storage
import loop_node_cleaner
import dag_storage
import loop_conversation
import loop_driver
import sandbox

@singleton_type('system')
class NodeCleaner(loop_node_cleaner.NodeCleaner):
    """
PURPOSE:
Implements node cleaner orchestrating sandbox and loop driver

GROUNDING_ARGUMENT:
- Through the agent session phase boundary, as a system singleton, NodeCleaner coordinates system singletons (agent_storage, dag_storage) in the same lifecycle. While system singletons cannot directly access narrower agent_session singletons under static lifecycle isolation, this service initiates and executes within an explicit agent session phase that instantiates and scopes session-level singletons (loop_driver, sandbox, loop_conversation, agent_node_config.RoleConfig), with defining modules all imported.
"""

    @operation
    def clean_nodes(self, nodes: Sequence[dag_storage.Node]) -> Set[dag_storage.Message]:
        """
PURPOSE:
Cleans dirty nodes within an agent session phase and returns resulting messages

FRESH_REQUIREMENTS:
- The node cleaner cleans dirty nodes within an agent session phase where the role config presents the role of the dirty nodes to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
- The conversation is initialized with instructions directing the agent to call the get work tool.
- Resolving dirty nodes produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
- Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
- Resolving dirty nodes produces no propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.
- When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.

GROUNDING_ARGUMENT:
- Receives nodes as an input argument and retrieves task prompts and node definitions from imported agent_storage in the same system lifecycle tier. When dirty nodes define no task prompt, cleaning resolves without executing an agent session phase, producing change messages if incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise. Within the orchestrated agent session phase, it configures agent_node_config.RoleConfig with the session role, initializes conversation with instructions directing the agent to call the get work tool, executes loop_driver, and maps the resulting loop outcome to change or feedback messages for dag_storage, relying on the requirements of collaborator types to satisfy message generation and dirty state management.
"""
        ...

    @operation
    @override
    def clean(self, nodes: Sequence[dag_storage.Node]) -> bool:
        """
PURPOSE:
Cleans dirty nodes, communicating whether processing should continue

FRESH_REQUIREMENTS:
- Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.

INHERITED_REQUIREMENTS:
- [NodeCleaner] A node cleaner can clean dirty nodes, communicating whether processing should continue.
- [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node; otherwise, processing continues.

GROUNDING_ARGUMENT:
- Receives nodes as an input argument and interacts with imported dag_storage in the same system tier to register the nodes as dependents to their non-silent dependencies, deliver change messages to dependents, and deliver feedback messages to their addressed dependency node, managing dirty state.
"""
        ...

@singleton_type('agent_session')
class RoleConfig(agent_node_config.RoleConfig):
    """
PURPOSE:
Implements role config presenting the active role, nodes, and version

GROUNDING_ARGUMENT:
- Maintains active node references, role, and version in self across the execution phase, requiring no external singleton dependencies.
"""

    @property
    @override
    def role(self) -> str:
        """
PURPOSE:
Role of the agent session

INHERITED_REQUIREMENTS:
- [RoleConfig] The role config provides the role of the session.

GROUNDING_ARGUMENT:
- Holds the active role configured via set_nodes or set_role when the agent session phase is initiated.
"""
        ...

    @property
    @override
    def nodes(self) -> Sequence[dag_storage.Node]:
        """
PURPOSE:
Sequence of nodes currently being cleaned in the agent session

INHERITED_REQUIREMENTS:
- [RoleConfig] The role config provides the sequence of nodes currently being cleaned in the agent session.

GROUNDING_ARGUMENT:
- Holds the active Node sequence configured via set_nodes when the agent session phase is initiated.
"""
        ...

    @property
    @override
    def version(self) -> int:
        """
PURPOSE:
Execution version that increments whenever the cleaned nodes change

INHERITED_REQUIREMENTS:
- [RoleConfig] The role config provides an execution version that increments whenever the cleaned nodes change.

GROUNDING_ARGUMENT:
- Holds the integer version incremented by set_nodes when the active nodes change.
"""
        ...

    @operation
    def set_role(self, role: str) -> None:
        """
PURPOSE:
Sets the role of the agent session

GROUNDING_ARGUMENT:
- Receives role as an input parameter and sets the role on self.
"""
        ...

    @operation
    @override
    def set_nodes(self, nodes: Sequence[dag_storage.Node]) -> None:
        """
PURPOSE:
Sets the nodes currently being cleaned in the agent session

INHERITED_REQUIREMENTS:
- [RoleConfig] The role config can set nodes to configure the nodes currently being cleaned in the agent session and increment the execution version.

GROUNDING_ARGUMENT:
- Receives nodes directly as a positional parameter, sets nodes and role on self, and increments the integer version.
"""
        ...
