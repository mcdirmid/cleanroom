"""Pretense state machine, fake synthesis, unit tests, and fuzzing for LoopDriver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import StateMachine, TransitionContext, transition
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.loop.lib import conversation, driver
from update_with_ai.parts.loop.lib.conversation import (
    ConversationContent,
    ConversationMessage,
    MessageRole,
    ModelRequest,
)
from update_with_ai.parts.loop.lib.driver import LoopDriver, LoopOutcome
from update_with_ai.parts.sandbox.lib.tool_provider import (
    ToolResponse,
    ToolResponseContent,
)


@dataclass
class DriverState:
    """Canonical model state for LoopDriver."""
    outcome_response: ToolResponse = field(
        default_factory=lambda: ToolResponse(
            is_failed=False,
            is_terminated=True,
            content=ToolResponseContent("Task completed successfully."),
        )
    )
    outcome_messages: List[ConversationMessage] = field(default_factory=list)
    has_run: bool = False


class DriverStateMachine(StateMachine[DriverState]):
    """Pretense StateMachine for LoopDriver."""

    def __init__(self, state: Optional[DriverState] = None):
        super().__init__(state=state or DriverState())

    # ==============================================================================
    # 1. LoopDriver Transitions
    # ==============================================================================

    @transition(LoopDriver.run)
    def run(
        self,
        ctx: TransitionContext[LoopDriver, [], LoopOutcome],
    ) -> None:
        def _returns() -> LoopOutcome:
            req = ModelRequest(messages=tuple(self.state.outcome_messages))
            return LoopOutcome(
                response=self.state.outcome_response,
                conversation=req,
            )
        ctx.returns(_returns)
        ctx.update(lambda res: setattr(self.state, "has_run", True))


proto = DriverStateMachine()


# ==============================================================================
# 2. Synthesized Fake Factory
# ==============================================================================

def make_driver_fake(state: Optional[DriverState] = None) -> LoopDriver:
    """Instantiate a synthesized LoopDriver fake."""
    sm = DriverStateMachine(state)
    return sm.as_fake(LoopDriver)


# ==============================================================================
# 3. Deterministic Unit Tests
# ==============================================================================

class TestDriverUnit(unittest.TestCase):
    """Deterministic unit tests validating state machine and synthesized fake."""

    def test_run_success_outcome(self) -> None:
        state = DriverState(
            outcome_messages=[
                ConversationMessage(role=MessageRole("user"), content=ConversationContent("Run")),
                ConversationMessage(role=MessageRole("assistant"), content=ConversationContent("Done")),
            ]
        )
        fake = make_driver_fake(state)
        outcome = fake.run()
        self.assertTrue(state.has_run)
        self.assertTrue(outcome.response.is_terminated)
        self.assertFalse(outcome.response.is_failed)
        self.assertEqual(len(outcome.conversation.messages), 2)


# ==============================================================================
# 4. Hypothesis Fuzz Tests
# ==============================================================================

class TestDriverFuzz(unittest.TestCase):
    """Hypothesis fuzz tests for LoopDriver execution invariants."""

    @given(
        is_failed=st.booleans(),
        content_text=st.text(min_size=1, max_size=50),
        msg_count=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=25)
    def test_run_termination_invariants(
        self, is_failed: bool, content_text: str, msg_count: int
    ) -> None:
        messages = [
            ConversationMessage(
                role=MessageRole("user" if i % 2 == 0 else "assistant"),
                content=ConversationContent(f"message_{i}"),
            )
            for i in range(msg_count)
        ]
        resp = ToolResponse(
            is_failed=is_failed,
            is_terminated=True,
            content=ToolResponseContent(content_text),
        )
        state = DriverState(outcome_response=resp, outcome_messages=messages)
        fake = make_driver_fake(state)
        outcome = fake.run()
        self.assertTrue(state.has_run)
        self.assertEqual(outcome.response.is_failed, is_failed)
        self.assertTrue(outcome.response.is_terminated)
        self.assertEqual(len(outcome.conversation.messages), msg_count)


class MockModelConfig:
    tier = "system"
    model_name = "test-model"
    base_url = "https://api.test.com"
    api_key = "test-key"
    timeout = 30
    conversation_limit = 5
    temperature = 0.2
    max_tokens = None
    is_step_mode = False
    is_startup_reads = False
    inject_followups = False


class MockLogger:
    tier = "system"
    def consume(self, event: Any) -> None:
        pass


class MockHistory:
    tier = "agent_session"
    def __init__(self) -> None:
        self._messages: List[ConversationMessage] = []
    @property
    def messages(self) -> List[ConversationMessage]:
        return list(self._messages)
    def append_message(self, message: ConversationMessage) -> None:
        self._messages.append(message)
    def append_tool_response(self, tool_response: Any, tool_call_id: Any, tool_name: Any, tool_arguments: Any) -> None:
        self._messages.append(
            ConversationMessage(
                role=MessageRole("tool"),
                content=ConversationContent(str(tool_response.content)),
                tool_call_id=tool_call_id,
                tool_name=tool_name,
            )
        )
    def get_model_request(self) -> ModelRequest:
        return ModelRequest(messages=list(self._messages))


class MockLoopGuard:
    tier = "agent_session"
    def evaluate(self, tool_name: Any, arguments: Any) -> Any:
        return None
    def reset(self) -> None:
        pass


class MockToolManager:
    tier = "agent_session"
    def __init__(self) -> None:
        self.responses: dict[str, ToolResponse] = {}
    @property
    def installed_tools(self) -> Mapping[Any, Any]:
        return {}
    def execute_tool(self, name: Any, bindings: Any) -> ToolResponse:
        return self.responses.get(
            str(name),
            ToolResponse(is_failed=False, is_terminated=True, content=ToolResponseContent("done")),
        )


class TestDriverImplReal(unittest.TestCase):
    """Direct unit tests for driver_impl.py."""

    def test_run_terminating_tool(self) -> None:
        from unittest.mock import MagicMock, patch
        from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
        from update_with_ai.parts.agent.lib.agent_config import AgentConfig
        from update_with_ai.parts.agent.lib.session import agent_session
        from update_with_ai.parts.loop.lib.conversation import Conversation
        from update_with_ai.parts.loop.lib.guard import LoopGuard
        from update_with_ai.parts.loop.lib.logger import RunnerLogger
        from update_with_ai.parts.loop.lib.driver import LoopDriver as LoopDriverInterface
        from update_with_ai.parts.openai.lib.driver_impl import LoopDriver, __initialize__
        from update_with_ai.parts.openai.lib.openai_config import OpenAIConfig
        from update_with_ai.parts.sandbox.lib.tool_provider import ToolManager

        registry = LifecycleRegistry()
        __initialize__(registry)
        model_cfg = MockModelConfig()
        logger = MockLogger()
        history = MockHistory()
        guard = MockLoopGuard()
        tool_mgr = MockToolManager()

        registry.register_instance(model_cfg, keys=[OpenAIConfig, AgentConfig], tier=system)
        registry.register_instance(logger, keys=[RunnerLogger], tier=system)
        registry.register_instance(history, keys=[Conversation], tier=agent_session)
        registry.register_instance(guard, keys=[LoopGuard], tier=agent_session)
        registry.register_instance(tool_mgr, keys=[ToolManager], tier=agent_session)

        with patch("update_with_ai.parts.openai.lib.driver_impl.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            dummy_choice = MagicMock()
            dummy_choice.message.content = "All done"
            dummy_choice.message.tool_calls = [
                MagicMock(
                    id="tc_1",
                    function=MagicMock(name="finish_task", arguments='{"summary": "done"}'),
                )
            ]
            dummy_choice.finish_reason = "stop"
            dummy_comp = MagicMock()
            dummy_comp.choices = [dummy_choice]
            dummy_comp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, prompt_tokens_details=None)
            mock_client.chat.completions.create.return_value = dummy_comp

            tool_mgr.responses["finish_task"] = ToolResponse(
                is_failed=False, is_terminated=True, content=ToolResponseContent("finished")
            )

            with enter_phase(agent_session, registry=registry) as scope:
                driver = scope.get_singleton(LoopDriver)
                outcome = driver.run()
                self.assertTrue(outcome.response.is_terminated)
                self.assertFalse(outcome.response.is_failed)
