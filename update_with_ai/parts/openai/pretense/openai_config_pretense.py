"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for OpenAIConfig."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.openai.lib.openai_config import (
    ApiKey,
    BaseUrl,
    MaxTokens,
    ModelName,
    OpenAIConfig,
    Temperature,
    TimeoutSeconds,
)


@dataclass
class OpenAIConfigState:
    """Canonical model state for OpenAIConfig."""
    model_name: str = "gpt-4o"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: float = 60.0
    temperature: float = 0.0
    max_tokens: Optional[int] = 4096


proto = StateMachineProto[OpenAIConfigState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_config(): pass

@seed_config.arguments
def _(
    state: OpenAIConfigState,
    this: Any,
    model_name: str | NotBoundType = NotBound,
    base_url: Optional[str] | NotBoundType = NotBound,
    api_key: Optional[str] | NotBoundType = NotBound,
    timeout: float | NotBoundType = NotBound,
    temperature: float | NotBoundType = NotBound,
    max_tokens: Optional[int] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str], Optional[str], float, float, Optional[int]]]:
    m = "gpt-4o" if isinstance(model_name, NotBoundType) else model_name
    b = None if isinstance(base_url, NotBoundType) else base_url
    k = None if isinstance(api_key, NotBoundType) else api_key
    t = 60.0 if isinstance(timeout, NotBoundType) else timeout
    temp = 0.0 if isinstance(temperature, NotBoundType) else temperature
    mt = 4096 if isinstance(max_tokens, NotBoundType) else max_tokens
    return (m, b, k, t, temp, mt)

@seed_config.returns
def _(
    state: OpenAIConfigState,
    this: Any,
    model_name: str,
    base_url: Optional[str],
    api_key: Optional[str],
    timeout: float,
    temperature: float,
    max_tokens: Optional[int],
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.model_name = model_name
    state.base_url = base_url
    state.api_key = api_key
    state.timeout = timeout
    state.temperature = temperature
    state.max_tokens = max_tokens
    return Value(None)


# ==============================================================================
# 2. Property Transitions
# ==============================================================================

@proto.transition(name="model_name")
def model_name(): pass

@model_name.arguments
def _(state: OpenAIConfigState, this: Any) -> Optional[Tuple[()]]:
    return ()

@model_name.returns
def _(state: OpenAIConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[ModelName]]:
    val = ModelName(state.model_name)
    if isinstance(outcome, Value) and outcome.val == val:
        return outcome
    if outcome is NotBound:
        return Value(val)
    return None


@proto.transition(name="base_url")
def base_url(): pass

@base_url.arguments
def _(state: OpenAIConfigState, this: Any) -> Optional[Tuple[()]]:
    return ()

@base_url.returns
def _(state: OpenAIConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Optional[BaseUrl]]]:
    val = BaseUrl(state.base_url) if state.base_url is not None else None
    if isinstance(outcome, Value) and outcome.val == val:
        return outcome
    if outcome is NotBound:
        return Value(val)
    return None


@proto.transition(name="api_key")
def api_key(): pass

@api_key.arguments
def _(state: OpenAIConfigState, this: Any) -> Optional[Tuple[()]]:
    return ()

@api_key.returns
def _(state: OpenAIConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Optional[ApiKey]]]:
    val = ApiKey(state.api_key) if state.api_key is not None else None
    if isinstance(outcome, Value) and outcome.val == val:
        return outcome
    if outcome is NotBound:
        return Value(val)
    return None


@proto.transition(name="timeout")
def timeout(): pass

@timeout.arguments
def _(state: OpenAIConfigState, this: Any) -> Optional[Tuple[()]]:
    return ()

@timeout.returns
def _(state: OpenAIConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[TimeoutSeconds]]:
    val = TimeoutSeconds(state.timeout)
    if isinstance(outcome, Value) and outcome.val == val:
        return outcome
    if outcome is NotBound:
        return Value(val)
    return None


