from framework import override, singleton_type
import agent_config
import dag_config

@singleton_type('system')
class McpConfig(agent_config.AgentConfig, dag_config.DagConfig):
    """
PURPOSE:
Implements agent config and dag config for Model Context Protocol execution environments

GROUNDING_ARGUMENT:
- As a system singleton, McpConfig reads parameters from ambient environment variables or falls back to standard defaults, requiring no external collaborators.
"""

    @property
    @override
    def conversation_limit(self) -> agent_config.ConversationLimit:
        """
PURPOSE:
Bound on the maximum number of model interaction turns

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides the conversation limit bounding interaction turns.

GROUNDING_ARGUMENT:
- Reads integer from CONVERSATION_LIMIT or MODEL_CONVERSATION_LIMIT environment variables, defaulting to 50.
"""
        ...

    @property
    @override
    def inject_followups(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should inject followups to execute follow-up tool calls specified by tool responses

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.

GROUNDING_ARGUMENT:
- Reads boolean from INJECT_FOLLOWUPS environment variable, defaulting to False.
"""
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should use step mode to communicate a guide progressively

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides whether the agent should use step mode to communicate a guide progressively.

GROUNDING_ARGUMENT:
- Reads boolean from STEP_MODE or CLEANROOM_STEP_MODE environment variables, defaulting to False.
"""
        ...

    @property
    @override
    def is_startup_reads(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should perform startup reads to inspect declared files at session start

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides whether the agent should perform startup reads to inspect declared files at session start.

GROUNDING_ARGUMENT:
- Reads boolean from STARTUP_READS environment variable, defaulting to False.
"""
        ...

    @property
    @override
    def edit_delta_output(self) -> bool:
        """
PURPOSE:
Indicates whether editing tools should produce delta output

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides whether editing tools should produce delta output.

GROUNDING_ARGUMENT:
- Reads boolean from EDIT_DELTA_OUTPUT environment variable, defaulting to False.
"""
        ...

    @property
    @override
    def is_mcp_mode(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should operate in mcp mode

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides whether the agent should operate in mcp mode.

GROUNDING_ARGUMENT:
- Reads boolean from MCP_MODE or CLEANROOM_MCP_MODE environment variables, defaulting to True.
"""
        ...

    @property
    @override
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        """
PURPOSE:
Bound on the maximum number of times any node can be visited during dag cleaning

INHERITED_REQUIREMENTS:
- [DagConfig] The dag config provides the node visit limit bounding node visits during graph cleaning.

GROUNDING_ARGUMENT:
- Reads integer from NODE_VISIT_LIMIT environment variable, defaulting to 500.
"""
        ...

    @property
    @override
    def batch_size(self) -> dag_config.BatchSize:
        """
PURPOSE:
Bound on the maximum number of dirty nodes of the same role processed together in an agent session

INHERITED_REQUIREMENTS:
- [DagConfig] The dag config provides the batch size bounding dirty nodes processed together in an agent session.

GROUNDING_ARGUMENT:
- Reads integer from BATCH_SIZE environment variable, defaulting to 1.
"""
        ...
