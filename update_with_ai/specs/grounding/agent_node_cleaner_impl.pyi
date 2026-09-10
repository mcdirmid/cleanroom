from typing import Set
from framework import operation, override, singleton_type
import agent_conversation_history
import agent_node_cleaner
import agent_runner
import bazel_graph_storage
import dag_node_cleaner
import dag_storage
import model_config
import node_config
import sandbox

@singleton_type('system')
class AgentNodeCleaner(agent_node_cleaner.AgentNodeCleaner):
    """
PURPOSE:
Implements agent node cleaner orchestrating sandbox and agent runner

GROUNDING_ARGUMENT:
- Through the agent session phase boundary, As a system singleton, AgentNodeCleaner coordinates system singletons (bazel_graph_storage, dag_storage) in the same lifecycle. While system singletons cannot directly access narrower agent_session singletons under static lifecycle isolation, this service initiates and executes within an explicit agent session phase that instantiates and scopes session-level singletons (agent_runner, sandbox, agent_conversation_history, CleanedNode), with defining modules all imported.
"""

    @operation
    @override
    def clean_node(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        """
PURPOSE:
Cleans a dirty node within an agent session phase and returns resulting messages

FRESH_REQUIREMENTS:
- Node cleaning executes within an agent session phase, configuring the cleaned node with the dirty node.
- Node cleaning executes an agent runner with the sandbox and conversation history.
- Startup templates from the sandbox are materialized for missing read-write files.
- The conversation history is seeded with the task prompt, node definition, incoming pending messages ordered deterministically by content, and paired startup tool executions from the sandbox.
- When seeding conversation history with a task prompt for a node configured with a guide, the prompt is augmented with instructions directing the agent to call advance without arguments to view each guide step and not supply a change summary until all guide steps are complete when progressive guidance is active, or identifying the guide file by its file alias when progressive guidance is inactive.
- When the agent outcome indicates change with workspace file modifications, change messages are produced for downstream dependent nodes.
- When the agent outcome indicates blame, feedback messages are produced for the blamed dependency node.
- When the agent outcome indicates failure, the node remains dirty and no propagating messages are produced.

INHERITED_REQUIREMENTS:
- [AgentNodeCleaner] An agent node cleaner cleans a dirty node within an agent session phase.
- [AgentNodeCleaner] When workspace file modifications occur and task verification passes, the agent node cleaner produces change messages.
- [AgentNodeCleaner] When blame is signaled, the agent node cleaner produces feedback messages addressed to dependency nodes.
- [AgentNodeCleaner] When cleaning succeeds without workspace file modifications, no messages are produced.

GROUNDING_ARGUMENT:
- Receives node as an input argument and retrieves task prompt and node definition from imported bazel_graph_storage in the same system lifecycle tier. Within the orchestrated agent session phase, it configures CleanedNode, materializes startup templates from sandbox, seeds conversation history with incoming pending messages ordered deterministically by content and augmenting the task prompt with guide instructions based on imported node_config and model_config, executes agent_runner, and maps the resulting agent outcome to change or feedback messages for dag_storage, relying on the requirements of collaborator types to satisfy message generation and dirty state management.
"""
        ...

    @operation
    @override
    def clean(self, node: dag_storage.Node) -> bool:
        """
PURPOSE:
Cleans a dirty node, interacting with dag storage to deliver messages and manage dirty state, communicating whether processing should continue

INHERITED_REQUIREMENTS:
- [NodeCleaner] When cleaning a dirty node, a node cleaner interacts with dag storage to deliver messages and manages whether the node remains dirty.
- [NodeCleaner] Delivering messages delivers change messages to dependents when modifications are made, or feedback messages to dependencies when defects require revision.
- [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
- [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the node that cannot be handled by cleaning any other node.
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
- The cleaned node is configured with the node currently being cleaned within the agent session phase.

GROUNDING_ARGUMENT:
- Receives node directly as a positional parameter and configures the instance state within self.
"""
        ...
