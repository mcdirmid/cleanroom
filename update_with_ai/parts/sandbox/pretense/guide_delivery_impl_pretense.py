"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for GuideDelivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.agent.lib import file_alias, node_config
from update_with_ai.parts.sandbox.lib import guide_delivery, tool_provider
from update_with_ai.parts.sandbox.lib.guide_delivery_impl import (
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


def _make_content(text: str) -> file_alias.FileContent:
    return file_alias.FileContent(text)


def _make_diagnostic(text: str) -> node_config.VerificationDiagnostic:
    return node_config.VerificationDiagnostic(text)


# ==============================================================================
# 1. State Machine Protocol Definition
# ==============================================================================

@dataclass
class GuideDeliveryState:
    """Canonical model state for GuideDelivery."""
    guide: Optional[node_config.NodeGuide] = None
    step_index: int = 0
    has_steps_remaining: bool = False


proto = StateMachineProto[GuideDeliveryState]()


@proto.transition(name="guide")
def guide(): pass

@guide.returns
def _(state: GuideDeliveryState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Optional[node_config.NodeGuide]]]:
    expected = state.guide
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(name="has_steps_remaining")
def has_steps_remaining(): pass

@has_steps_remaining.returns
def _(state: GuideDeliveryState, this: Any, outcome: object = NotBound) -> Optional[Outcome[bool]]:
    expected = state.has_steps_remaining
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 2. Comprehensive Non-Fuzz Tests
# ==============================================================================

class MockNodeConfig:
    tier = agent_session

    def __init__(self, guide: Optional[node_config.NodeGuide] = None) -> None:
        self.guide = guide


class TestGuideDeliveryReal(unittest.TestCase):
    """Direct verification of the real GuideDelivery implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register_instance(
            MockNodeConfig(),
            keys=[node_config.NodeConfig],
            tier=agent_session,
        )

    def test_initialization(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            self.assertIsInstance(delivery, GuideDelivery)
            self.assertIs(scope.get_singleton(guide_delivery.GuideDelivery), delivery)
            self.assertIsNone(delivery.guide)
            self.assertFalse(delivery.has_steps_remaining)

    def test_initialize_obtains_configured_guide(self) -> None:
        configured = node_config.NodeGuide(
            summary=node_config.GuideSummary("Configured summary text."),
            sections=[
                node_config.StepSection(
                    index=node_config.StepIndex(1),
                    title=node_config.StepTitle("Configured Step"),
                    content=node_config.StepContent("Configured milestone task."),
                )
            ],
        )
        registry = LifecycleRegistry()
        __initialize__(registry)
        registry.register_instance(
            MockNodeConfig(guide=configured),
            keys=[node_config.NodeConfig],
            tier=agent_session,
        )
        with enter_phase(agent_session, registry=registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.initialize()
            self.assertEqual(delivery.guide, configured)
            self.assertTrue(delivery.has_steps_remaining)

    def test_parse_guide_extracts_summary(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertIsInstance(guide, node_config.NodeGuide)
            self.assertIn(_PREAMBLE, guide.summary)
            self.assertIn(_SUMMARY_BODY, guide.summary)
            self.assertNotIn(_STEP_ONE_CONTENT, guide.summary)
            self.assertNotIn(_FAILURE_CONTENT, guide.summary)

    def test_parse_guide_captures_verification_failure(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertIsNotNone(guide.verification_failure)
            self.assertIn(_FAILURE_CONTENT, str(guide.verification_failure))

    def test_parse_guide_creates_sequential_step_sections(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertEqual(len(guide.sections), 2)
            first, second = guide.sections[0], guide.sections[1]
            self.assertEqual(first.title, node_config.StepTitle("Step One"))
            self.assertEqual(second.title, node_config.StepTitle("Step Two"))
            self.assertIn(_STEP_ONE_CONTENT, first.content)
            self.assertIn(_STEP_TWO_CONTENT, second.content)
            self.assertEqual(second.index, first.index + 1)

    def test_guide_property_exposes_parsed_guide(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertEqual(delivery.guide, guide)

    def test_has_steps_remaining_after_parse(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            self.assertTrue(delivery.has_steps_remaining)

    def test_record_initial_primer(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            guide = delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            result = delivery.record_initial_primer(
                guide_delivery.InitialPrimer("Initial primer instructions.")
            )
            self.assertIsNone(result)
            self.assertEqual(delivery.guide, guide)
            self.assertTrue(delivery.has_steps_remaining)

    def test_advance_step_passed_delivers_instructions(self) -> None:
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
                or _STEP_TWO_CONTENT in response.content
            )

    def test_advance_step_passed_progresses_milestones(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            delivery.advance_step(True, _make_diagnostic(""))
            self.assertTrue(delivery.has_steps_remaining)
            delivery.advance_step(True, _make_diagnostic(""))
            self.assertFalse(delivery.has_steps_remaining)

    def test_advance_step_failed_reports_diagnostics(self) -> None:
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
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            resp1 = delivery.advance_step(True, _make_diagnostic(""))
            self.assertIsNotNone(resp1)
            self.assertTrue(delivery.has_steps_remaining)
            resp2 = delivery.advance_step(True, _make_diagnostic(""))
            self.assertFalse(delivery.has_steps_remaining)
            resp_past = delivery.advance_step(True, _make_diagnostic(""))
            self.assertFalse(delivery.has_steps_remaining)

    def test_advance_step_initial_step_failure_reports_primer(self) -> None:
        primer_text = "Important initial primer: review requirements carefully."
        diag_text = "SyntaxError on initial compile"
        with enter_phase(agent_session, registry=self.registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.parse_guide(_make_content(_GUIDE_MARKDOWN))
            delivery.record_initial_primer(guide_delivery.InitialPrimer(primer_text))
            response = delivery.advance_step(False, _make_diagnostic(diag_text))
            self.assertIsNotNone(response)
            assert response is not None
            self.assertIn(diag_text, response.content)
            self.assertIn(primer_text, response.content)



# ==============================================================================
# 3. Hypothesis Property Fuzz Testing
# ==============================================================================

class TestGuideDeliveryFuzz(unittest.TestCase):
    """Property fuzz testing for GuideDelivery."""

    @settings(max_examples=25)
    @given(
        num_sections=st.integers(min_value=1, max_value=5),
        title_prefix=st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnopqrstuvwxyz"),
    )
    def test_step_progression_invariants(self, num_sections: int, title_prefix: str) -> None:
        sections = [
            node_config.StepSection(
                index=node_config.StepIndex(i),
                title=node_config.StepTitle(f"{title_prefix}_{i}"),
                content=node_config.StepContent(f"Task {i}"),
            )
            for i in range(1, num_sections + 1)
        ]
        guide_obj = node_config.NodeGuide(
            summary=node_config.GuideSummary("Summary"),
            sections=sections,
        )

        registry = LifecycleRegistry()
        __initialize__(registry)
        registry.register_instance(
            MockNodeConfig(guide=guide_obj),
            keys=[node_config.NodeConfig],
            tier=agent_session,
        )
        with enter_phase(agent_session, registry=registry) as scope:
            delivery = scope.get_singleton(GuideDelivery)
            delivery.initialize()
            self.assertTrue(delivery.has_steps_remaining)
            for i in range(1, num_sections + 1):
                self.assertTrue(delivery.has_steps_remaining)
                delivery.advance_step(verification_passed=True, failure_diagnostics=node_config.VerificationDiagnostic(""))
            self.assertFalse(delivery.has_steps_remaining)
