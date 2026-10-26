"""Pretense state machine, fake synthesis, unit tests, parity tests, and fuzzing for DshTelemetryParser."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
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


proto = StateMachineProto[DshTelemetryState]()


# ==============================================================================
# 1. DshTelemetryParser Transitions
# ==============================================================================

@proto.transition(DshTelemetryParser.parse_stream_text)
def parse_stream_text(): pass

@parse_stream_text.arguments
def _(
    state: DshTelemetryState,
    this: Any,
    stream_text: str | NotBoundType = NotBound,
    model_name: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str]]]:
    st_text = "" if isinstance(stream_text, NotBoundType) else str(stream_text)
    m = None if isinstance(model_name, NotBoundType) else model_name
    return (st_text, m)

@parse_stream_text.returns
def _(
    state: DshTelemetryState,
    this: Any,
    stream_text: str,
    model_name: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[DshSessionTokenMetrics]]:
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

    expected = DshSessionTokenMetrics(
        input_tokens=in_t,
        cached_tokens=cached_t,
        output_tokens=out_t,
        total_tokens=in_t + cached_t + out_t,
        cost_usd=0.0,
        model_name=model_name or "",
    )

    if isinstance(outcome, Value) and outcome.val.total_tokens == expected.total_tokens:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(DshTelemetryParser.is_desktop_server_available)
def is_desktop_server_available(): pass

@is_desktop_server_available.arguments
def _(
    state: DshTelemetryState,
    this: Any,
    sessions_dir: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str]]]:
    s = None if isinstance(sessions_dir, NotBoundType) else sessions_dir
    return (s,)

@is_desktop_server_available.returns
def _(
    state: DshTelemetryState,
    this: Any,
    sessions_dir: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[bool]]:
    res = state.server_available
    if isinstance(outcome, Value) and outcome.val == res:
        return outcome
    if outcome is NotBound:
        return Value(res)
    return None


@proto.transition(DshTelemetryParser.dispatch_round_rpc)
def dispatch_round_rpc(): pass

@dispatch_round_rpc.arguments
def _(
    state: DshTelemetryState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    role_name: str | NotBoundType = NotBound,
    prompt_text: str | NotBoundType = NotBound,
    session_id: Optional[str] | NotBoundType = NotBound,
    sessions_dir: Optional[str] | NotBoundType = NotBound,
    model_name: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, str, Optional[str], Optional[str], Optional[str]]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    r = "low" if isinstance(role_name, NotBoundType) else str(role_name)
    p = "prompt" if isinstance(prompt_text, NotBoundType) else str(prompt_text)
    sid = None if isinstance(session_id, NotBoundType) else session_id
    sdir = None if isinstance(sessions_dir, NotBoundType) else sessions_dir
    m = None if isinstance(model_name, NotBoundType) else model_name
    return (ws, r, p, sid, sdir, m)

@dispatch_round_rpc.returns
def _(
    state: DshTelemetryState,
    this: Any,
    workspace_dir: str,
    role_name: str,
    prompt_text: str,
    session_id: Optional[str],
    sessions_dir: Optional[str],
    model_name: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[Optional[str]]]:
    if not state.server_available:
        expected = None
    else:
        handle = f"task-{role_name}-{len(state.dispatched_tasks) + 1}"
        state.dispatched_tasks[handle] = DshRpcRoundStatus(is_active=True, is_completed=False)
        expected = handle

    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(DshTelemetryParser.poll_round_rpc)
def poll_round_rpc(): pass

@poll_round_rpc.arguments
def _(
    state: DshTelemetryState,
    this: Any,
    task_handle: str | NotBoundType = NotBound,
    sessions_dir: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str]]]:
    h = "task-mock" if isinstance(task_handle, NotBoundType) else str(task_handle)
    s = None if isinstance(sessions_dir, NotBoundType) else sessions_dir
    return (h, s)

@poll_round_rpc.returns
def _(
    state: DshTelemetryState,
    this: Any,
    task_handle: str,
    sessions_dir: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[DshRpcRoundStatus]]:
    expected = state.dispatched_tasks.get(
        task_handle,
        DshRpcRoundStatus(is_active=False, is_completed=True, error=None),
    )
    if isinstance(outcome, Value) and outcome.val.is_completed == expected.is_completed:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


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
