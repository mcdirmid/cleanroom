"""Tests for guide_delivery_impl derived from LLS."""

import unittest
from lib.guide_delivery import TaskGuide, StepSection, StepDelivery
from lib.guide_delivery_impl import GuideDeliveryFactoryImpl


class GuideDeliveryImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = GuideDeliveryFactoryImpl()

    def test_dataclasses(self) -> None:
        """Tests Data Types: TaskGuide and StepSection dataclasses."""
        section = StepSection(index=0, title="Step 1", content="Content 1")
        self.assertEqual(section.index, 0)
        self.assertEqual(section.title, "Step 1")
        self.assertEqual(section.content, "Content 1")

        guide = TaskGuide(summary="Summary", sections=[section])
        self.assertEqual(guide.summary, "Summary")
        self.assertEqual(len(guide.sections), 1)

    def test_guide_summary_delivery(self) -> None:
        """Tests CUJ for pre-injecting guide summary at run start.

        Checks postconditions: get_summary_delivery returns StepDelivery containing the guide summary.
        """
        guide = TaskGuide(
            summary="Guide high-level summary",
            sections=[
                StepSection(index=0, title="Step 1", content="Content 1"),
            ],
        )
        delivery = self.factory.create_guide_delivery(guide)
        summary = delivery.get_summary_delivery()
        self.assertIsInstance(summary, StepDelivery)
        self.assertEqual(summary.content, "Guide high-level summary")

    def test_advance_step_progression_and_verification_failure(self) -> None:
        """Tests all sides of step advancement:
        1. verification_passed=True -> advances to next step section.
        2. verification_passed=False -> retains current step section without advancement.
        3. All steps completed -> has_steps_remaining returns False.
        4. Exhausted steps with verification_passed=True -> returns None.
        """
        guide = TaskGuide(
            summary="Summary",
            sections=[
                StepSection(index=0, title="Step 1", content="Content 1"),
                StepSection(index=1, title="Step 2", content="Content 2"),
            ],
        )
        delivery = self.factory.create_guide_delivery(guide)
        self.assertTrue(delivery.has_steps_remaining())

        # Failure retains current step
        step_fail = delivery.advance_step(verification_passed=False)
        self.assertIsNone(step_fail)
        self.assertTrue(delivery.has_steps_remaining())

        # Passing advances to step 1
        step1 = delivery.advance_step(verification_passed=True)
        self.assertIsNotNone(step1)
        assert step1 is not None
        self.assertEqual(step1.content, "Content 1")
        self.assertTrue(delivery.has_steps_remaining())

        # Passing advances to step 2
        step2 = delivery.advance_step(verification_passed=True)
        self.assertIsNotNone(step2)
        assert step2 is not None
        self.assertEqual(step2.content, "Content 2")
        self.assertFalse(delivery.has_steps_remaining())

        # Calling advance_step when exhausted returns None
        step_exhausted = delivery.advance_step(verification_passed=True)
        self.assertIsNone(step_exhausted)
        self.assertFalse(delivery.has_steps_remaining())

    def test_skips_lint_checks_section(self) -> None:
        """Tests Behavioral Description: GuideDeliveryImpl skips sections headed by 'Lint checks'."""
        guide = TaskGuide(
            summary="Summary",
            sections=[
                StepSection(index=0, title="Step 1", content="Content 1"),
                StepSection(index=1, title="Lint checks", content="Lint checks content"),
                StepSection(index=2, title="Step 2", content="Content 2"),
            ],
        )
        delivery = self.factory.create_guide_delivery(guide)
        s1 = delivery.advance_step(verification_passed=True)
        self.assertIsNotNone(s1)
        assert s1 is not None
        self.assertEqual(s1.content, "Content 1")

        s2 = delivery.advance_step(verification_passed=True)
        self.assertIsNotNone(s2)
        assert s2 is not None
        # Should have skipped "Lint checks" and delivered "Content 2" directly
        self.assertEqual(s2.content, "Content 2")
        self.assertFalse(delivery.has_steps_remaining())


if __name__ == "__main__":
    unittest.main()