@proto.transition(name="temperature")
def temperature(): pass

@temperature.arguments
def _(state: OpenAIConfigState, this: Any) -> Optional[Tuple[()]]:
    return ()

@temperature.returns
def _(state: OpenAIConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Temperature]]:
    val = Temperature(state.temperature)
    if isinstance(outcome, Value) and outcome.val == val:
        return outcome
    if outcome is NotBound:
        return Value(val)
    return None


@proto.transition(name="max_tokens")
def max_tokens(): pass

@max_tokens.arguments
def _(state: OpenAIConfigState, this: Any) -> Optional[Tuple[()]]:
    return ()

@max_tokens.returns
def _(state: OpenAIConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Optional[MaxTokens]]]:
    val = MaxTokens(state.max_tokens) if state.max_tokens is not None else None
    if isinstance(outcome, Value) and outcome.val == val:
        return outcome
    if outcome is NotBound:
        return Value(val)
    return None


# ==============================================================================
# 3. Synthesized Fake Factory
# ==============================================================================

def make_openai_config_fake(state: Optional[OpenAIConfigState] = None) -> OpenAIConfig:
    """Instantiate a synthesized OpenAIConfig fake."""
    st = state or OpenAIConfigState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(OpenAIConfig)


# ==============================================================================
# 4. Deterministic Unit Tests
# ==============================================================================

class TestOpenAIConfigUnit(unittest.TestCase):
    """Deterministic unit tests validating state machine and synthesized fake."""

    def test_default_config(self) -> None:
        fake = make_openai_config_fake()
        self.assertEqual(fake.model_name, "gpt-4o")
        self.assertIsNone(fake.base_url)
        self.assertIsNone(fake.api_key)
        self.assertEqual(fake.timeout, 60.0)
        self.assertEqual(fake.temperature, 0.0)
        self.assertEqual(fake.max_tokens, 4096)

    def test_custom_config(self) -> None:
        state = OpenAIConfigState(
            model_name="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
            timeout=120.0,
            temperature=0.7,
            max_tokens=8192,
        )
        fake = make_openai_config_fake(state)
        self.assertEqual(fake.model_name, "deepseek-chat")
        self.assertEqual(fake.base_url, "https://api.deepseek.com")
        self.assertEqual(fake.api_key, "sk-test")
        self.assertEqual(fake.timeout, 120.0)
        self.assertEqual(fake.temperature, 0.7)
        self.assertEqual(fake.max_tokens, 8192)


# ==============================================================================
# 5. Hypothesis Fuzz Tests
# ==============================================================================

class TestOpenAIConfigFuzz(unittest.TestCase):
    """Hypothesis fuzz tests for OpenAIConfig invariants."""

    @given(
        model=st.text(min_size=1, max_size=30),
        url=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
        key=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
        timeout_sec=st.floats(min_value=0.1, max_value=300.0),
        temp=st.floats(min_value=0.0, max_value=2.0),
        tokens=st.one_of(st.none(), st.integers(min_value=1, max_value=65536)),
    )
    @settings(max_examples=30)
    def test_config_fuzz_invariants(
        self,
        model: str,
        url: Optional[str],
        key: Optional[str],
        timeout_sec: float,
        temp: float,
        tokens: Optional[int],
    ) -> None:
        state = OpenAIConfigState(
            model_name=model,
            base_url=url,
            api_key=key,
            timeout=timeout_sec,
            temperature=temp,
            max_tokens=tokens,
        )
        fake = make_openai_config_fake(state)

        self.assertEqual(fake.model_name, model)
        self.assertEqual(fake.base_url, url)
        self.assertEqual(fake.api_key, key)
        self.assertAlmostEqual(fake.timeout, timeout_sec)
        self.assertAlmostEqual(fake.temperature, temp)
        self.assertEqual(fake.max_tokens, tokens)
