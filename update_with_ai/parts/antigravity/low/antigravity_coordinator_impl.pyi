# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_coordinator_impl implementation low-level specification
# CODE_HASH: 33bd72b9e8ed
# SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for antigravity_coordinator_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import antigravity_coordinator
import antigravity_ext
import subagent_coordinator


@singleton_type("agent_session")
class AntigravityCoordinatorGenerator(
    antigravity_coordinator.AntigravityCoordinatorGenerator,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes skill artifact generation, tool parameter formatting, and wake notification parsing.

    GROUNDING:
    - Realizes coordinator skill rendering conforming to antigravity_ext YAML frontmatter
      and instruction schemas, maps subagent_coordinator.RoleDispatch objects into
      antigravity_coordinator.SubagentDispatchSpec instances, and deserializes
      antigravity_coordinator.WakeNotificationMessage records from subagent output text.
    """

    @operation
    @override
    def generate_coordinator_skill(
        self,
        dir_scope: str = "",
    ) -> antigravity_coordinator.CoordinatorSkillDocument:
        """Generates the zero-execution coordinator skill document.

        GROUNDING:
        - Renders YAML frontmatter and Markdown body conforming to antigravity_ext,
          instructing the coordinator to evaluate DAG queues via CLI and dispatch roles
          via invoke_subagent while asserting that Workspace is explicitly set and never inherited.
        """
        ...

    @operation
    @override
    def format_dispatch_directive(
        self,
        dispatch: subagent_coordinator.RoleDispatch,
        model: Optional[str] = None,
    ) -> antigravity_coordinator.SubagentDispatchSpec:
        """Formats a role dispatch directive into an Antigravity tool specification.

        GROUNDING:
        - Converts subagent_coordinator.RoleDispatch parameters into an
          antigravity_coordinator.SubagentDispatchSpec instance, binding the target workspace
          path to dispatch.workspace_dir and constructing the role invocation prompt.
        """
        ...

    @operation
    @override
    def parse_wake_notification(
        self,
        message_text: str,
    ) -> antigravity_coordinator.WakeNotificationMessage:
        """Parses completion message text into a structured wake notification.

        GROUNDING:
        - Extracts JSON objects or formatted status lines from message text conforming
          to antigravity_ext, populating antigravity_coordinator.WakeNotificationMessage.
        """
        ...
