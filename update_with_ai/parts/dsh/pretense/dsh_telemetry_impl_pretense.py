"""Pretense state machine, fake synthesis, unit tests, parity tests, and fuzzing for DshTelemetryParser."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.dsh.lib import dsh_telemetry, dsh_telemetry_impl
from update_with_ai.parts.dsh.lib.dsh_telemetry import (
    DshRpcRoundStatus,
    DshSessionTokenMetrics,
    DshTelemetryParser,
)


@dataclass
class DshTelemetryState:
    """Canonical model state for DshTelemetry."""
    dispatched_tasks: Dict[str, DshRpcRoundStatus] = field(default_factory=dict)
    server_available: bool = False


class DshTelemetryStateMachine(StateMachine[DshTelemetryState]):
    """Unified Pretense State Machine for DshTelemetryParser."""

    def __init__(
        self,
        state: Optional[DshTelemetryState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DshTelemetryState(), singletons=singletons)

    @transition(DshTelemetryParser.parse_stream_text)
    def parse_stream_text(
        self,
        ctx: TransitionContext[DshTelemetryParser, [str, Optional[str]], DshSessionTokenMetrics],
    ) -> None:
        ctx.arguments(
                    stream_text=Domain(strategy=lambda: ''),
                    model_name=Domain(strategy=lambda: None),
                )
        def returns(stream_text: str = "", model_name: Optional[str] = None) -> DshSessionTokenMetrics:
            in_t = 0
            cached_t = 0
            out_t = 0
            for line in stream_text.splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    ev = json.loads(line)
                    usage = ev.get("usage")
                    if not usage and isinstance(ev.get("data"), dict):
                        usage = ev["data"].get("usage")
                    if isinstance(usage, dict):
                        in_t += int(usage.get("inputTokens") or 0)
                        cached_t += int(usage.get("cacheReadTokens") or 0)
                        out_t += int(usage.get("outputTokens") or 0)
                except Exception:
                    pass

            return DshSessionTokenMetrics(
                input_tokens=in_t,
                cached_tokens=cached_t,
                output_tokens=out_t,
                total_tokens=in_t + cached_t + out_t,
                cost_usd=0.0,
                model_name=model_name or "",
            )
        ctx.returns(returns)
        ctx.update(lambda res, stream_text="", model_name=None: None)

    @transition(DshTelemetryParser.is_desktop_server_available)
    def is_desktop_server_available(
        self,
        ctx: TransitionContext[DshTelemetryParser, [Optional[str]], bool],
    ) -> None:
        ctx.arguments(sessions_dir=Domain(strategy=lambda: None))
        ctx.returns(lambda sessions_dir=None: self.state.server_available)
        ctx.update(lambda res, sessions_dir=None: None)

    @transition(DshTelemetryParser.dispatch_round_rpc)
    def dispatch_round_rpc(
        self,
        ctx: TransitionContext[DshTelemetryParser, [str, str, str, Optional[str], Optional[str], Optional[str]], Optional[str]],
    ) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    role_name=Domain(strategy=lambda: 'low'),
                    prompt_text=Domain(strategy=lambda: 'prompt'),
                    session_id=Domain(strategy=lambda: None),
                    sessions_dir=Domain(strategy=lambda: None),
                    model_name=Domain(strategy=lambda: None),
                )
        def returns(workspace_dir: str = "/tmp/ws", role_name: str = "low", prompt_text: str = "prompt", session_id: Optional[str] = None, sessions_dir: Optional[str] = None, model_name: Optional[str] = None) -> Optional[str]:
            if not self.state.server_available:
                return None
            handle = f"task-{role_name}-{len(self.state.dispatched_tasks) + 1}"
            self.state.dispatched_tasks[handle] = DshRpcRoundStatus(is_active=True, is_completed=False)
            return handle
        ctx.returns(returns)
        ctx.update(lambda res, workspace_dir="/tmp/ws", role_name="low", prompt_text="prompt", session_id=None, sessions_dir=None, model_name=None: None)

    @transition(DshTelemetryParser.poll_round_rpc)
    def poll_round_rpc(
        self,
        ctx: TransitionContext[DshTelemetryParser, [str, Optional[str]], DshRpcRoundStatus],
    ) -> None:
        ctx.arguments(
                    task_handle=Domain(strategy=lambda: 'task-mock'),
                    sessions_dir=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda task_handle="task-mock", sessions_dir=None: self.state.dispatched_tasks.get(
            task_handle,
            DshRpcRoundStatus(is_active=False, is_completed=True, error=None),
        ))
        ctx.update(lambda res, task_handle="task-mock", sessions_dir=None: None)


proto = DshTelemetryStateMachine()


# ==============================================================================
# 2. Synthesized Fake Factory
# ==============================================================================

def make_dsh_telemetry_fake(
    state: Optional[DshTelemetryState] = None,
) -> DshTelemetryParser:
    """Instantiate a synthesized DshTelemetryParser fake."""
    st = state or DshTelemetryState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(DshTelemetryParser)


# ==============================================================================
# 3. Deterministic Unit Tests
# ==============================================================================

class TestDshTelemetryUnit(unittest.TestCase):
    """Deterministic unit tests validating state machine and synthesized fake."""

    def test_parse_stream_text_json_lines(self) -> None:
        fake = make_dsh_telemetry_fake()
        stream = (
            '{"event": "start"}\n'
            '{"usage": {"inputTokens": 120, "cacheReadTokens": 40, "outputTokens": 30}}\n'
            '{"event": "chunk", "data": {"usage": {"inputTokens": 10, "outputTokens": 5}}}\n'
            'Plain log message\n'
        )
        metrics = fake.parse_stream_text(stream, model_name="deepseek-v3")
        self.assertEqual(metrics.input_tokens, 130)
        self.assertEqual(metrics.cached_tokens, 40)
        self.assertEqual(metrics.output_tokens, 35)
        self.assertEqual(metrics.total_tokens, 205)

    def test_rpc_lifecycle_offline_vs_online(self) -> None:
        state = DshTelemetryState(server_available=False)
        fake = make_dsh_telemetry_fake(state)
        self.assertFalse(fake.is_desktop_server_available())
        task = fake.dispatch_round_rpc(workspace_dir="/ws", role_name="lib", prompt_text="Work")
        self.assertIsNone(task)

        # Switch online
        state.server_available = True
        self.assertTrue(fake.is_desktop_server_available())
        task = fake.dispatch_round_rpc(workspace_dir="/ws", role_name="lib", prompt_text="Work")
        self.assertIsNotNone(task)
        assert task is not None
        status = fake.poll_round_rpc(task)
        self.assertTrue(status.is_active)
        self.assertFalse(status.is_completed)


# ==============================================================================
# 4. Parity Tests
# ==============================================================================

class TestDshTelemetryParity(unittest.TestCase):
    """Parity tests verifying stream parsing alignment with dsh_telemetry_impl."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        dsh_telemetry_impl.__initialize__(self.registry)

    def test_stream_parsing_parity(self) -> None:
        stream = (
            '{"usage": {"inputTokens": 500, "cacheReadTokens": 200, "outputTokens": 150}}\n'
            'Non-json log line\n'
            '{"usage": {"inputTokens": 50, "outputTokens": 25}}\n'
        )
        fake = make_dsh_telemetry_fake()
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            real = scope.get_singleton(dsh_telemetry.DshTelemetryParser)
            real_metrics = real.parse_stream_text(stream, model_name="deepseek-flash")
            fake_metrics = fake.parse_stream_text(stream, model_name="deepseek-flash")

            self.assertEqual(real_metrics.input_tokens, fake_metrics.input_tokens)
            self.assertEqual(real_metrics.cached_tokens, fake_metrics.cached_tokens)
            self.assertEqual(real_metrics.output_tokens, fake_metrics.output_tokens)
            self.assertEqual(real_metrics.total_tokens, fake_metrics.total_tokens)


# ==============================================================================
# 5. Hypothesis Fuzz Tests
# ==============================================================================

class TestDshTelemetryFuzz(unittest.TestCase):
    """Hypothesis fuzz tests for stream parsing token calculations."""

    @given(
        in_t=st.integers(min_value=0, max_value=50000),
        cached_t=st.integers(min_value=0, max_value=50000),
        out_t=st.integers(min_value=0, max_value=50000),
    )
    @settings(max_examples=30)
    def test_token_summation_invariants(
        self, in_t: int, cached_t: int, out_t: int
    ) -> None:
        fake = make_dsh_telemetry_fake()
        stream = json.dumps({"usage": {"inputTokens": in_t, "cacheReadTokens": cached_t, "outputTokens": out_t}})
        metrics = fake.parse_stream_text(stream)
        self.assertEqual(metrics.input_tokens, in_t)
        self.assertEqual(metrics.cached_tokens, cached_t)
        self.assertEqual(metrics.output_tokens, out_t)
        self.assertEqual(metrics.total_tokens, in_t + cached_t + out_t)
