"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for OpenAIConfig."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
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


class OpenAIConfigStateMachine(StateMachine[OpenAIConfigState]):
    """State machine for OpenAIConfig."""

    @transition.seeding()
    def seed_config(
        self,
        ctx: TransitionContext[
            Any,
            [str | None, str | None, str | None, float | None, float | None, int | None],
            None,
        ],
    ) -> None:
        ctx.arguments(
                    m=Domain(strategy=lambda: 'gpt-4o'),
                    b=Domain(strategy=lambda: None),
                    k=Domain(strategy=lambda: None),
                    t=Domain(strategy=lambda: 60.0),
                    temp=Domain(strategy=lambda: 0.0),
                    mt=Domain(strategy=lambda: 4096),
                )
        ctx.returns(lambda m, b, k, t, temp, mt: None)
        ctx.update(
            lambda res, m, b, k, t, temp, mt: (
                setattr(self.state, "model_name", "gpt-4o" if m is None else m),
                setattr(self.state, "base_url", b),
                setattr(self.state, "api_key", k),
                setattr(self.state, "timeout", 60.0 if t is None else t),
                setattr(self.state, "temperature", 0.0 if temp is None else temp),
                setattr(self.state, "max_tokens", 4096 if mt is None else mt),
            )
        )

    @transition(name="model_name")
    def model_name(self, ctx: TransitionContext[OpenAIConfig, [], ModelName]) -> None:
        ctx.arguments()
        ctx.returns(lambda: ModelName(self.state.model_name))

    @transition(name="base_url")
    def base_url(self, ctx: TransitionContext[OpenAIConfig, [], Optional[BaseUrl]]) -> None:
        ctx.arguments()
        ctx.returns(lambda: BaseUrl(self.state.base_url) if self.state.base_url is not None else None)

    @transition(name="api_key")
    def api_key(self, ctx: TransitionContext[OpenAIConfig, [], Optional[ApiKey]]) -> None:
        ctx.arguments()
        ctx.returns(lambda: ApiKey(self.state.api_key) if self.state.api_key is not None else None)

    @transition(name="timeout")
    def timeout(self, ctx: TransitionContext[OpenAIConfig, [], TimeoutSeconds]) -> None:
        ctx.arguments()
        ctx.returns(lambda: TimeoutSeconds(self.state.timeout))

    @transition(name="temperature")
    def temperature(self, ctx: TransitionContext[OpenAIConfig, [], Temperature]) -> None:
        ctx.arguments()
        ctx.returns(lambda: Temperature(self.state.temperature))

    @transition(name="max_tokens")
    def max_tokens(self, ctx: TransitionContext[OpenAIConfig, [], Optional[MaxTokens]]) -> None:
        ctx.arguments()
        ctx.returns(lambda: MaxTokens(self.state.max_tokens) if self.state.max_tokens is not None else None)


proto = OpenAIConfigStateMachine()


# ==============================================================================
# 3. Synthesized Fake Factory
# ==============================================================================

def make_openai_config_fake(state: Optional[OpenAIConfigState] = None) -> OpenAIConfig:
    """Instantiate a synthesized OpenAIConfig fake."""
    sm = OpenAIConfigStateMachine(state or OpenAIConfigState())
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
