"""
Implementation of the LLS run_control interface.

Delegates verification to the injected verification callback when provided;
advance performs the run's verification internally (the diff of the run's
changes via the configured file_view, truncated at the diff size limit), then
sequences the step-mode output (per guide_delivery's output rule) and the
termination machinery. Provides the termination tools: the failure tool and
the blame tool (only when blame targets are configured). Per-run state only:
the diff and the verification outcome; nothing persists across runs.
"""

from typing import Any, Dict, List, Optional

from .run_control import RunControl, RunControlConfig, Blame
from .file_view import FileView
from .guide_delivery import GuideDelivery
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


# Change summaries must stay bounded so the change messages broadcast to
# dependents stay concise. A soft bound nudges one short sentence; a hard
# bound caps the message. advance() rejects a change message over the
# soft bound (with shortening guidance) up to a grace count, then accepts
# it when within the hard bound; a change message still over the hard
# bound after its grace count turns advance() into a hard failure. Pinned
# in specs/low/run_control_impl.md, Non-Concerns.
SOFT_CHANGE_SUMMARY_LENGTH = 200
HARD_CHANGE_SUMMARY_LENGTH = 500
SUMMARY_LENGTH_GRACE = 4


class RunControlImpl(RunControl):
    """
    Implementation of the LLS RunControl interface.

    Provides the termination tools (the failure tool always, the blame tool
    only when blame targets are configured), verification inside advance (a
    failing verification provides feedback, never a tool failure, and the
    session continues), the change-message machinery (the change-message
    requirement applies only to the terminating advance), and the
    feedback-pending gate (checked only when advance would otherwise signal
    successful termination without a change). Termination tools produce no
    ToolResult and never supersede an earlier result.
    """

    def __init__(self, config: RunControlConfig, file_view: FileView,
                 guide_delivery: GuideDelivery):
        """
        Initialize run control with configuration and the composed components.

        Args:
            config: Configuration object containing the verification callback,
                the feedback-pending flag, the blame targets, and the diff
                size limit.
            file_view: The file machinery (for the changed-file and diff
                information the termination rules read).
            guide_delivery: The step-mode delivery (for the step-state gating
                the advance rules consult).
        """
        self.config = config
        self.file_view = file_view
        self.guide_delivery = guide_delivery

        # Per-run change-summary rejection counters (soft/hard length bounds):
        # a summary over the soft bound is rejected up to a grace count, then
        # accepted within the hard bound; a summary over the hard bound after
        # its grace turns advance() into a hard failure. Reset on any accepted
        # summary; per-run state only (fresh run_control per run).
        self._summary_soft_rejections: int = 0
        self._summary_hard_rejections: int = 0

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return the termination tools' definitions."""
        definitions = [
            self._create_tool_definition(
                "fail",
                "Signal failed termination",
                {}
            )
        ]

        # Conditional: blame
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
                                    "target": {"type": "string", "description": "Target to blame (the virtual name of the artifact to blame — a dependency's declared source file, e.g. foo.py)"},
                                    "feedback": {"type": "string", "description": "Feedback on how to correct the target's output"}
                                },
                                "required": ["target", "feedback"],
                                "additionalProperties": False
                            },
                            "description": "Blame pairs (target, feedback), each delivered as a feedback message to the blamed artifact's owning node"
                        }
                    }
                )
            )

        return definitions

    def advance(self, changes: List[Dict[str, str]] = []) -> ToolCallOutcome:
        """Signal the run's completion: verify the run and then signal
        successful termination, or provide feedback on a failing verification.

        Verifies the run automatically: computes the diff of the run's
        changes and, when a verification callback is configured, runs it. A
        failing verification provides feedback (never a tool failure, never
        termination) and the session continues. On a passing verification (or
        no callback), requires the change message when the run changed files
        and signals successful termination. A file counts as changed only
        when its current content differs from its run-start snapshot; a run
        whose writes all net out to no change reports no change.
        """
        changes = changes or []

        # Verification runs automatically as part of advance: run the
        # configured callback (when present). A failing verification provides
        # feedback — the failure details and guidance, never the run's diff —
        # and the session continues.
        if self.config.verification_callback is not None:
            try:
                success, output = self.config.verification_callback()
            except Exception as e:
                return ToolFailure[str](f"Verification error: {str(e)}")
            if not success:
                step_output = self.guide_delivery.get_advance_output(
                    verification_passed=False, failure_reason=output
                )
                if step_output is not None:
                    # In step mode, a failing verification restates the guide
                    # summary with the reason and an instruction to correct
                    # before calling advance again; the step-section pointer
                    # does not advance.
                    return [step_output.result]
                # Outside step mode, the output is a ToolResult with the
                # failure details and guidance.
                content = (
                    (output + "\n\n" if output else "")
                    + "Verification failed; fix the reported issues by "
                    "changing files (edit_file/replace_lines) "
                    "and then call advance() again, or call blame() or "
                    "fail() to end the run."
                )
                # The feedback supersedes the earlier non-stubbed verification
                # result (an earlier advance feedback, stubbed by the agent
                # loop); the note reports only the status (pinned in
                # specs/low/run_control_impl.md), never the failure details.
                return [ToolResult(
                    content=content,
                    supersedes=True,
                    note="Verification failed.",
                )]

        # Verification passed (or no callback). In step mode, while step
        # sections remain, advance provides the next step section and the
        # session continues (no termination, no change message): the output
        # supersedes the previous advance output, so the guide summary stays
        # visible and at most one step section is live.
        if self.guide_delivery.has_step_sections_remaining():
            output = self.guide_delivery.get_advance_output(
                verification_passed=True
            )
            assert output is not None
            return [output]

        # Verification passed (or no callback): require the change message
        # when the run changed files, then signal successful termination.
        # A write may net out to no change (e.g., an edit undone by a later
        # edit): only files whose current content differs from their run-start
        # snapshot count as changed for advance's requirements and result. A
        # claimed change for a net-unchanged file is fabricated and rejected.
        effectively_changed: List[str] = []
        for file_path in self.file_view.get_changed_files():
            current = self.file_view.get_current_content(file_path)
            if current != self.file_view.get_run_start_snapshot(file_path):
                effectively_changed.append(file_path)

        if not effectively_changed:
            if changes:
                return ToolFailure[str](
                    "Cannot advance: the run wrote files but net-changed "
                    "nothing — each file's current content equals its content "
                    "at run start. Call advance() with no changes to report "
                    "no change."
                )
            if self.config.feedback_pending:
                # The run is processing feedback (per the run_control
                # contract): advance cannot terminate without a change. The
                # session continues; the agent must change files (and report
                # the change), or call blame() or fail() to end the run.
                return ToolFailure[str](
                    "Cannot advance without a change: the run is processing "
                    "feedback, so it must change files and report the change "
                    "in advance(), or call blame() or fail() to end the run."
                )
            return TerminateAgentWithSuccess(NoChangeResult())

        if not changes:
            # The run's diff is shown only here (per the run_control
            # contract): advance's verification passed, files changed, and the
            # change message is empty, so the agent sees what changed and can
            # write the change message.
            failure_message = (
                "Cannot advance: the run changed files ({changed}). Call "
                "advance(changes=[{{file, summary}}, ...]) with one entry "
                "per changed file — each summary one short sentence on "
                "what changed in that file (not how it was done) — so the "
                "next agent knows what changed, or call fail() or blame() "
                "to end the run.\n\nThe run's diff:\n{diff}"
            ).format(changed=", ".join(effectively_changed), diff=self._diff_report())
            return ToolFailure[str](failure_message)

        changed_set = set(effectively_changed)
        mentioned: set = set()
        messages: List[NodeMessage] = []
        for entry in changes:
            file_name = (entry or {}).get("file")
            summary = (entry or {}).get("summary")
            if not file_name or not summary or not summary.strip():
                return ToolFailure[str](
                    "Cannot advance: each change entry must have a "
                    "non-empty 'file' and a non-empty one-sentence "
                    "'summary' of what changed in that file."
                )
            if file_name not in changed_set:
                unknown_message = (
                    "Cannot advance: '{file}' was not changed by this run; "
                    "report only the changed files ({changed})."
                ).format(file=file_name, changed=", ".join(effectively_changed))
                return ToolFailure[str](unknown_message)
            summary_text = summary.strip()
            summary_length = len(summary_text)
            if summary_length > HARD_CHANGE_SUMMARY_LENGTH:
                if self._summary_hard_rejections >= SUMMARY_LENGTH_GRACE:
                    # The hard-limit grace is exhausted: advance() turns into
                    # a hard failure ending the run.
                    return TerminateAgentWithFailure[str](
                        f"Task failed: the change summary for '{file_name}' "
                        f"could not be shortened to the hard limit "
                        f"({HARD_CHANGE_SUMMARY_LENGTH} characters) "
                        f"after repeated attempts."
                    )
                self._summary_hard_rejections += 1
                return ToolFailure[str](
                    "Cannot advance: the summary for '{file}' is {length} "
                    "characters (max {max} — the hard limit). Shorten it to "
                    "at most {max} characters: name the parts of the file "
                    "that changed in one short sentence, dropping how it was "
                    "done, then call advance() again with the shortened "
                    "summary.".format(
                        file=file_name,
                        length=summary_length,
                        max=HARD_CHANGE_SUMMARY_LENGTH,
                    )
                )
            if summary_length > SOFT_CHANGE_SUMMARY_LENGTH:
                if self._summary_soft_rejections < SUMMARY_LENGTH_GRACE:
                    self._summary_soft_rejections += 1
                    return ToolFailure[str](
                        "Cannot advance: the summary for '{file}' is {length} "
                        "characters (aim for at most {soft}). Shorten it to "
                        "at most {soft} characters: name the parts of the "
                        "file that changed in one short sentence, so the next "
                        "agent knows what to pay attention to when updating "
                        "further artifacts, dropping how it was done, then "
                        "call advance() again with the shortened summary."
                        .format(
                            file=file_name,
                            length=summary_length,
                            soft=SOFT_CHANGE_SUMMARY_LENGTH,
                        )
                    )
                # The soft-limit grace is exhausted: accept the summary when
                # it is within the hard bound.
            # An accepted summary resets the rejection counters.
            self._summary_soft_rejections = 0
            self._summary_hard_rejections = 0
            mentioned.add(file_name)
            messages.append(NodeMessage(
                kind="change",
                text="{}: {}".format(file_name, summary_text),
            ))

        missing = changed_set - mentioned
        if missing:
            missing_message = (
                "Cannot advance: changed files not covered by the change "
                "summary ({missing}). Add one entry per changed file."
            ).format(missing=", ".join(sorted(missing)))
            return ToolFailure[str](missing_message)

        return TerminateAgentWithSuccess(ChangeResult(messages=messages))

    def _diff_report(self) -> str:
        """Diff of each changed file vs. its content at run start, truncated.

        The report is bounded by the diff size limit (config; default 1000
        chars): a larger diff is cut to its first `limit` characters, followed
        by a footer stating the truncated size and the full change counts.
        """
        import difflib

        changed_files = self.file_view.get_changed_files()
        sections: List[str] = []
        for file_path in changed_files:
            old = self.file_view.get_run_start_snapshot(file_path)
            current = self.file_view.get_current_content(file_path)
            if old is None or current is None:
                sections.append(
                    f"### {file_path}: diff unavailable (no baseline for this run)"
                )
                continue
            diff = difflib.unified_diff(
                old.splitlines(),
                current.splitlines(),
                fromfile=f"{file_path} (at run start)",
                tofile=f"{file_path} (now)",
            )
            sections.append(f"### diff for {file_path}\n" + "\n".join(diff))
        if not sections:
            return "No files were changed in this run."

        full = "\n\n".join(sections)
        limit = self.config.diff_size_limit
        if len(full) <= limit:
            return full
        lines = full.splitlines()
        additions = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        footer = (
            f"\n... diff truncated: showing {limit} of {len(full)} chars "
            f"({len(changed_files)} file(s), +{additions}/-{deletions} lines). "
            "Raise diff_size_limit to see it in full."
        )
        return full[:limit] + footer

    def fail(self) -> ToolCallOutcome:
        """End the session in failure (agent failure)."""
        return TerminateAgentWithFailure[str]("Task failed")

    def blame(self, blames: List[Any]) -> ToolCallOutcome:
        """Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs."""
        if not self.config.blame_targets:
            return ToolFailure[str]("Blame targets are not configured")

        if not blames:
            return ToolFailure[str]("Blame list must not be empty")

        parsed_blames: List[Tuple[str, str]] = []
        for b in blames:
            if isinstance(b, dict):
                t = str(b.get("target") or "")
                f = str(b.get("feedback") or "")
            elif isinstance(b, (tuple, list)) and len(b) == 2:
                t = str(b[0])
                f = str(b[1])
            else:
                t = ""
                f = ""
            parsed_blames.append((t, f))

        invalid_blames = [(t, f) for (t, f) in parsed_blames if t not in self.config.blame_targets]
        if invalid_blames:
            valid_targets = list(self.config.blame_targets.keys())
            invalid_names = [t for (t, _) in invalid_blames]
            return ToolFailure[str](
                f"Invalid blame target(s) {invalid_names}. Valid blame targets are: {valid_targets}"
            )

        # Each target is a blameable artifact's virtual name; resolve it to
        # the owning node via the configured blame targets mapping, so the
        # feedback messages are addressed to the owning nodes (NodeIds).
        return TerminateAgentWithSuccess(FeedbackResult(
            messages=[
                (self.config.blame_targets[target], NodeMessage(kind="feedback", text=feedback))
                for (target, feedback) in parsed_blames
            ],
        ))

    # Helper methods

    def _create_tool_definition(self, name: str, description: str,
                                parameters: Dict[str, Any],
                                required: Optional[List[str]] = None) -> ToolDefinition:
        """Create a tool definition in OpenAI function-calling format."""
        schema = {
            "type": "object",
            "properties": parameters,
            "additionalProperties": False,
        }
        if required:
            schema["required"] = required
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": schema,
            },
        }
