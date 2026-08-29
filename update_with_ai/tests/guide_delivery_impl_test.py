"""
Tests for the GuideDeliveryImpl implementation.

Written from the LLS (specs/low/guide_delivery_impl.md,
specs/low/guide_delivery.md, specs/low/tool_provider.md): the guide's split
into its guide summary and step sections, the step-section pointer, advance
output composition, the pre-injected session-start output, step-mode
gating, and the advance tool definition's parameters.

In step mode, the guide's content reaches the agent only through the
advance operation's outputs: the guide summary pre-injected at run start,
then one step section per passing advance. Each advance output is a
PresentedToolResult pairing the advance call with its output, with
supersedes set (the output supersedes the previous advance output, so the
guide summary is always visible and at most one step section is live). A
failing verification restates the guide summary with the reason and does
not advance the step-section pointer. When step mode is disabled, no
step-mode output is provided: the guide is a readable file, provided whole
at run start through the file machinery.
"""

import os
import shutil
import tempfile
import unittest
from typing import List, Optional

from lib.guide_delivery import GuideDeliveryConfig
from lib.guide_delivery_impl import GuideDeliveryImpl
from lib.tool_provider import (
    PresentedToolResult,
    ToolResult,
)

GUIDE = (
    "# Guide: Converting\n\n"
    "## Summary\n\n"
    "The artifact conforms to this guide.\n\n"
    "## Checklist: Imports\n\n"
    "- [ ] Imports come from the closure\n\n"
    "## Checklist: Contracts\n\n"
    "- [ ] Signatures match the LLS\n"
)


