"""
lib/agent_loop_impl.py

Agent Loop Implementation using OpenAI API, delegating history and loop guardrails.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

try:
    from openai import OpenAI
    from openai.types.chat import (
        ChatCompletionMessage,
        ChatCompletionMessageFunctionToolCall,
        ChatCompletionToolParam,
    )
except ImportError:
    OpenAI = Any  # type: ignore
    ChatCompletionMessage = Any  # type: ignore
    ChatCompletionMessageFunctionToolCall = Any  # type: ignore
    ChatCompletionToolParam = Any  # type: ignore

from .agent_loop import (
    AgentLoop,
    AgentResult,
    CumulativeUsage,
    HistoryEntry,
    LogEvent,
    LoggerCallback,
    ToolCall,
    Usage,
)
from .agent_loop_config import AgentLoopConfig
from .conversation_history import ConversationHistory
from .loop_guard import LoopGuard
from .tool_provider import (
    Continue,
    PresentedToolResult,
    TerminateAgentWithFailure,
    TerminateAgentWithSuccess,
    ToolDefinition,
    ToolExecutor,
    ToolFailure,
    ToolResult,
)

DEFAULT_CONTINUATION_PROMPT = (
    "Your previous response was cut off because it exceeded the output limit. "
    "Continue from where you left off."
)


class AgentLoopImpl(AgentLoop):
    """
    Implementation of the agent_loop interface using the OpenAI API.
    """

    def __init__(
        self,
        config: AgentLoopConfig,
        conversation_history: ConversationHistory,
        loop_guard: LoopGuard,
    ) -> None:
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
        )
        self._history = conversation_history
        self._guard = loop_guard

    def _invoke_logger(
        self, logger: Optional[LoggerCallback], event: LogEvent, data: Dict[str, Any]
    ) -> None:
        """Invoke the logger callback, catching and ignoring exceptions."""
        if logger is None:
            return
        try:
            logger(event, data)
        except Exception:
            pass

    def _extract_usage(self, response: Any, duration_seconds: float = 0.0) -> Usage:
        """Extract per-request token usage and timing from an OpenAI API response."""
        if hasattr(response, "usage") and response.usage is not None:
            input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(response.usage, "completion_tokens", 0) or 0
            total_tokens = getattr(response.usage, "total_tokens", 0) or 0

            cached_tokens = 0
            details = getattr(response.usage, "prompt_tokens_details", None)
            if details is not None:
                if isinstance(details, dict):
                    cached_tokens = details.get("cached_tokens", 0) or 0
                else:
                    cached_tokens = getattr(details, "cached_tokens", 0) or 0

            non_cached_tokens = max(0, input_tokens - cached_tokens)
            return {
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_tokens,
                "non_cached_input_tokens": non_cached_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "duration_seconds": round(duration_seconds, 3),
                "prompt_tokens": input_tokens,
                "cached_prompt_tokens": cached_tokens,
                "non_cached_prompt_tokens": non_cached_tokens,
                "completion_tokens": output_tokens,
            }
        return {}

    def _update_cumulative_usage(
        self, cumulative: CumulativeUsage, usage: Usage
    ) -> CumulativeUsage:
        """Update cumulative usage with per-request usage and timing."""
        input_tok = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        cached_tok = usage.get("cached_input_tokens", usage.get("cached_prompt_tokens", 0))
        non_cached_tok = usage.get("non_cached_input_tokens", usage.get("non_cached_prompt_tokens", 0))
        output_tok = usage.get("output_tokens", usage.get("completion_tokens", 0))
        total_tok = usage.get("total_tokens", 0)

        cum_input = cumulative.get("input_tokens", cumulative.get("prompt_tokens", 0)) + input_tok
        cum_cached = cumulative.get("cached_input_tokens", cumulative.get("cached_prompt_tokens", 0)) + cached_tok
        cum_non_cached = cumulative.get("non_cached_input_tokens", cumulative.get("non_cached_prompt_tokens", 0)) + non_cached_tok
        cum_output = cumulative.get("output_tokens", cumulative.get("completion_tokens", 0)) + output_tok
        cum_total = cumulative.get("total_tokens", 0) + total_tok

        return {
            "input_tokens": cum_input,
            "cached_input_tokens": cum_cached,
            "non_cached_input_tokens": cum_non_cached,
            "output_tokens": cum_output,
            "total_tokens": cum_total,
            "request_count": cumulative.get("request_count", 0) + 1,
            "total_duration_seconds": round(
                cumulative.get("total_duration_seconds", 0.0) + usage.get("duration_seconds", 0.0), 3
            ),
            "prompt_tokens": cum_input,
            "cached_prompt_tokens": cum_cached,
            "non_cached_prompt_tokens": cum_non_cached,
            "completion_tokens": cum_output,
        }

    def _log_api_response(self, logger: Optional[LoggerCallback]) -> None:
        self._invoke_logger(logger, "api_response", {})

    def _log_response_truncated(
        self,
        logger: Optional[LoggerCallback],
        message: HistoryEntry,
        usage: Optional[Usage] = None,
    ) -> None:
        self._invoke_logger(logger, "response_truncated", {"message": message})

    def _log_run_terminated(
        self,
        logger: Optional[LoggerCallback],
        termination_value: Any,
        response: Any,
        cumulative_usage: CumulativeUsage,
    ) -> None:
        if logger is None:
            return
        usage = self._extract_usage(response) if response is not None else {}
        final_context_size = usage.get("prompt_tokens", 0)
        self._invoke_logger(
            logger,
            "run_terminated",
            {
                "termination_value": termination_value,
                "usage": usage,
                "cumulative_usage": cumulative_usage,
                "final_context_size": final_context_size,
            },
        )

    def _log_reminder_injected(
        self, logger: Optional[LoggerCallback], reminder: str
    ) -> None:
        self._invoke_logger(logger, "reminder_injected", {"message": reminder})

    def _log_error(
        self,
        logger: Optional[LoggerCallback],
        error_msg: str,
        usage: Optional[Usage] = None,
        cumulative_usage: Optional[CumulativeUsage] = None,
    ) -> None:
        if logger is None:
            return
        data: Dict[str, Any] = {"error": error_msg}
        if usage is not None:
            data["usage"] = usage
            data["last_context_size"] = usage.get("prompt_tokens", 0)
        if cumulative_usage is not None:
            data["cumulative_usage"] = cumulative_usage
        self._invoke_logger(logger, "error", data)

    @staticmethod
    def _convert_tool_call_to_dict(tc: Any) -> ToolCall:
        """Convert an OpenAI function tool call to our ToolCall dict format."""
        tc_id = getattr(tc, "id", "") or (tc.get("id", "") if isinstance(tc, dict) else "")
        tc_type = getattr(tc, "type", "function") or (tc.get("type", "function") if isinstance(tc, dict) else "function")
        fn = getattr(tc, "function", None) or (tc.get("function") if isinstance(tc, dict) else None)
        fn_name = getattr(fn, "name", "") if fn is not None else ""
        if not fn_name and isinstance(fn, dict):
            fn_name = fn.get("name", "")
        fn_args = getattr(fn, "arguments", "") if fn is not None else ""
        if not fn_args and isinstance(fn, dict):
            fn_args = fn.get("arguments", "")
        return {
            "id": tc_id,
            "type": tc_type,
            "function": {
                "name": fn_name,
                "arguments": fn_args,
            },
        }

    @staticmethod
    def _convert_openai_message_to_dict(message: Any) -> HistoryEntry:
        """Convert OpenAI response message to our Message dict format."""
        msg: HistoryEntry = {"role": "assistant"}
        content = getattr(message, "content", None) if not isinstance(message, dict) else message.get("content")
        msg["content"] = content

        raw_tool_calls = (
            getattr(message, "tool_calls", None)
            if not isinstance(message, dict)
            else message.get("tool_calls")
        )
        if raw_tool_calls:
            converted = []
            for tc in raw_tool_calls:
                converted.append(AgentLoopImpl._convert_tool_call_to_dict(tc))
            msg["tool_calls"] = converted
        return msg

    def _handle_tool_calls(
        self,
        tool_calls: List[ToolCall],
        tool_executor: ToolExecutor,
        logger: Optional[LoggerCallback],
        last_usage: Optional[Usage],
        cumulative_usage: CumulativeUsage,
    ) -> Tuple[bool, Optional[AgentResult]]:
        """Handle tool calls from the model."""
        self._invoke_logger(logger, "tool_called", {"tool_calls": tool_calls})
        outcomes: List[Tuple[ToolCall, Optional[Union[ToolResult, PresentedToolResult]]]] = []

        for tool_call in tool_calls:
            name = tool_call.get("function", {}).get("name", "")
            raw_args = tool_call.get("function", {}).get("arguments", "")
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                arguments = {}

            # Evaluate repetition guardrails
            is_stop, reminder, error_msg = self._guard.record_tool_call(tool_call)
            if reminder is not None:
                reminder_message: HistoryEntry = {"role": "user", "content": reminder}
                self._history.append_message(reminder_message, logger)
                self._log_reminder_injected(logger, reminder)
            if is_stop and error_msg is not None:
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (True, (error_msg, self._history.get_history()))

            try:
                outcome = tool_executor(name, arguments)
            except Exception as e:
                error = f"Tool executor failed: {str(e)}"
                self._log_error(logger, error, last_usage, cumulative_usage)
                return (True, (error, self._history.get_history()))

            if isinstance(outcome, list):
                for item in outcome:
                    outcomes.append((tool_call, item))
            elif isinstance(outcome, Continue):
                continue
            elif isinstance(outcome, TerminateAgentWithSuccess):
                self._log_run_terminated(logger, outcome.value, None, cumulative_usage)
                return (True, (outcome, self._history.get_history()))
            elif isinstance(outcome, TerminateAgentWithFailure):
                self._log_run_terminated(logger, outcome.value, None, cumulative_usage)
                return (True, (outcome, self._history.get_history()))
            elif isinstance(outcome, ToolFailure):
                outcomes.append((
                    tool_call,
                    ToolResult(content=outcome.value, supersedes=False),
                ))
            else:
                error = f"Tool executor returned unexpected type: {type(outcome).__name__}"
                self._log_error(logger, error, last_usage, cumulative_usage)
                return (True, (error, self._history.get_history()))

        if outcomes:
            self._invoke_logger(
                logger,
                "tool_result",
                {
                    "results": [
                        r.result if isinstance(r, PresentedToolResult) else r
                        for _, r in outcomes
                        if r is not None
                    ]
                },
            )
            for tool_call, tool_result in outcomes:
                if tool_result is not None:
                    self._history.add_tool_result(tool_call, tool_result, logger)

        return (False, None)

    def run_agent(
        self,
        prompt: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        system_prompt: Optional[str] = None,
        session_start_results: Optional[List[PresentedToolResult]] = None,
        logger: Optional[LoggerCallback] = None,
    ) -> AgentResult:
        """Run the agent loop to answer a user prompt."""
        self._history.initialize(prompt, session_start_results, logger)
        self._guard.reset()

        iterations = 0
        last_usage: Optional[Usage] = None
        cumulative_usage: CumulativeUsage = {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "non_cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "request_count": 0,
            "total_duration_seconds": 0.0,
            "prompt_tokens": 0,
            "cached_prompt_tokens": 0,
            "non_cached_prompt_tokens": 0,
            "completion_tokens": 0,
        }

        while iterations < self._config.max_iterations:
            iterations += 1
            current_tools: List[ToolDefinition] = tool_executor.get_tool_definitions()
            openai_messages = self._history.get_rendered_messages(system_prompt)

            api_params: Dict[str, Any] = {
                "messages": openai_messages,
                "model": self._config.model,
                "temperature": self._config.temperature,
                "max_tokens": self._config.max_tokens,
            }
            if current_tools:
                api_params["tools"] = cast(List[ChatCompletionToolParam], current_tools)
                api_params["tool_choice"] = "auto"

            t0 = time.perf_counter()
            try:
                response = self._client.chat.completions.create(**api_params)
            except Exception as e:
                error_msg = f"API call failed: {str(e)}"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (error_msg, self._history.get_history())
            duration_seconds = time.perf_counter() - t0

            usage = self._extract_usage(response, duration_seconds)
            last_usage = usage
            cumulative_usage = self._update_cumulative_usage(cumulative_usage, usage)
            self._log_api_response(logger)

            if not response.choices or len(response.choices) == 0:
                error_msg = "API returned empty response"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (error_msg, self._history.get_history())

            choice = response.choices[0]
            message = choice.message
            finish_reason = choice.finish_reason
            assistant_message = self._convert_openai_message_to_dict(message)

            if finish_reason == "length":
                truncated_message = dict(assistant_message)
                truncated_message.pop("tool_calls", None)
                content = truncated_message.get("content")
                if self._guard.check_degenerate_response(content):
                    error_msg = "Degenerate truncated response: single character repeated"
                    self._log_error(logger, error_msg, last_usage, cumulative_usage)
                    return (error_msg, self._history.get_history())
                if content is not None:
                    self._history.append_message(truncated_message, logger)
                self._log_response_truncated(logger, truncated_message, usage)

                continuation = (
                    self._config.continuation_prompt or DEFAULT_CONTINUATION_PROMPT
                )
                continuation_message: HistoryEntry = {
                    "role": "user",
                    "content": continuation,
                }
                self._history.append_message(continuation_message, logger)
                continue

            self._history.append_message(assistant_message, logger)

            if finish_reason == "stop":
                if message.content is not None:
                    reminder = self._guard.get_termination_reminder()
                    reminder_message = {"role": "user", "content": reminder}
                    self._history.append_message(reminder_message, logger)
                    self._log_reminder_injected(logger, reminder)
                    continue

                error_msg = "API returned stop but no content"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (error_msg, self._history.get_history())

            if finish_reason == "tool_calls":
                raw_tool_calls = getattr(message, "tool_calls", None) or (
                    message.get("tool_calls") if isinstance(message, dict) else None
                )
                if not raw_tool_calls:
                    error_msg = "API indicated tool_calls but no tool_calls present"
                    self._log_error(logger, error_msg, last_usage, cumulative_usage)
                    return (error_msg, self._history.get_history())

                converted_tool_calls: List[ToolCall] = assistant_message.get("tool_calls") or []
                if not converted_tool_calls:
                    error_msg = "No valid function tool calls found"
                    self._log_error(logger, error_msg, last_usage, cumulative_usage)
                    return (error_msg, self._history.get_history())

                stop, result = self._handle_tool_calls(
                    converted_tool_calls,
                    tool_executor,
                    logger,
                    last_usage,
                    cumulative_usage,
                )
                if stop and result is not None:
                    return result
                continue

            if finish_reason == "content_filter":
                error_msg = f"Incomplete response: {finish_reason}"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (error_msg, self._history.get_history())

            error_msg = f"Unknown finish_reason: {finish_reason}"
            self._log_error(logger, error_msg, last_usage, cumulative_usage)
            return (error_msg, self._history.get_history())

        error_msg = f"Maximum iterations ({self._config.max_iterations}) exceeded"
        self._log_error(logger, error_msg, last_usage, cumulative_usage)
        return (error_msg, self._history.get_history())
