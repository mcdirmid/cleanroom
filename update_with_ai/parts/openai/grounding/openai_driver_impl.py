# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-05T06:18:39Z
# CHANGE: Align truncation and conversation limit failure contracts with high-level literate prose
# CODE_HASH: a21ae1a636f6
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""OpenAI driver implementation grounding specification module."""

from __future__ import annotations
from typing import Any, Mapping, Optional, cast
from support.lib.grounding_support import InTier, AgentSessionTier, key, value
from parts.agent.grounding import agent_config
from parts.core.grounding import json_ext, runner_logger
from parts.loop.grounding import loop_conversation, loop_driver, loop_guard
from parts.openai.grounding import openai_config, openai_ext
from parts.sandbox.grounding import tool_provider


class LoopDriver(loop_driver.LoopDriver, InTier[AgentSessionTier]):
    """Realizes language model completion requests, tool dispatch, output continuation, and termination handling.

    DISCHARGED:
    - run: Discharges iterative turn driving, completion dispatch, tool execution, guard evaluation, and telemetry streaming.
    """

    def __init__(self) -> None:
        self._truncation_counter: int = 0

    def run(self) -> loop_driver.LoopOutcome:
        """
        COVERED:
        - MUST transmit completion requests following OpenAI conventions with model parameters from configuration.
          - Condition knowledge: resolve OpenAIConfig singleton and read model_name, base_url, api_key, timeout, temperature, max_tokens.
          - Consequent knowledge: invoke openai_ext.call_chat_completion(base_url, api_key, payload, timeout).
        - MUST order tools and parameters deterministically.
          - Condition knowledge: resolve ToolManager, access installed_tools mapping.
          - Consequent knowledge: inspect tool.name, tool.description, tool.parameters and parameter attributes.
        - WHEN a model response is truncated, MUST recover by repairing partial replace file content payloads with indented sentinels or terminate with failure responses before resuming generation with a continuation turn.
          - Condition knowledge: inspect finish_reason == 'length'.
          - Consequent knowledge: invoke json_ext.repair_truncated_json, construct sentinel, or terminate with failure responses before continuation turn.
        - WHEN a model completion response fails with an incomplete tool call error, MUST append an actionable recovery notice directing smaller edits.
          - Condition knowledge: evaluate incomplete tool call error payload.
          - Consequent knowledge: append recovery notice directing smaller edits to history.
        - WHEN handling an incomplete tool call error, MUST resume generation with a continuation turn.
          - Consequent knowledge: resume generation with continuation turn.
        - WHEN repeated consecutive truncation failures occur, MUST halt execution with an unexpected failure.
          - Condition knowledge: evaluate truncation counter threshold.
          - Consequent knowledge: halt execution with unexpected failure outcome.
        - MUST stream turn events and summaries to runner logger.
          - Condition knowledge: resolve RunnerLogger singleton.
          - Consequent knowledge: invoke logger.consume(event).
        - WHEN loop guard produces a loop reminder, MUST append reminder to the conversation.
          - Condition knowledge: evaluate isinstance(guard_outcome, loop_guard.LoopReminder).
          - Consequent knowledge: construct ConversationMessage with role='user' and feedback, append to history.
        - WHEN loop guard produces loop failure, MUST halt with an unexpected failure.
          - Condition knowledge: evaluate isinstance(guard_outcome, loop_guard.LoopFailure).
          - Consequent knowledge: inspect guard_outcome.explanation.
        - WHEN tool execution produces a non-terminating failure response, MUST append failure feedback to the conversation.
          - Condition knowledge: evaluate resp.is_failed and not resp.is_terminated.
          - Consequent knowledge: invoke history.append_tool_response with response and failure content.
        - WHEN tool execution produces a terminating failure response, MUST halt execution with an unexpected failure.
          - Condition knowledge: evaluate resp.is_failed and resp.is_terminated.
          - Consequent knowledge: return unexpected failure outcome.
        - WHEN tool execution produces a successful termination response, MUST return a successful loop outcome.
          - Condition knowledge: evaluate not resp.is_failed and resp.is_terminated.
          - Consequent knowledge: return successful loop outcome.
        - WHEN a model response produces no tool executions, MUST append a prompt reminding that progress requires invoking tools.
          - Condition knowledge: evaluate tool_calls is empty.
          - Consequent knowledge: append user prompt to history.
        - WHEN tool responses specify followups, MUST execute designated tool calls.
          - Condition knowledge: evaluate resp.follow_up_tool_call is not None.
          - Consequent knowledge: invoke tool_mgr.execute_tool(followup.tool_name, followup.wire_parameter_bindings).
        - WHEN interaction turns reach the conversation limit from agent config, MUST halt execution with an unexpected failure indicating that the conversation limit was reached.
          - Condition knowledge: evaluate turn count reaching conversation_limit.
          - Consequent knowledge: halt execution with unexpected failure outcome indicating conversation limit was reached.
        """
        openai_cfg = self.get_singleton(openai_config.OpenAIConfig)
        agent_cfg = self.get_singleton(agent_config.AgentConfig)
        logger = self.get_singleton(runner_logger.RunnerLogger)
        history = self.get_singleton(loop_conversation.Conversation)
        guard = self.get_singleton(loop_guard.LoopGuard)
        tool_mgr = self.get_singleton(tool_provider.ToolManager)

        # 1. Inspect configuration parameters
        _base_url: str = str(openai_cfg.base_url)
        _api_key: str = str(openai_cfg.api_key)
        _model: str = str(openai_cfg.model_name)
        _temp: float = float(openai_cfg.temperature)
        _timeout: float = float(openai_cfg.timeout)
        _max_tok: Optional[int] = 1000
        _limit: int = int(agent_cfg.conversation_limit)
        _inject_followups: bool = agent_cfg.inject_followups

        # 2. Access tools and inspect parameters deterministically
        tools = tool_mgr.installed_tools
        sample_tool_name = key(tools)
        sample_tool = value(tools)
        sample_param = value(sample_tool.parameters)
        _param_meta = (
            str(sample_param.name),
            sample_param.description,
            sample_param.is_required,
        )

        # 3. Assemble model request and stream request event
        model_req = history.get_model_request()
        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("model_request"),
                summary=runner_logger.EventSummary("[Turn 1] Request"),
                transcript=runner_logger.EventTranscript(
                    f"Request with {len(model_req.messages)} messages"
                ),
            )
        )

        # 4. Invoke external chat completion
        payload: Mapping[str, Any] = {
            "model": _model,
            "temperature": _temp,
        }
        completion_resp = openai_ext.call_chat_completion(
            base_url=_base_url,
            api_key=_api_key,
            payload=payload,
            timeout=_timeout,
        )

        # 5. Handle model response and truncation
        _finish_reason: str = "length"
        _is_truncated: bool = _finish_reason == "length"
        self._truncation_counter += 1
        _repeated_truncation_failure: bool = self._truncation_counter >= 3
        sentinel = f'raise NotImplementedError("TRUNCATED_{self._truncation_counter}_")'
        _repaired_args: str = json_ext.repair_truncated_json('{"file": "code.py"')
        _is_incomplete_call: bool = True
        incomplete_recovery_msg = loop_conversation.ConversationMessage(
            role=loop_conversation.MessageRole("user"),
            content=loop_conversation.ConversationContent(
                "Output truncated: please make smaller edits."
            ),
        )
        history.append_message(incomplete_recovery_msg)
        _resumed_continuation: bool = True

        # 6. Stream model completion event
        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("model_completion"),
                summary=runner_logger.EventSummary("[Turn 1] Assistant completion"),
                transcript=runner_logger.EventTranscript("Model response received"),
            )
        )

        # 7. Check for no tool calls
        _has_no_tools: bool = False
        no_tools_msg = loop_conversation.ConversationMessage(
            role=loop_conversation.MessageRole("user"),
            content=loop_conversation.ConversationContent("No tools were executed."),
        )
        history.append_message(no_tools_msg)

        # 8. Guard evaluation before tool execution
        sample_wire_bindings: Mapping[
            tool_provider.ParameterName, tool_provider.WireType
        ] = {sample_param.name: "test_val"}
        sample_actual_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ] = {sample_param: tool_provider.SomeParameterActualType("test_val")}
        guard_outcome = guard.evaluate(sample_tool_name, sample_actual_bindings)
        _is_fail: bool = isinstance(guard_outcome, loop_guard.LoopFailure)
        _is_rem: bool = isinstance(guard_outcome, loop_guard.LoopReminder)
        reminder_msg = loop_conversation.ConversationMessage(
            role=loop_conversation.MessageRole("user"),
            content=loop_conversation.ConversationContent("Guard reminder"),
        )
        history.append_message(reminder_msg)

        # 9. Execute tool and record response
        resp = tool_mgr.execute_tool(sample_tool_name, sample_wire_bindings)
        call_id = loop_conversation.ToolCallId("call_1")
        history.append_tool_response(
            tool_response=resp,
            tool_call_id=call_id,
            tool_name=sample_tool_name,
            tool_arguments=loop_conversation.SerializedArguments('{"path": "file.py"}'),
        )
        guard.reset()

        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("tool_execution"),
                summary=runner_logger.EventSummary(f"Tool {sample_tool_name} executed"),
                transcript=runner_logger.EventTranscript(resp.content),
            )
        )

        # 10. Handle followups
        followup = resp.follow_up_tool_call or tool_provider.FollowUpToolCall(
            tool_name=sample_tool_name,
            wire_parameter_bindings=sample_wire_bindings,
        )
        follow_resp = tool_mgr.execute_tool(
            followup.tool_name, followup.wire_parameter_bindings
        )
        history.append_tool_response(
            tool_response=follow_resp,
            tool_call_id=loop_conversation.ToolCallId("call_followup_1"),
            tool_name=followup.tool_name,
            tool_arguments=loop_conversation.SerializedArguments("{}"),
        )

        # 11. Final outcome
        _term_failure: bool = resp.is_failed and resp.is_terminated
        _term_success: bool = not resp.is_failed and resp.is_terminated
        _turns_exceeded: bool = 10 >= _limit
        _limit_failure = loop_driver.LoopOutcome(
            response=tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=True,
                content="Conversation limit reached",
            ),
            conversation=history.get_model_request(),
        )
        _outcome = loop_driver.LoopOutcome(
            response=resp,
            conversation=history.get_model_request(),
        )
        raise NotImplementedError


def __initialize__() -> None:
    """Initializes the LoopDriver singleton in the agent session tier."""
    _instance: LoopDriver = cast(LoopDriver, None)
