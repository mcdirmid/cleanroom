from typing import Self
from framework import override, singleton_type
import agent_config
import dag_config


@singleton_type('system')
class McpConfig(agent_config.AgentConfig, dag_config.DagConfig):
    """Implements agent config and dag config for Model Context Protocol execution environments.

    GROUNDING_ARGUMENT:
    - As a system singleton, McpConfig reads parameters from ambient environment variables or falls back to standard defaults, requiring no external collaborators.
    """

    @property
    @override
    def conversation_limit(self) -> agent_config.ConversationLimit:
        """Bound on the maximum number of model interaction turns.

        GROUNDING_IMPLEMENTS:
        - knows("conversation_limit", agent_config.ConversationLimit): Exposes turn limit.
        """
        ...

    @property
    @override
    def inject_followups(self) -> bool:
        """Indicates whether the agent should inject followups to execute follow-up tool calls specified by tool responses.

        GROUNDING_IMPLEMENTS:
        - knows("inject_followups", bool): Exposes whether followups are injected.
        """
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """Indicates whether the agent should use step mode to communicate a guide progressively.

        GROUNDING_IMPLEMENTS:
        - knows("is_step_mode", bool): Exposes whether step mode is active.
        """
        ...

    @property
    @override
    def is_startup_reads(self) -> bool:
        """Indicates whether the agent should perform startup reads to inspect declared files at session start.

        GROUNDING_IMPLEMENTS:
        - knows("is_startup_reads", bool): Exposes whether startup reads are active.
        """
        ...

    @property
    @override
    def edit_delta_output(self) -> bool:
        """Indicates whether editing tools should produce delta output.

        GROUNDING_IMPLEMENTS:
        - knows("edit_delta_output", bool): Exposes whether editing tools produce delta output.
        """
        ...

    @property
    @override
    def is_mcp_mode(self) -> bool:
        """Indicates whether the agent should operate in mcp mode.

        GROUNDING_IMPLEMENTS:
        - knows("is_mcp_mode", bool): Exposes whether mcp mode is active.
        """
        ...

    @property
    @override
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        """Bound on the maximum number of times any node can be visited during dag cleaning.

        GROUNDING_IMPLEMENTS:
        - knows("node_visit_limit", dag_config.NodeVisitLimit): Exposes node visit limit.
        """
        ...

    @property
    @override
    def batch_size(self) -> dag_config.BatchSize:
        """Bound on the maximum number of dirty nodes of the same role processed together in an agent session.

        GROUNDING_IMPLEMENTS:
        - knows("batch_size", dag_config.BatchSize): Exposes batch size limit.
        """
        ...
