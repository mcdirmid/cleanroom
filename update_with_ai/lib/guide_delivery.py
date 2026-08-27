"""
Interface LLS: guide_delivery
Provides the guide's step-mode delivery: the guide summary at run start,
then one step section per passing advance, through the advance tool.
"""

from typing import List, Optional, Protocol
from dataclasses import dataclass
from .tool_provider import (
    PresentedToolResult,
    ToolDefinition,
)


@dataclass
class GuideDeliveryConfig:
    """Client-supplied configuration for the guide's delivery: the guide (the
    declared guide file's location — its full filesystem path, resolved by the
    composer from the guide's virtual name via the file mappings; None when no
    guide is declared) and whether step mode is enabled."""
    guide: Optional[str]
    step_sections_enabled: bool


class GuideDelivery(Protocol):
    """
    Interface for the LLS GuideDelivery.

    Provides the advance tool's definition (the vehicle through which the
    guide's step-mode delivery reaches the agent) and the step-mode outputs:
    the guide summary pre-injected at run start, then one step section per
    passing advance, each a PresentedToolResult with supersedes set (the
    output supersedes the previous advance output, so the guide summary is
    always visible and at most one step section is live). In step mode the
    guide is not readable: its content reaches the agent only through the
    advance operation's outputs.
    """

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """
        Return the advance tool's definition — the tool through which the
        guide's step-mode delivery reaches the agent. The advance tool is
        always included; its parameters follow the step state: in step mode,
        the change-message argument is omitted while step sections remain and
        is included when verification passes with no step sections remaining;
        when step mode is disabled, it is always included.

        Always succeeds.
        """
        ...

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        """
        Provide the guide's presentation at run start: in step mode, the
        pre-injected advance call carrying the guide summary and the ensure
        instruction, before the agent's first turn; when step mode is
        disabled, an empty list (the guide is a readable file, provided whole
        at run start through the file machinery). Requesting the guide's
        presentation changes no guide_delivery state.
        """
        ...

    def get_advance_output(self, verification_passed: bool,
                           failure_reason: Optional[str] = None) -> Optional[PresentedToolResult]:
        """
        Provide the advance's step-mode output: the next step section on a
        passing verification while sections remain, or the restated guide
        summary with the reason on a failing verification. Returns None when
        step mode is disabled, or verification passed with no step sections
        remaining (the run proceeds to the termination machinery).
        """
        ...

    def has_step_sections_remaining(self) -> bool:
        """
        Query whether step sections remain: whether the next advance that
        passes verification would deliver a step section rather than proceed
        to the termination machinery. Requesting changes no guide_delivery
        state.
        """
        ...
