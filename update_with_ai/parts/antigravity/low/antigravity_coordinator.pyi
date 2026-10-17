# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_coordinator interface low-level specification
# CODE_HASH: b31631e9f301
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for antigravity_coordinator."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import subagent_coordinator


@data_type
@dataclass(frozen=True)
class SubagentDispatchSpec:
    """Subagent dispatch payload for Antigravity invocation.

    Args:
        type_name: Subagent template type name.
        role: Subagent persona role identifier.
        prompt: Instructional task prompt.
        workspace: Absolute or relative path to the role workspace directory.
        model: Optional model tier identifier.
    """

    type_name: str
    role: str
    prompt: str
    workspace: str
    model: Optional[str] = None


@data_type
@dataclass(frozen=True)
class CoordinatorSkillDocument:
    """Coordinator skill artifact metadata and content.

    Args:
        name: Skill identifier name.
        description: Skill usage summary description.
        frontmatter: Formatted YAML frontmatter block.
        content: Complete markdown skill file content.
    """

    name: str
    description: str
    frontmatter: str
    content: str


@data_type
@dataclass(frozen=True)
class WakeNotificationMessage:
    """Parsed completion message from a role subagent turn.

    Args:
        action: Emitted action status indicator.
        role: Subagent role identifier.
        submitted_targets: Sequence of submitted target paths.
        blamed_targets: Sequence of blamed target paths.
        failure_reason: Optional diagnostic failure message.
    """

    action: str
    role: str
    submitted_targets: Sequence[str] = ()
    blamed_targets: Sequence[str] = ()
    failure_reason: Optional[str] = None


@singleton_type("agent_session")
class AntigravityCoordinatorGenerator(InTier[AgentSessionTier], Protocol):
    """Generates coordinator skills and formats Antigravity subagent dispatch directives."""

    @operation
    def generate_coordinator_skill(
        self,
        dir_scope: str = "",
    ) -> CoordinatorSkillDocument:
        """Generates the zero-execution coordinator skill document.

        POSTCONDITIONS:
        - MUST generate coordinator skill document containing YAML frontmatter and zero-execution instructions.
        - MUST require pinning subagent Workspace parameter to role workspace and prohibit workspace inheritance.
        """
        ...

    @operation
    def format_dispatch_directive(
        self,
        dispatch: subagent_coordinator.RoleDispatch,
        model: Optional[str] = None,
    ) -> SubagentDispatchSpec:
        """Formats a role dispatch directive into an Antigravity tool specification.

        POSTCONDITIONS:
        - MUST format role dispatch directive into subagent dispatch specification with workspace path pinned.
        - MUST set TypeName to cleanroom_worker and Role to dispatch.role_name.
        """
        ...

    @operation
    def parse_wake_notification(
        self,
        message_text: str,
    ) -> WakeNotificationMessage:
        """Parses completion message text into a structured wake notification.

        POSTCONDITIONS:
        - MUST parse completion message text and return structured wake notification message.
        """
        ...
