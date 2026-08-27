"""
Implementation of the LLS guide_delivery interface.

Reads the declared guide's content at run start and splits it into its guide
summary and step sections; in step mode, provides the step-mode outputs
(the guide summary pre-injected at run start, then one step section per
passing advance) and the advance tool's definition. The step state (the
guide, its split, and the step-section pointer) is per-run state only.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

from .guide_delivery import GuideDelivery, GuideDeliveryConfig
from .tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
)


# The change-summary length bounds the advance tool's description mentions:
# pinned in specs/low/run_control_impl.md, Non-Concerns (soft bound 200
# characters, hard bound 500 characters). The description wording itself is
# unspecified (guide_delivery.md, Non-Concerns); the numbers are advisory.
SOFT_CHANGE_SUMMARY_LENGTH = 200
HARD_CHANGE_SUMMARY_LENGTH = 500


class GuideDeliveryImpl(GuideDelivery):
    """
    Implementation of the LLS GuideDelivery interface.

    In step mode, the guide is not readable and its content reaches the agent
    only through advance's outputs: the summary pre-injected at run start,
    then one section per passing advance. A failing verification restates the
    guide summary with the reason and does not advance the step-section
    pointer. Each advance output is composed at delivery time from the guide
    summary, the ensure instruction, and the pointer's current selection,
    with supersedes set. The step state is per-run state only.
    """

    def __init__(self, config: GuideDeliveryConfig):
        """
        Initialize the guide delivery with configuration.

        Args:
            config: Configuration object containing the guide's full path
                (None when no guide is declared) and whether step mode is
                enabled.
        """
        self.config = config
        # Step mode (per the guide_delivery contract): when step mode is
        # enabled and a guide is configured, the guide is read at run start
        # and split into its guide summary and step sections; the guide is
        # then not readable and its content reaches the agent only through
        # advance's outputs (the summary pre-injected at run start, then one
        # section per passing advance). The step state is per-run state only.
        self._step_mode: bool = bool(
            config.step_sections_enabled and config.guide
        )
        self._step_summary: str = ""
        self._step_sections: List[str] = []
        self._step_pointer: int = 0
        if self._step_mode:
            guide_real = config.guide
            if guide_real and os.path.isfile(guide_real):
                with open(guide_real, "r", encoding="utf-8") as f:
                    guide_content = f.read()
                summary, sections = self._split_guide(guide_content)
                self._step_summary = summary
                self._step_sections = sections

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return the advance tool's definition, per the current step state."""
        return [
            self._create_tool_definition(
                "advance",
                self._advance_tool_description(),
                self._advance_tool_parameters(),
            ),
        ]

    def _advance_tool_description(self) -> str:
        """The advance tool's description, per the current step state.

        In step mode, while step sections remain, the description directs the
        agent to the step-mode loop (call advance after each section); when
        verification passed with no sections remaining (the terminating
        advance), the description includes the change-message requirement.
        """
        if self._step_mode and self._step_pointer < len(self._step_sections):
            return (
                "Call advance when you have completed the current step's "
                "requirements. Advance verifies the run's changes and, when "
                "verification passes, provides the next step; when no steps "
                "remain, it signals successful termination. A failing "
                "verification returns feedback: fix the reported issues and "
                "call advance() again, or call fail() or blame() to end the "
                "run."
            )
        return (
            "Call advance when you have nothing more to do or think you are "
            "done. Advance verifies the run's changes (running the "
            "verification callback when configured) and, when verification "
            "passes, signals successful termination — requiring a change "
            "message naming the parts of each changed file when files "
            "changed. A failing verification returns feedback: fix the "
            "reported issues and call advance() again, or call fail() or "
            "blame() to end the run."
        )

    def _advance_tool_parameters(self) -> Dict[str, Any]:
        """The advance tool's parameters, per the current step state.

        In step mode, while step sections remain, the `changes` argument is
        omitted from the definition (the change message applies only to the
        terminating advance); when verification passed with no sections
        remaining, the definition includes it.
        """
        if self._step_mode and self._step_pointer < len(self._step_sections):
            return {}
        return {
            "changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "A file changed by this run"},
                        "summary": {"type": "string", "description": "One short sentence naming the parts of the file that changed, so the next agent knows what to pay attention to when updating further artifacts; not the task performed, not how it was done; aim for at most %d characters (hard limit %d)" % (SOFT_CHANGE_SUMMARY_LENGTH, HARD_CHANGE_SUMMARY_LENGTH)}
                    },
                    "required": ["file", "summary"],
                    "additionalProperties": False
                },
                "description": "Required when the run changed files: one entry per changed file, each a short sentence naming the parts of that file that changed, so the next agent knows what to pay attention to when updating further artifacts"
            }
        }

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        """The guide's presentation at run start.

        In step mode, pre-injects the advance call: the guide summary with
        the ensure instruction, presented as the first advance output. The
        result supersedes the earlier advance output (the previous step-mode
        output), so the summary is always visible and the step sections
        slide; at run start there is nothing to stub yet. When step mode is
        disabled, provides no presentation (the guide is a readable file,
        provided whole at run start through the file machinery).
        """
        if not self._step_mode:
            return []
        return [self._step_advance_output(include_section=False)]

    def get_advance_output(self, verification_passed: bool,
                           failure_reason: Optional[str] = None) -> Optional[PresentedToolResult]:
        """Provide the advance's step-mode output.

        On a failing verification: the restated guide summary with the reason
        (the step-section pointer does not advance). On a passing verification
        with step sections remaining: the next step section (the pointer
        advances). When step mode is disabled, or verification passed with no
        step sections remaining: None (the run proceeds to the termination
        machinery).
        """
        if not self._step_mode:
            return None
        if not verification_passed:
            return self._step_failure_output(failure_reason)
        if self._step_pointer < len(self._step_sections):
            output = self._step_advance_output(include_section=True)
            self._step_pointer += 1
            return output
        return None

    def has_step_sections_remaining(self) -> bool:
        """Whether the next advance that passes verification would deliver a
        step section rather than proceed to the termination machinery."""
        return self._step_mode and self._step_pointer < len(self._step_sections)

    def _step_failure_output(self, failure_reason: Optional[str]) -> PresentedToolResult:
        """The restated guide summary with the reason verification failed.

        The guide summary stays visible (each advance output supersedes the
        previous advance output); the reason is the verification callback's
        output. The next step section is not delivered and the step-section
        pointer does not advance.
        """
        content = self._step_summary
        if failure_reason:
            content += "\n\n" + failure_reason
        content += (
            "\n\n"
            "Verification failed; correct the reported issues "
            "before calling advance() again, or call blame() or "
            "fail() to end the run."
        )
        return PresentedToolResult(
            name="advance",
            arguments={},
            result=ToolResult(
                content=content,
                supersedes=True,
                note="Verification failed.",
            ),
        )

    def _step_advance_output(self, include_section: bool) -> PresentedToolResult:
        """Compose a step-mode advance output.

        The guide summary is part of every step-mode advance output, so the
        summary is always visible; the step sections slide. When a step
        section is presented, the output carries the summary, the ensure
        instruction for the section, and the section itself; otherwise it
        carries the summary and the ensure instruction for the summary only.
        The output's result supersedes the earlier advance output (the
        consuming agent loop stubs it), so at most one step section is live
        alongside the summary.
        """
        parts: List[str] = [self._step_summary]
        if include_section and self._step_pointer < len(self._step_sections):
            parts.append(self._step_instruction(with_section=True))
            parts.append(self._step_sections[self._step_pointer])
        else:
            parts.append(self._step_instruction(with_section=False))
        return PresentedToolResult(
            name="advance",
            arguments={},
            result=ToolResult(
                content="\n\n".join(parts),
                supersedes=True,
                note=(
                    f"Guide summary"
                    if not include_section
                    else f"Step {self._step_pointer + 1} of {len(self._step_sections)}"
                ),
            ),
        )

    def _step_instruction(self, with_section: bool) -> str:
        """The ensure instruction for a step-mode advance output.

        The exact wording is implementation-pinned (the guide_delivery
        contract leaves it unspecified): when a step section is presented,
        direct the agent to ensure that section's requirements before
        advancing; when only the summary is presented, direct the agent to
        ensure the summary's requirements before advancing.
        """
        if with_section:
            return (
                "Ensure the following before calling advance again:"
            )
        return "Ensure the above before calling advance again."

    @staticmethod
    def _split_guide(content: str) -> Tuple[str, List[str]]:
        """Split a guide's content into its guide summary and step sections.

        The guide summary is the content from the guide's first line through
        the end of its `## Summary` section (the guide's first `##` heading);
        each step section is a `## <name>`-delimited part of the guide after
        the summary, in the guide's section order.
        """
        lines = content.split("\n")
        headings = [
            i for i, line in enumerate(lines) if line.startswith("## ")
        ]
        if not headings:
            return content, []
        summary_end = headings[1] if len(headings) > 1 else len(lines)
        summary = "\n".join(lines[:summary_end])
        sections: List[str] = []
        for idx in range(1, len(headings)):
            start = headings[idx]
            end = headings[idx + 1] if idx + 1 < len(headings) else len(lines)
            sections.append("\n".join(lines[start:end]))
        return summary, sections

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
