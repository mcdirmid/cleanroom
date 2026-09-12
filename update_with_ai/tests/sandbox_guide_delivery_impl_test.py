"""Unit tests for sandbox_guide_delivery_impl aligned with grounding specifications."""

import unittest
from typing import Optional, Set, Tuple
from lib.file_alias import BoundFile, FileContent, UnboundFile
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from lib.node_config import NodeConfig
from lib.sandbox_guide_delivery import Guide, GuideDelivery, StepSection
from lib.sandbox_guide_delivery_impl import (
    GuideDelivery as GuideDeliveryImpl,
    __initialize__,
)
from lib.tool_provider import Response


class MockNodeConfig:
    tier = "agent_session"

    def __init__(self, guide: Optional[Guide] = None, feedback: Tuple[str, ...] = ()) -> None:
        self._guide = guide
        self._feedback = feedback

    @property
    def read_only_files(self) -> Set[BoundFile]:
        return set()

    @property
    def read_write_files(self) -> Set[BoundFile]:
        return set()

    @property
    def guide_file(self) -> Optional[UnboundFile]:
        return None

    @property
    def templates(self) -> Set[Tuple[BoundFile, FileContent]]:
        return set()

    @property
    def guide(self) -> Optional[Guide]:
        return self._guide

    @guide.setter
    def guide(self, value: Optional[Guide]) -> None:
        self._guide = value

    @property
    def blame_targets(self) -> Set[BoundFile]:
        return set()

    @property
    def feedback(self) -> Tuple[str, ...]:
        return self._feedback

    @feedback.setter
    def feedback(self, value: Tuple[str, ...]) -> None:
        self._feedback = value


class SandboxGuideDeliveryImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.node_cfg = MockNodeConfig()
        self.registry.register_instance(self.node_cfg, keys=[NodeConfig], tier="agent_session")

    def test_dataclasses(self) -> None:
        """CUJ: Instantiating StepSection and Guide records."""
        section = StepSection(index=0, title="Step 1", content="Content 1")
        self.assertEqual(section.index, 0)
        self.assertEqual(section.title, "Step 1")
        self.assertEqual(section.content, "Content 1")

        guide = Guide(summary="Guide Summary", sections=[section])
        self.assertEqual(guide.summary, "Guide Summary")
        self.assertEqual(len(guide.sections), 1)

    def test_parse_guide_and_skips_lint_checks(self) -> None:
        """CUJ: Parsing markdown guide extracts summary and sections, skipping Lint checks."""
        content = (
            "This is the summary text.\n\n"
            "## Verification failure\nCheck error logs carefully.\n\n"
            "## Step 1\nDo the first task.\n\n"
            "## Lint checks\nRun pyright and check for warnings.\n\n"
            "## Step 2\nDo the second task."
        )
        with enter_phase("agent_session", registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            parsed = delivery.parse_guide(content)

            # Requirement: Guide parsing extracts the summary from content preceding the first section heading, captures verification failure instructions when a section heading begins with `Verification failure`, and creates sequential step sections for subsequent level-two headings while excluding sections whose title begins with `Lint checks` or `Verification failure`.
            self.assertEqual(parsed.summary, "This is the summary text.")
            self.assertEqual(parsed.verification_failure, "Check error logs carefully.")
            self.assertEqual(len(parsed.sections), 2)
            self.assertEqual(parsed.sections[0].title, "Step 1")
            self.assertEqual(parsed.sections[0].content, "Do the first task.")
            self.assertEqual(parsed.sections[1].title, "Step 2")
            self.assertEqual(parsed.sections[1].content, "Do the second task.")

            plain = delivery.parse_guide("Just a guide summary without headings.")
            self.assertEqual(plain.summary, "Just a guide summary without headings.")
            self.assertIsNone(plain.verification_failure)
            self.assertEqual(len(plain.sections), 0)

    def test_advance_step_lifecycle(self) -> None:
        """CUJ: Advancing through steps with verification passing and failing."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            self.assertFalse(delivery.has_steps_remaining)
            # Requirement: When no guide is configured or no step sections remain, the guide delivery indicates that no steps remain and advancing produces no response.
            res_none = delivery.advance_step(verification_passed=True)
            self.assertIsNone(res_none)

        guide = Guide(
            summary="High-level summary",
            verification_failure="Fix failure instructions",
            sections=[
                StepSection(index=0, title="Step 1", content="Content 1"),
                StepSection(index=1, title="Step 2", content="Content 2"),
            ],
        )
        self.node_cfg._guide = guide

        with enter_phase("agent_session", registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            # Requirement: Initializing the guide delivery obtains its guide from the node config.
            # Requirement: [GuideDelivery] Steps remaining indicates whether further step sections remain to be completed.
            self.assertTrue(delivery.has_steps_remaining)
            self.assertIs(delivery.guide, guide)

            # Verification failure before any steps delivered emits summary and failure diagnostics
            # Requirement: When advancing a step with failed verification, if no step section has been delivered yet, the guide delivery retains its index and emits a response combining the guide summary, any configured verification failure instructions, and failure diagnostics.
            # Requirement: [GuideDelivery] Advancing step delivers instructional text when verification passes, or retains the current milestone and reports failure diagnostics alongside verification failure instructions when verification fails.
            res_fail0 = delivery.advance_step(verification_passed=False, failure_diagnostics="Pre-flight check failed")
            self.assertIsNotNone(res_fail0)
            assert res_fail0 is not None
            self.assertTrue(res_fail0.is_failed)
            self.assertFalse(res_fail0.is_terminated)
            self.assertIn("High-level summary", res_fail0.content)
            self.assertIn("## Verification failure\nFix failure instructions", res_fail0.content)
            self.assertTrue(delivery.has_steps_remaining)

            # Initial passing advance produces summary alone without step section
            # Requirement: When advancing a step with passed verification, if no steps have been delivered yet, the guide delivery emits a response containing the guide summary alone without delivering a step section.
            # Requirement: [GuideDelivery] Advancing step delivers instructional text when verification passes, or retains the current milestone and reports failure diagnostics alongside verification failure instructions when verification fails.
            res0 = delivery.advance_step(verification_passed=True)
            self.assertIsNotNone(res0)
            assert res0 is not None
            self.assertFalse(res0.is_failed)
            self.assertFalse(res0.is_terminated)
            self.assertEqual(res0.content, "High-level summary")
            self.assertNotIn("## Verification failure", res0.content)
            self.assertTrue(delivery.has_steps_remaining)

            # Advance to first step section
            # Requirement: When advancing a step with passed verification, if steps have already been delivered and further step sections remain, the guide delivery emits a response presenting the guide summary above the next step section content introduced by `Now check carefully:` and advances its index to that section.
            # Requirement: [GuideDelivery] Advancing step delivers instructional text when verification passes, or retains the current milestone and reports failure diagnostics alongside verification failure instructions when verification fails.
            res1 = delivery.advance_step(verification_passed=True)
            self.assertIsNotNone(res1)
            assert res1 is not None
            self.assertFalse(res1.is_failed)
            self.assertFalse(res1.is_terminated)
            self.assertIn("High-level summary", res1.content)
            self.assertIn("Step 1", res1.content)
            self.assertIn("Now check carefully:\nContent 1", res1.content)
            self.assertTrue(delivery.has_steps_remaining)

            # Verification failure while Step 1 is active retains step index and emits summary, current step, and diagnostics
            # Requirement: When advancing a step with failed verification, if a step section is currently active, the guide delivery retains the current step index without advancement and emits a response combining the guide summary, the current step section content introduced by `Now check carefully:`, any configured verification failure instructions, and the failure diagnostics.
            # Requirement: [GuideDelivery] Advancing step delivers instructional text when verification passes, or retains the current milestone and reports failure diagnostics alongside verification failure instructions when verification fails.
            res_fail1 = delivery.advance_step(verification_passed=False, failure_diagnostics="Syntax error in step 1")
            self.assertIsNotNone(res_fail1)
            assert res_fail1 is not None
            self.assertTrue(res_fail1.is_failed)
            self.assertFalse(res_fail1.is_terminated)
            self.assertIn("High-level summary", res_fail1.content)
            self.assertIn("Step 1", res_fail1.content)
            self.assertIn("Now check carefully:\nContent 1", res_fail1.content)
            self.assertIn("## Verification failure\nFix failure instructions", res_fail1.content)
            self.assertTrue(delivery.has_steps_remaining)

            # Advance to second step section
            res2 = delivery.advance_step(verification_passed=True)
            self.assertIsNotNone(res2)
            assert res2 is not None
            self.assertFalse(res2.is_failed)
            self.assertFalse(res2.is_terminated)
            self.assertIn("High-level summary", res2.content)
            self.assertIn("Step 2", res2.content)
            self.assertIn("Now check carefully:\nContent 2", res2.content)
            self.assertFalse(delivery.has_steps_remaining)

            # Subsequent advance when exhausted produces None
            res3 = delivery.advance_step(verification_passed=True)
            self.assertIsNone(res3)

    def test_has_steps_remaining_when_no_guide(self) -> None:
        """CUJ: When no guide is configured, steps remaining evaluates to false."""
        self.node_cfg._guide = None
        with enter_phase("agent_session", registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            # Requirement: Steps remaining evaluates to false once all step sections have been delivered or when no guide is configured.
            # Requirement: [GuideDelivery] Steps remaining indicates whether further step sections remain to be completed.
            self.assertFalse(delivery.has_steps_remaining)
            self.assertIsNone(delivery.advance_step(verification_passed=True))


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