class TestGuideDeliveryImpl(unittest.TestCase):
    """Main coverage: the guide's split, the step-section pointer, advance
    output composition, the pre-injected session-start output, step-mode
    gating, and the advance tool definition's parameters."""

    def setUp(self) -> None:
        """Set up a temp workspace with a guide file in the guide format: its
        first line is `# Guide: <title>` and its first `##` heading is
        `## Summary`; the step sections follow, `## <name>`-delimited."""
        self.temp_dir = tempfile.mkdtemp()
        self.guide_path = os.path.join(self.temp_dir, "guide.md")
        with open(self.guide_path, "w", encoding="utf-8") as f:
            f.write(GUIDE)

    def _delivery(self, step_sections: bool = True,
                  guide: Optional[str] = "guide.md") -> GuideDeliveryImpl:
        """Construct a GuideDeliveryImpl with the fixture guide (its full
        path, as the composer resolves) or an override."""
        guide_real = self.guide_path if guide == "guide.md" else guide
        return GuideDeliveryImpl(GuideDeliveryConfig(
            guide=guide_real,
            step_sections_enabled=step_sections,
        ))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def _advance_def(self, delivery: GuideDeliveryImpl) -> dict:
        defs = delivery.get_tool_definitions()
        return next(d for d in defs if d["function"]["name"] == "advance")

    # ------------------------------------------------------------------
    # get_tool_definitions
    # ------------------------------------------------------------------

    def test_get_tool_definitions_returns_only_the_advance_tool(self) -> None:
        # The advance tool is the vehicle through which the guide's step-mode
        # delivery reaches the agent; it is the only tool guide_delivery
        # provides.
        delivery = self._delivery()
        names = [d["function"]["name"] for d in delivery.get_tool_definitions()]
        self.assertEqual(names, ["advance"])

    def test_advance_definition_omits_changes_while_sections_remain(self) -> None:
        # In step mode, the change-message argument is omitted while step
        # sections remain and is included when verification passes with no
        # step sections remaining (the terminating advance).
        delivery = self._delivery()
        props = self._advance_def(delivery)["function"]["parameters"]["properties"]
        self.assertNotIn("changes", props)
        # Deliver both sections (passing verifications), exhausting the
        # pointer; the definition now includes the change argument.
        delivery.get_advance_output(verification_passed=True)
        delivery.get_advance_output(verification_passed=True)
        props = self._advance_def(delivery)["function"]["parameters"]["properties"]
        self.assertIn("changes", props)

    def test_advance_definition_includes_changes_when_step_mode_disabled(self) -> None:
        # When step mode is disabled, the change argument is always included.
        delivery = self._delivery(step_sections=False)
        props = self._advance_def(delivery)["function"]["parameters"]["properties"]
        self.assertIn("changes", props)

    # ------------------------------------------------------------------
    # get_session_start_reads
    # ------------------------------------------------------------------

    def test_session_start_pre_injects_advance_with_summary(self) -> None:
        # In step mode, the guide's presentation at run start is one
        # PresentedToolResult pairing the advance call (no arguments) with
        # the guide summary and the ensure instruction, supersedes set.
        reads = self._delivery().get_session_start_reads()
        self.assertEqual(len(reads), 1)
        advance = reads[0]
        self.assertIsInstance(advance, PresentedToolResult)
        self.assertEqual(advance.name, "advance")
        self.assertEqual(advance.arguments, {})
        self.assertIn("# Guide: Converting", advance.result.content)
        self.assertIn("The artifact conforms to this guide.", advance.result.content)
        self.assertIn("Ensure the above before calling advance again.", advance.result.content)
        self.assertTrue(advance.result.supersedes)
        self.assertEqual(advance.result.note, "Guide summary")

    def test_session_start_output_contains_summary_not_sections(self) -> None:
        # The guide is split into its guide summary (the content through the
        # end of its `## Summary` section) and its step sections (the
        # `## <name>`-delimited parts after); the pre-injected run-start
        # output carries only the summary.
        advance = self._delivery().get_session_start_reads()[0]
        self.assertIn("The artifact conforms to this guide.", advance.result.content)
        self.assertNotIn("Checklist", advance.result.content)
        self.assertNotIn("Imports come from the closure", advance.result.content)

    def test_session_start_empty_when_step_mode_disabled(self) -> None:
        # When step mode is disabled, the guide is a readable file provided
        # whole at run start through the file machinery; guide_delivery
        # provides no presentation.
        self.assertEqual(self._delivery(step_sections=False).get_session_start_reads(), [])

    def test_session_start_empty_when_no_guide(self) -> None:
        # With no guide declared, there is no step-mode output even when step
        # sections are enabled.
        delivery = self._delivery(guide=None)
        self.assertEqual(delivery.get_session_start_reads(), [])

    def test_session_start_changes_no_state(self) -> None:
        # Requesting the guide's presentation changes no guide_delivery
        # state: the first passing advance still delivers section 1.
        delivery = self._delivery()
        delivery.get_session_start_reads()
        output = delivery.get_advance_output(verification_passed=True)
        assert output is not None
        self.assertIn("Checklist: Imports", output.result.content)

    # ------------------------------------------------------------------
    # get_advance_output
    # ------------------------------------------------------------------

    def test_advance_output_composes_summary_instruction_and_section(self) -> None:
        # On a passing verification with step sections remaining, the output
        # is the next step section, composed from the guide summary, the
        # ensure instruction, and the pointer's current selection.
        output = self._delivery().get_advance_output(verification_passed=True)
        assert output is not None
        self.assertIsInstance(output, PresentedToolResult)
        self.assertEqual(output.name, "advance")
        self.assertIn("The artifact conforms to this guide.", output.result.content)
        self.assertIn("Ensure the following before calling advance again:", output.result.content)
        self.assertIn("Checklist: Imports", output.result.content)
        self.assertTrue(output.result.supersedes)

    def test_advance_output_delivers_sections_in_order(self) -> None:
        # The step sections are delivered one at a time, in the guide's
        # section order.
        delivery = self._delivery()
        first = delivery.get_advance_output(verification_passed=True)
        assert first is not None
        self.assertIn("Checklist: Imports", first.result.content)
        self.assertNotIn("Checklist: Contracts", first.result.content)
        second = delivery.get_advance_output(verification_passed=True)
        assert second is not None
        self.assertIn("Checklist: Contracts", second.result.content)

    def test_advance_output_none_when_no_sections_remaining(self) -> None:
        # On a passing verification with no step sections remaining, the run
        # proceeds to the termination machinery: no step-mode output.
        delivery = self._delivery()
        delivery.get_advance_output(verification_passed=True)
        delivery.get_advance_output(verification_passed=True)
        self.assertIsNone(delivery.get_advance_output(verification_passed=True))

    def test_advance_output_none_when_step_mode_disabled(self) -> None:
        self.assertIsNone(self._delivery(step_sections=False).get_advance_output(verification_passed=True))

    def test_failing_verification_restates_summary_with_reason(self) -> None:
        # On a failing verification, the output is the restated guide summary
        # with the reason verification failed; the next step section is not
        # delivered.
        output = self._delivery().get_advance_output(
            verification_passed=False, failure_reason="lint error here"
        )
        assert output is not None
        self.assertIsInstance(output, PresentedToolResult)
        self.assertIn("The artifact conforms to this guide.", output.result.content)
        self.assertIn("lint error here", output.result.content)
        self.assertIn("Verification failed", output.result.content)
        self.assertNotIn("Checklist", output.result.content)
        self.assertTrue(output.result.supersedes)
        self.assertEqual(output.result.note, "Verification failed.")

    def test_failing_verification_does_not_advance_pointer(self) -> None:
        # A failing verification does not advance the step-section pointer:
        # the next passing verification still delivers section 1.
        delivery = self._delivery()
        delivery.get_advance_output(verification_passed=False, failure_reason="bad")
        output = delivery.get_advance_output(verification_passed=True)
        assert output is not None
        self.assertIn("Checklist: Imports", output.result.content)

    # ------------------------------------------------------------------
    # has_step_sections_remaining
    # ------------------------------------------------------------------

    def test_has_step_sections_remaining_transitions(self) -> None:
        # True while step sections remain; False once the pointer reaches the
        # end of the guide's step sections.
        delivery = self._delivery()
        self.assertTrue(delivery.has_step_sections_remaining())
        delivery.get_advance_output(verification_passed=True)
        self.assertTrue(delivery.has_step_sections_remaining())
        delivery.get_advance_output(verification_passed=True)
        self.assertFalse(delivery.has_step_sections_remaining())

    def test_has_step_sections_remaining_false_when_step_mode_disabled(self) -> None:
        self.assertFalse(self._delivery(step_sections=False).has_step_sections_remaining())

    def test_has_step_sections_remaining_false_when_no_guide(self) -> None:
        self.assertFalse(self._delivery(guide=None).has_step_sections_remaining())

    def test_no_state_persists_across_runs(self) -> None:
        # A fresh GuideDeliveryImpl for the same configuration starts with the
        # pointer at the first section: the next passing advance delivers
        # section 1 again.
        delivery1 = self._delivery()
        delivery1.get_advance_output(verification_passed=True)
        delivery1.get_advance_output(verification_passed=True)
        delivery2 = self._delivery()
        self.assertTrue(delivery2.has_step_sections_remaining())
        output = delivery2.get_advance_output(verification_passed=True)
        assert output is not None
        self.assertIn("Checklist: Imports", output.result.content)

    def test_lint_checks_section_skipped_in_step_mode(self) -> None:
        # In step mode, the `## Lint checks` section is skipped and never
        # delivered as a step section.
        guide_with_lint = os.path.join(self.temp_dir, "guide_lint.md")
        with open(guide_with_lint, "w", encoding="utf-8") as f:
            f.write(
                "# Guide: Converting\n\n"
                "## Summary\n\n"
                "Summary content here.\n\n"
                "## Checklist: Section 1\n\n"
                "- [ ] Item 1\n\n"
                "## Lint checks\n\n"
                "- [ ] Lint check 1\n\n"
                "## Checklist: Section 2\n\n"
                "- [ ] Item 2\n"
            )
        delivery = self._delivery(guide=guide_with_lint)
        # Should have exactly 2 step sections (Section 1 and Section 2), Lint checks skipped
        first = delivery.get_advance_output(verification_passed=True)
        assert first is not None
        self.assertIn("Checklist: Section 1", first.result.content)
        self.assertNotIn("Lint checks", first.result.content)

        second = delivery.get_advance_output(verification_passed=True)
        assert second is not None
        self.assertIn("Checklist: Section 2", second.result.content)
        self.assertNotIn("Lint checks", second.result.content)

        # No more sections remain
        self.assertFalse(delivery.has_step_sections_remaining())
        third = delivery.get_advance_output(verification_passed=True)
        self.assertIsNone(third)


if __name__ == "__main__":
    unittest.main()
