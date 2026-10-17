# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_coordinator interface library
# CODE_HASH: c68c051c4d86
# --- END CLEANROOM METADATA ---

"""Interface specification for antigravity_coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from support.lib.lifecycle import InTier
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from update_with_ai.parts.subagent.lib import subagent_coordinator


# Contract: SubagentDispatchSpec defines the subagent dispatch payload for Antigravity invocation.
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


# Contract: CoordinatorSkillDocument captures coordinator skill artifact metadata and content.
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


# Contract: WakeNotificationMessage captures parsed completion message from a role subagent turn.
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


# Contract: AntigravityCoordinatorGenerator generates coordinator skills and formats Antigravity subagent dispatch directives.
class AntigravityCoordinatorGenerator(InTier[AgentSessionTier], Protocol):
    """Generates coordinator skills and formats Antigravity subagent dispatch directives."""

    # Contract: AntigravityCoordinatorGenerator.generate_coordinator_skill - generates zero-execution coordinator skill document.
    def generate_coordinator_skill(
        self,
        dir_scope: str = "",
    ) -> CoordinatorSkillDocument:
        """Generates the zero-execution coordinator skill document."""
        ...

    # Contract: AntigravityCoordinatorGenerator.format_dispatch_directive - formats role dispatch directive into subagent dispatch spec with workspace path pinned.
    def format_dispatch_directive(
        self,
        dispatch: subagent_coordinator.RoleDispatch,
        model: Optional[str] = None,
    ) -> SubagentDispatchSpec:
        """Formats a role dispatch directive into an Antigravity tool specification."""
        ...

    # Contract: AntigravityCoordinatorGenerator.parse_wake_notification - parses completion message text into structured wake notification.
    def parse_wake_notification(
        self,
        message_text: str,
    ) -> WakeNotificationMessage:
        """Parses completion message text into a structured wake notification."""
        ...

