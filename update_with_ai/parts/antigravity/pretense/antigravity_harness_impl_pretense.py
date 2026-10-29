"""Pretense specifications and tests for antigravity_harness_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from pretense import Domain, StateMachine, TransitionContext, transition
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.antigravity.lib import (
    antigravity_harness,
    antigravity_harness_impl,
)
from update_with_ai.parts.subagent.lib import subagent_harness


# ==============================================================================
# 1. Pretense State Definitions
# ==============================================================================

@dataclass
class TelemetryParserState:
    parsed_files: int = 0


class AntigravityHarnessStateMachine(StateMachine[TelemetryParserState]):
    """Unified Pretense State Machine for TranscriptTelemetryParser."""

    def __init__(
        self,
        state: Optional[TelemetryParserState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or TelemetryParserState(), singletons=singletons)

    @transition(antigravity_harness.TranscriptTelemetryParser.parse_transcript_file)
    def parse_transcript_file(
        self,
        ctx: TransitionContext[antigravity_harness.TranscriptTelemetryParser, [str, Optional[str]], antigravity_harness.TranscriptTokenMetrics],
    ) -> None:
        ctx.arguments(
                    transcript_path=Domain(strategy=lambda: '/tmp/transcript.jsonl'),
                    model_name=Domain(strategy=lambda: 'gemini-2.5-flash'),
                )
        ctx.returns(lambda transcript_path="/tmp/transcript.jsonl", model_name="gemini-2.5-flash": (
            antigravity_harness.TranscriptTokenMetrics(
                input_tokens=100,
                output_tokens=50,
                cached_tokens=20,
                cost_usd=0.001,
            )
        ))
        def provide(res: antigravity_harness.TranscriptTokenMetrics, transcript_path: str = "/tmp/transcript.jsonl", model_name: Optional[str] = "gemini-2.5-flash") -> None:
            self.state.parsed_files += 1
        ctx.update(provide)


proto = AntigravityHarnessStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_telemetry_parser_fake(
    state: Optional[TelemetryParserState] = None,
) -> antigravity_harness.TranscriptTelemetryParser:
    """Instantiate a synthesized TranscriptTelemetryParser fake."""
    st = state or TelemetryParserState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(antigravity_harness.TranscriptTelemetryParser)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestTranscriptTelemetryParserUnit(unittest.TestCase):
    """Unit tests for synthesized TranscriptTelemetryParser fake."""

    def setUp(self) -> None:
        self.state = TelemetryParserState()
        self.fake = make_telemetry_parser_fake(self.state)

    def test_parse_telemetry(self) -> None:
        metrics = self.fake.parse_transcript_file("/tmp/foo.jsonl", "gemini-2.5-flash")
        self.assertEqual(metrics.input_tokens, 100)
        self.assertEqual(self.state.parsed_files, 1)


class MockHarnessRegistry:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.installed: dict[str, Any] = {}

    def install_harness(self, platform_name: str, factory: Any) -> None:
        self.installed[platform_name] = factory


class TestAntigravityHarnessImplReal(unittest.TestCase):
    """Direct unit tests for antigravity_harness_impl.py."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        self.mock_registry = MockHarnessRegistry()
        self.registry.register_instance(
            self.mock_registry,
            keys=[subagent_harness.HarnessRegistry],
            tier=agent_session.agent_session,
        )
        antigravity_harness_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_transcript_parser_flash_and_pro(self) -> None:
        parser = antigravity_harness_impl.TranscriptTelemetryParser()
        transcript_file = os.path.join(self.test_dir, "transcript.jsonl")
        step1 = {
            "step_index": 1,
            "type": "MODEL",
            "usage": {
                "input_tokens": 100_000,
                "cached_tokens": 400_000,
                "output_tokens": 50_000,
            },
        }
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(step1) + "\n")

        metrics_flash = parser.parse_transcript_file(
            transcript_path=transcript_file,
            model_name="gemini-2.5-flash",
        )
        self.assertEqual(metrics_flash.input_tokens, 100_000)
        self.assertEqual(metrics_flash.cached_tokens, 400_000)
        self.assertEqual(metrics_flash.output_tokens, 50_000)
        self.assertGreater(metrics_flash.cost_usd, 0.0)

        metrics_pro = parser.parse_transcript_file(
            transcript_path=transcript_file,
            model_name="gemini-2.5-pro",
        )
        self.assertGreater(metrics_pro.cost_usd, metrics_flash.cost_usd)

    def test_harness_manager_register(self) -> None:
        manager = self.scope.get_singleton(
            antigravity_harness.AntigravityHarnessManager
        )
        manager.initialize()
        self.assertIn("antigravity", self.mock_registry.installed)
