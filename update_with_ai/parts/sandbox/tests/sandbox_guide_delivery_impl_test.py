# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T04:10:39Z
# CHANGE: Verify advance_step progressing past all guide milestones and reporting recorded initial primer alongside verification diagnostics upon failure at initial step
# CODE_HASH: 1c8cdbf6f4aa
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for sandbox_guide_delivery_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import List

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config
from update_with_ai.parts.sandbox.lib import sandbox_guide_delivery, tool_provider
from update_with_ai.parts.sandbox.lib.sandbox_guide_delivery_impl import (
    GuideDelivery,
    __initialize__,
)


_PREAMBLE = "Preamble overview text."
_SUMMARY_BODY = "Summary section body text."
_STEP_ONE_CONTENT = "Perform the first milestone task."
_STEP_TWO_CONTENT = "Perform the second milestone task."
_LINT_CONTENT = "Lint checklist item."
_FAILURE_CONTENT = "Repair the reported verification failures."

_GUIDE_MARKDOWN = (
    f"{_PREAMBLE}\n"
    "\n"
    "## Summary\n"
    "\n"
    f"{_SUMMARY_BODY}\n"
    "\n"
    "## Lint checks\n"
    "\n"
    f"- [ ] {_LINT_CONTENT}\n"
    "\n"
    "## Step One\n"
    "\n"
    f"{_STEP_ONE_CONTENT}\n"
    "\n"
    "## Step Two\n"
    "\n"
    f"{_STEP_TWO_CONTENT}\n"
    "\n"
    "## Verification failure instructions\n"
    "\n"
    f"{_FAILURE_CONTENT}\n"
)


def _make_content(text: str) -> agent_file_alias.FileContent:
    return agent_file_alias.FileContent(text)


def _make_diagnostic(text: str) -> agent_node_config.VerificationDiagnostic:
    return agent_node_config.VerificationDiagnostic(text)


class SandboxGuideDeliveryImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """CUJ: Singleton resolves under both impl and interface keys; unconfigured guide is None."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            self.assertIsInstance(delivery, GuideDelivery)
            self.assertIs(scope.get_singleton(sandbox_guide_delivery.GuideDelivery), delivery)
            self.assertIsNone(delivery.guide)
            self.assertFalse(delivery.has_steps_remaining)

    def test_parse_guide_extracts_summary(self) -> None:
        """Postcondition: Summary is extracted from preamble content and 'Summary' headings."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertIsInstance(guide, agent_node_config.NodeGuide)
            self.assertIn(_PREAMBLE, guide.summary)
            self.assertIn(_SUMMARY_BODY, guide.summary)
            self.assertNotIn(_STEP_ONE_CONTENT, guide.summary)
            self.assertNotIn(_FAILURE_CONTENT, guide.summary)

    def test_parse_guide_captures_verification_failure(self) -> None:
        """Postcondition: Headings beginning with 'Verification failure' populate failure instructions."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertIsNotNone(guide.verification_failure)
            self.assertIn(_FAILURE_CONTENT, str(guide.verification_failure))

    def test_parse_guide_creates_sequential_step_sections(self) -> None:
        """Postcondition: Level-two headings other than Summary/Lint checks/Verification failure become steps."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertEqual(len(guide.sections), 2)
            first, second = guide.sections[0], guide.sections[1]
            self.assertEqual(first.title, agent_node_config.StepTitle("Step One"))
            self.assertEqual(second.title, agent_node_config.StepTitle("Step Two"))
            self.assertIn(_STEP_ONE_CONTENT, first.content)
            self.assertIn(_STEP_TWO_CONTENT, second.content)
            self.assertEqual(second.index, first.index + 1)
            titles: List[str] = [str(s.title) for s in guide.sections]
            self.assertNotIn("Summary", titles)
            self.assertNotIn("Lint checks", titles)
            for section in guide.sections:
                self.assertNotIn(_LINT_CONTENT, section.content)
                self.assertNotIn(_FAILURE_CONTENT, section.content)

    def test_guide_property_exposes_parsed_guide(self) -> None:
        """Postcondition: guide returns the configured node guide when present."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertEqual(delivery.guide, guide)

    def test_has_steps_remaining_after_parse(self) -> None:
        """Postcondition: has_steps_remaining reports remaining steps after parsing a guide with steps."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertTrue(delivery.has_steps_remaining)

    def test_record_initial_primer(self) -> None:
        """Postcondition: record_initial_primer records primer without disturbing guide progression."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            result = delivery.record_initial_primer(
                sandbox_guide_delivery.InitialPrimer("Initial primer instructions.")
            )
            self.assertIsNone(result)
            self.assertEqual(delivery.guide, guide)
            self.assertTrue(delivery.has_steps_remaining)

    def test_advance_step_passed_delivers_instructions(self) -> None:
        """Postcondition: WHEN verification passes, MUST deliver instructional text."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            response = delivery.advance_step(True, _make_diagnostic(""))
            self.assertIsNotNone(response)
            assert response is not None
            self.assertIsInstance(response, tool_provider.ToolResponse)
            self.assertFalse(response.is_failed)
            self.assertTrue(
                _STEP_ONE_CONTENT in response.content
                or _STEP_TWO_CONTENT in response.content,
                f"Expected milestone instructions in response: {response.content!r}",
            )

    def test_advance_step_passed_progresses_milestones(self) -> None:
        """Postcondition: Passing verification advances milestones until no steps remain."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            delivery.advance_step(True, _make_diagnostic(""))
            self.assertTrue(delivery.has_steps_remaining)
            delivery.advance_step(True, _make_diagnostic(""))
            self.assertFalse(delivery.has_steps_remaining)

    def test_advance_step_failed_reports_diagnostics(self) -> None:
        """Postcondition: WHEN verification fails, MUST retain milestone and report diagnostics with failure instructions."""
        diagnostic_text = "check_files: 3 lint errors detected"
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            response = delivery.advance_step(False, _make_diagnostic(diagnostic_text))
            self.assertIsNotNone(response)
            assert response is not None
            self.assertIsInstance(response, tool_provider.ToolResponse)
            self.assertIn(diagnostic_text, response.content)
            self.assertIn(_FAILURE_CONTENT, response.content)
            self.assertTrue(delivery.has_steps_remaining)

    def test_advance_step_failed_retains_milestone(self) -> None:
        """Postcondition: WHEN verification fails, MUST retain current milestone (no progression)."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            delivery.advance_step(True, _make_diagnostic(""))
            self.assertTrue(delivery.has_steps_remaining)
            delivery.advance_step(False, _make_diagnostic("failure one"))
            delivery.advance_step(False, _make_diagnostic("failure two"))
            self.assertTrue(delivery.has_steps_remaining)
            delivery.advance_step(True, _make_diagnostic(""))
            self.assertFalse(delivery.has_steps_remaining)

    def test_advance_step_past_all_milestones(self) -> None:
        """Postcondition: advance_step when progressing past all guide milestone steps upon successful verification."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            resp1 = delivery.advance_step(True, _make_diagnostic(""))
            self.assertIsNotNone(resp1)
            self.assertTrue(delivery.has_steps_remaining)
            resp2 = delivery.advance_step(True, _make_diagnostic(""))
            self.assertFalse(delivery.has_steps_remaining)
            # Progressing past all milestone steps
            resp_past = delivery.advance_step(True, _make_diagnostic(""))
            self.assertFalse(delivery.has_steps_remaining)

    def test_advance_step_initial_step_failure_reports_primer(self) -> None:
        """Postcondition: Reporting the recorded initial primer alongside verification diagnostics upon failure at the initial step."""
        primer_text = "Important initial primer: review requirements carefully."
        diag_text = "SyntaxError on initial compile"
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            delivery.record_initial_primer(sandbox_guide_delivery.InitialPrimer(primer_text))

            # Failure at initial step
            response = delivery.advance_step(False, _make_diagnostic(diag_text))
            self.assertIsNotNone(response)
            assert response is not None
            self.assertIsInstance(response, tool_provider.ToolResponse)
            self.assertIn(primer_text, response.content)
            self.assertIn(diag_text, response.content)
            self.assertIn(_FAILURE_CONTENT, response.content)
            self.assertTrue(delivery.has_steps_remaining)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
