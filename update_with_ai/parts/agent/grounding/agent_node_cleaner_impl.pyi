from typing import Set
from framework import operation, override, singleton_type
import agent_conversation
import agent_driver
import agent_storage
import dag_node_cleaner
import dag_storage
import agent_node_config
import sandbox

@singleton_type('system')
class NodeCleaner(dag_node_cleaner.NodeCleaner):
    """
PURPOSE:
Implements node cleaner orchestrating sandbox and agent driver

GROUNDING_ARGUMENT:
- Through the agent session phase boundary, As a system singleton, NodeCleaner coordinates system singletons (agent_storage, dag_storage) in the same lifecycle. While system singletons cannot directly access narrower agent_session singletons under static lifecycle isolation, this service initiates and executes within an explicit agent session phase that instantiates and scopes session-level singletons (agent_driver, sandbox, agent_conversation, CleanedNode), with defining modules all imported.
"""

    @operation
    def clean_node(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        """
PURPOSE:
Cleans a dirty node within an agent session phase and returns resulting messages

FRESH_REQUIREMENTS:
- The node cleaner cleans a dirty node within an agent session phase where the cleaned node presents the node currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
- Within the agent session phase, missing read-write files materialize from sandbox startup templates.
- The conversation is initialized with startup context comprising the node definition and task prompt retrieved from graph storage for the dirty node, incoming pending messages ordered deterministically by content and formatted with their message content, and paired startup tool executions from the sandbox formatted with synthetic tool requests and captured responses.
- Incoming feedback messages are formatted as actionable instructions prefaced with directives to fix read-write target files based on the feedback.
- Task prompt instructions for a guided node include directing the agent to call advance without arguments to view each guide step and omit a change summary until all guide steps are complete when guide step mode is active.
- Task prompt instructions for a guided node include identifying the guide file by its file alias and directing the agent to call the finish tool with a change summary describing modifications when complete, or call finish without arguments if no workspace files were modified, when guide step mode is inactive.
- Resolving the dirty node produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
- Resolving the dirty node produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
- Resolving the dirty node produces no propagating messages when the outcome signals run failure, leaving the node dirty and communicating that processing cannot continue.
- When a dirty node defines no task prompt, cleaning resolves the node without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.

GROUNDING_ARGUMENT:
- Receives node as an input argument and retrieves task prompt and node definition from imported agent_storage in the same system lifecycle tier. When a dirty node defines no task prompt, it resolves without executing an agent session phase, producing change messages if incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise. Within the orchestrated agent session phase, it configures CleanedNode, materializes startup templates from sandbox, initializes conversation with incoming pending messages ordered deterministically by content and augmenting the task prompt with guide instructions based on imported agent_node_config, executes agent_driver, and maps the resulting agent outcome to change or feedback messages for dag_storage, relying on the requirements of collaborator types to satisfy message generation and dirty state management.
"""
        ...

    @operation
    @override
    def clean(self, node: dag_storage.Node) -> bool:
        """
PURPOSE:
Cleans a dirty node, communicating whether processing should continue

FRESH_REQUIREMENTS:
- Cleaning a dirty node registers the node as a dependent to its non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.

INHERITED_REQUIREMENTS:
- [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
- [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the node that cannot be handled by cleaning any other node.

GROUNDING_ARGUMENT:
- Receives node as an input argument and interacts with imported dag_storage in the same system tier to register the node as a dependent to its non-silent dependencies, deliver change messages to dependents, and deliver feedback messages to their addressed dependency node, managing dirty state.
"""
        ...

@singleton_type('agent_session')
class CleanedNode(dag_node_cleaner.CleanedNode):
    """
PURPOSE:
Implements cleaned node presenting the active node and providing configuration

GROUNDING_ARGUMENT:
- Maintains the active node reference in self.node across the execution phase, requiring no external singleton dependencies.
"""

    @property
    @override
    def node(self) -> dag_storage.Node:
        """
PURPOSE:
Target node currently being cleaned in the agent session

INHERITED_REQUIREMENTS:
- [CleanedNode] The cleaned node presents the node currently being cleaned in the agent session.

GROUNDING_ARGUMENT:
- Holds the active Node reference configured via the set_node configuration operation when the agent session phase is initiated.
"""
        ...

    @operation
    def set_node(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Sets the node currently being cleaned in the agent session

FRESH_REQUIREMENTS:
- The cleaned node presents the node currently being cleaned to session services.

GROUNDING_ARGUMENT:
- Receives node directly as a positional parameter and configures the instance state within self.
"""
        ...
