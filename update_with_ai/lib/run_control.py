"""
Interface LLS: run_control
Provides the verification and termination rules: the failure and blame tools,
verification inside advance, the change-message machinery, and the
feedback-pending gate.
"""

from typing import Callable, Dict, List, Optional, Protocol, Tuple
from dataclasses import dataclass
from .tool_provider import (
    TerminateAgentWithFailure,
    TerminateAgentWithSuccess,
    TerminateSuccessResult,
    ToolCallOutcome,
    ToolDefinition,
    ToolFailure,
    T_tool,
)
from .dag_storage import NodeId, NodeMessage
from .dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult
from .file_view import VirtualName


# Type definitions
# Blame targets map each blameable artifact's virtual name (a dependency's
# declared source file) to the node that owns it; run_control resolves a
# blame target to its owning node before forming the feedback result (see
# specs/low/run_control.md).
BlameTargets = Dict[VirtualName, NodeId]
BlameTarget = VirtualName
Feedback = str
Blame = Tuple[BlameTarget, Feedback]
# A verification callback runs a shell command and returns (success, output):
# success is True when the command exited 0. run_control uses the success
# flag to gate advance()'s termination (see specs/low/run_control.md).
VerificationCallback = Optional[Callable[[], Tuple[bool, str]]]
DiffSizeLimit = int


@dataclass
class RunControlConfig:
    """Client-supplied configuration for verification and termination: an
    optional verification callback (its success flag gates advance; it may
    only modify the node's lib/test BUILD file, which is not among the
    workspace's files), whether the run's pending messages include a feedback
    message, the blame targets (a mapping from each blameable artifact's
    virtual name to the node that owns it), and the diff size limit (the
    maximum characters a verification diff may report; default 1000)."""
    verification_callback: VerificationCallback
    feedback_pending: bool
    blame_targets: BlameTargets
    diff_size_limit: DiffSizeLimit = 1000


class RunControl(Protocol):
    """
    Interface for the LLS RunControl.

    Provides the termination tools (the failure tool always, the blame tool
    only when blame targets are configured), verification inside advance (a
    failing verification provides feedback, never a tool failure, and the
    session continues), the change-message machinery (the change-message
    requirement applies only to the terminating advance), and the
    feedback-pending gate (checked only when advance would otherwise signal
    successful termination without a change). Termination tools produce no
    ToolResult and never supersede an earlier result.
    """

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """
        Return the termination tools' definitions: the failure tool (always)
        and the blame tool (only when blame targets are configured). The
        advance tool's definition is provided by guide_delivery (its
        parameters follow the step state); it is not among run_control's
        definitions.

        Always succeeds.
        """
        ...

    def advance(self, changes: List[Dict[str, str]] = []) -> ToolCallOutcome:
        """
        Signal the run's completion: verify the run and then signal
        successful termination, or provide feedback on a failing verification.

        Verifies the run automatically: computes the diff of the run's
        changes (truncated when it exceeds the diff size limit) and, when a
        verification callback is configured, runs it. A failing verification
        provides feedback (never a tool failure, never termination) and the
        session continues; in step mode, the output is the restated guide
        summary with the reason (per guide_delivery's output rule); outside
        step mode, the output is a ToolResult carrying the verification
        failure details and guidance. On a passing verification (or no
        callback): in step mode with step sections remaining, delivers the
        next step section (per guide_delivery's output rule); with no step
        sections remaining, proceeds to the termination machinery.

        Args:
            changes: One entry per changed file — {"file": <virtual path>,
                "summary": one short sentence naming the parts of the file
                that changed for the next reader; not the task performed, not
                how it was done}. Required when the run changed files; a
                missing, malformed, or incomplete summary signals a
                ToolFailure.

        Returns:
            On a failing verification: a ToolResult with the feedback (the
            session continues). On a passing verification:
            TerminateAgentWithSuccess carrying a TerminateSuccessResult (no
            change, or change when the run changed files). Termination tools
            produce no ToolResult and never supersede an earlier result; the
            change-message requirement applies only to the terminating
            advance.
        """
        ...

    def fail(self) -> ToolCallOutcome:
        """
        End the session in failure (agent failure).

        Returns:
            TerminateAgentWithFailure[T_tool]. A correctly-invoked fail is
            not a ToolFailure (ToolFailure signals a failed tool call).
            Termination tools produce no ToolResult and never supersede an earlier
            update.
        """
        ...

    def blame(self, blames: List[Blame]) -> ToolCallOutcome:
        """
        Signal termination with blame: attribute the task's incompleteness to
        dependencies and provide feedback on how to correct their outputs.

        Args:
            blames: List of (target, feedback) pairs; each target is the
                    virtual name of a blameable artifact (a dependency's
                    declared source file), and each pair is one feedback
                    message to that artifact's owning node.

        Returns:
            TerminateAgentWithSuccess carrying a TerminateSuccessResult (the
            implementation resolves each target to its owning node and forms a
            feedback result from the pairs) if all pairs are valid, or
            ToolFailure[T_tool] if any target is invalid. Termination tools
            produce no ToolResult and never supersede an earlier update.

        Preconditions:
            Blame targets must be configured and non-empty.
            Each pair's target must be a key of blame_targets.
        """
        ...
