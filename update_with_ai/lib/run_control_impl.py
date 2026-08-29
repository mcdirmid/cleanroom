"""
Implementation of the LLS run_control interface.

Delegates verification to the injected verification callback when provided;
advance performs the run's verification internally, then sequences the step-mode
output and termination machinery. Delegates diff computation and change summary
validation to change_summary_validator.
"""

from typing import Any, Dict, List, Optional, Union

from .run_control import RunControl, RunControlConfig, Blame
from .file_reader import FileReader
from .file_editor import FileEditor
from .guide_delivery import GuideDelivery
from .change_summary_validator import ChangeSummaryValidator
from .tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
    ToolCallOutcome,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    ToolFailure,
)
from .dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult
from .dag_storage import NodeId, NodeMessage


class RunControlImpl(RunControl):
    """
    Implementation of the LLS RunControl interface.
    """

    def __init__(
        self,
        config: RunControlConfig,
        file_reader: FileReader,
        file_editor: FileEditor,
        guide_delivery: GuideDelivery,
        validator: Optional[ChangeSummaryValidator] = None,
    ):
        self.config = config
        self.file_reader = file_reader
        self.file_editor = file_editor
        self.guide_delivery = guide_delivery
        self.validator = validator
        self._feedback_warned: bool = False

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return the termination tools' definitions."""
        definitions = [
            self._create_tool_definition(
                "fail",
                "Signal failed termination",
                {}
            )
        ]

        if self.config.blame_targets:
            definitions.append(
                self._create_tool_definition(
                    "blame",
                    "Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs",
                    {
                        "blames": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "target": {
                                        "type": "string",
                                        "description": "Target to blame (virtual name)",
                                    },
                                    "feedback": {
                                        "type": "string",
                                        "description": "Feedback on how to correct output",
                                    },
                                },
                                "required": ["target", "feedback"],
                                "additionalProperties": False,
                            },
                            "description": "Blame pairs (target, feedback)",
                        }
                    },
                    required=["blames"],
                )
            )

        return definitions

    def advance(self, changes: List[Dict[str, str]] = []) -> ToolCallOutcome:
        changes = changes or []

        # 1. Verification callback
        if self.config.verification_callback is not None:
            try:
                success, output = self.config.verification_callback()
            except Exception as e:
                return ToolFailure[str](f"Verification error: {str(e)}")
            if not success:
                sanitized_output = self.file_reader.sanitize_paths(output) if output else ""
                step_output = self.guide_delivery.get_advance_output(
                    verification_passed=False, failure_reason=sanitized_output
                )
                if step_output is not None:
                    return [step_output.result]
                content = (
                    (sanitized_output + "\n\n" if sanitized_output else "")
                    + "Verification failed; fix the reported issues by "
                    "changing files (replace/update_lines) "
                    "and then call advance() again, or call blame() or "
                    "fail() to end the run."
                )
                return [ToolResult(
                    content=content,
                    supersedes=True,
                    note="Verification failed.",
                )]

        # 2. Step mode sections remaining
        if self.guide_delivery.has_step_sections_remaining():
            output = self.guide_delivery.get_advance_output(verification_passed=True)
            assert output is not None
            return [output]

        # 3. Change summary validation
        effectively_changed: List[str] = []
        if self.validator is not None:
            try:
                val_error = self.validator.validate_change_summaries(changes)
                if val_error is not None:
                    return val_error
            except RuntimeError as re:
                return TerminateAgentWithFailure[str](f"Task failed: {str(re)}")
            effectively_changed = self.validator.get_effective_changes()
        else:
            for file_path in self.file_editor.get_changed_files():
                current = self.file_editor.get_current_content(file_path)
                if current != self.file_editor.get_run_start_snapshot(file_path):
                    effectively_changed.append(file_path)

        if not effectively_changed:
            if changes:
                return ToolFailure[str](
                    "Cannot advance: the run wrote files but net-changed "
                    "nothing — each file's current content equals its content "
                    "at run start. Call advance() with no changes to report "
                    "no change."
                )
            if self.config.feedback_pending and not self._feedback_warned:
                self._feedback_warned = True
                return ToolFailure[str](
                    "Warning: feedback was given and not responded to with file changes. "
                    "If you believe no changes are needed, call advance() again to proceed, "
                    "or change files and report the change in advance(), or call blame() or fail() to end the run."
                )
            return TerminateAgentWithSuccess(NoChangeResult())

        if not changes:
            return ToolFailure[str](
                f"Cannot advance: the run changed files ({', '.join(effectively_changed)}). "
                "Call advance(changes=[{file, summary}, ...]) with one entry per changed file."
            )

        messages = [
            NodeMessage(
                kind="change",
                text=f"{entry.get('file', '')}: {entry.get('summary', '').strip()}",
            )
            for entry in changes
        ]
        return TerminateAgentWithSuccess(ChangeResult(messages=messages))

    def fail(self, reason: str = "") -> ToolCallOutcome:
        return TerminateAgentWithFailure[str]("Task failed")

    def blame(
        self,
        blames: Optional[List[Union[Dict[str, str], Blame]]] = None,
        targets: Optional[List[Union[Dict[str, str], Blame]]] = None,
    ) -> ToolCallOutcome:
        pairs = blames if blames is not None else targets
        if not self.config.blame_targets:
            return ToolFailure[str]("Blame is not configured for this run.")

        if not pairs:
            return ToolFailure[str]("Cannot blame: blames list must not be empty.")

        valid_targets = sorted(self.config.blame_targets.keys())
        messages: List[tuple[NodeId, NodeMessage]] = []

        for pair in pairs:
            if isinstance(pair, dict):
                target = pair.get("target", "")
                feedback = pair.get("feedback", "").strip()
            elif isinstance(pair, (tuple, list)) and len(pair) == 2:
                target = pair[0]
                feedback = pair[1].strip()
            else:
                target = ""
                feedback = ""

            if not target or not feedback:
                return ToolFailure[str](
                    "Cannot blame: each blame entry must have a non-empty 'target' and non-empty 'feedback'."
                )

            if target not in self.config.blame_targets:
                return ToolFailure[str](
                    f"Cannot blame: invalid target '{target}'. Valid blame targets: {', '.join(valid_targets)}"
                )

            owning_node = self.config.blame_targets[target]
            messages.append((owning_node, NodeMessage(kind="feedback", text=feedback)))

        return TerminateAgentWithSuccess(FeedbackResult(messages=messages))

    def _create_tool_definition(
        self,
        name: str,
        description: str,
        properties: Dict[str, Any],
        required: Optional[List[str]] = None,
    ) -> ToolDefinition:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required or [],
                    "additionalProperties": False,
                },
            },
        }
