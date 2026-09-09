"""Unit tests for sandbox_guide_delivery_impl aligned with grounding specifications."""

import unittest
from typing import Optional, Set, Tuple
from lib.file_alias import BoundFile, FileContent, UnboundFile
from lib.lifecycle import LifecycleRegistry, enter_phase
from lib.node_config import NodeConfig
from lib.sandbox_guide_delivery import Guide, GuideDelivery, StepSection
from lib.sandbox_guide_delivery_impl import (
    GuideDelivery as GuideDeliveryImpl,
    __initialize__,
)
from lib.tool_provider import Response


class MockNodeConfig:
    tier = "agent_session"

    def __init__(self, guide: Optional[Guide] = None) -> None:
        self._guide = guide

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

    @property
    def blame_targets(self) -> Set[BoundFile]:
        return set()


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
            "## Step 1\nDo the first task.\n\n"
            "## Lint checks\nRun pyright and check for warnings.\n\n"
            "## Step 2\nDo the second task."
        )
        with enter_phase("agent_session", registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            parsed = delivery.parse_guide(content)

            # Requirement: Guide parsing extracts the summary from content preceding the first section heading and excludes sections whose title begins with `Lint checks`.
            # Requirement: [GuideDelivery] Parsing file content extracts the summary from content preceding the first section heading and excludes sections whose title begins with `Lint checks`.
            self.assertEqual(parsed.summary, "This is the summary text.")
            self.assertEqual(len(parsed.sections), 2)
            self.assertEqual(parsed.sections[0].title, "Step 1")
            self.assertEqual(parsed.sections[0].content, "Do the first task.")
            self.assertEqual(parsed.sections[1].title, "Step 2")
            self.assertEqual(parsed.sections[1].content, "Do the second task.")

            plain = delivery.parse_guide("Just a guide summary without headings.")
            self.assertEqual(plain.summary, "Just a guide summary without headings.")
            self.assertEqual(len(plain.sections), 0)

    def test_advance_step_lifecycle(self) -> None:
        """CUJ: Advancing through steps with verification passing and failing."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            self.assertFalse(delivery.has_steps_remaining)

        guide = Guide(
            summary="High-level summary",
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

            # Verification failure produces no response and does not advance step
            # Requirement: When advancing a step with failed verification, the current step index is retained and no response is produced.
            # Requirement: [GuideDelivery] When verification fails, advancing a step retains the current step section and produces no response.
            res_fail = delivery.advance_step(verification_passed=False)
            self.assertIsNone(res_fail)
            self.assertTrue(delivery.has_steps_remaining)

            # First advance produces summary + first step
            # Requirement: When advancing a step with passed verification before any step is delivered, the response combines the guide summary and first step section content, advancing to the first section.
            # Requirement: [GuideDelivery] When verification passes on initial delivery, advancing a step produces a response containing the guide summary and first step section content.
            res1 = delivery.advance_step(verification_passed=True)
            self.assertIsNotNone(res1)
            assert res1 is not None
            self.assertIn("High-level summary", res1.content)
            self.assertIn("Content 1", res1.content)
            self.assertTrue(delivery.has_steps_remaining)

            # Second advance produces second step
            # Requirement: When advancing a step with passed verification and subsequent steps remain, the response contains the next step section content and the step index advances to that section.
            # Requirement: [GuideDelivery] When verification passes on subsequent steps and steps remain, advancing a step produces a response containing the next step section content.
            res2 = delivery.advance_step(verification_passed=True)
            self.assertIsNotNone(res2)
            assert res2 is not None
            self.assertIn("Content 2", res2.content)
            self.assertFalse(delivery.has_steps_remaining)

            # Subsequent advance when exhausted produces None
            # Requirement: When no guide is configured or no step sections remain, advancing a step produces no response.
            res3 = delivery.advance_step(verification_passed=True)
            self.assertIsNone(res3)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
