"""
lib/agent_loop_impl.py

Agent Loop Implementation - LLS Specification

Provides the agent loop implementation using the OpenAI API.
"""

import json
from typing import Any, cast, List, Dict, Optional, Tuple, Union

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam

from .agent_loop import (
    AgentLoop,
    HistoryEntry,
    ToolCall,
    AgentResult,
    LoggerCallback,
    LogEvent,
    Usage,
    CumulativeUsage,
    AgentLoopConfig,
    FinalAnswer,
)
from .tool_provider import (
    ToolDefinition,
    ToolResult,
    ToolExecutor,
    Continue,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    ToolFailure,
)

# Pinned default continuation prompt (specs/agent_loop_impl-low.md,
# Non-Concerns): appended as a user message when a response is truncated at
# the generation limit and no continuation_prompt is configured.
DEFAULT_CONTINUATION_PROMPT = (
    "Your previous response was cut off because it exceeded the output limit. "
    "Continue from where you left off."
)


class AgentLoopImpl(AgentLoop):
    """
    Implementation of the agent_loop interface using the OpenAI API.

    Operation Implemented: agent_loop.run_agent
    """

    def __init__(
        self,
        config: AgentLoopConfig,
    ) -> None:
        """
        Initialize the agent loop implementation.

        Preconditions:
        - config must contain valid connection parameters
        """
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
        )
        # Per-run loop-repetition state (reset at each run_agent; no state
        # persists between runs): consecutive identical tool calls (same name
        # and arguments) trigger a reminder so the agent cannot spin forever
        # on the same call.
        self._loop_last_signature: Optional[Tuple[str, str]] = None
        self._loop_repeat_count = 0
        self._loop_reminder_injected = False

    def _convert_tool_call_to_dict(self, tc: ChatCompletionMessageFunctionToolCall) -> ToolCall:
        """Convert an OpenAI function tool call to our ToolCall dict format."""
        return {
            "id": tc.id,
            "type": tc.type,
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        }

    def _clean_message_for_openai(self, msg: HistoryEntry) -> HistoryEntry:
        """Remove internal metadata fields before sending to OpenAI."""
        return {k: v for k, v in msg.items() if not k.startswith("_")}

    def _convert_message_to_openai(
        self, msg: HistoryEntry
    ) -> Union[
        ChatCompletionUserMessageParam,
        ChatCompletionAssistantMessageParam,
        ChatCompletionToolMessageParam,
        ChatCompletionSystemMessageParam,
    ]:
        """Convert our Message dict to OpenAI message format."""
        # Remove internal metadata fields
        clean_msg = self._clean_message_for_openai(msg)
        
        role = clean_msg.get("role")
        if role == "user":
            return cast(ChatCompletionUserMessageParam, {"role": "user", "content": clean_msg.get("content")})
        elif role == "assistant":
            assistant_msg: ChatCompletionAssistantMessageParam = {"role": "assistant"}
            if "content" in clean_msg:
                assistant_msg["content"] = clean_msg.get("content")
            if "tool_calls" in clean_msg and clean_msg.get("tool_calls"):
                tool_calls = clean_msg.get("tool_calls")
                if tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": tc.get("function", {}).get("arguments", ""),
                            },
                        }
                        for tc in tool_calls
                    ]
            return assistant_msg
        elif role == "tool":
            # The tool result's note (e.g. remaining-length guidance) is
            # rendered into the model-visible content so the agent always
            # sees it during model execution.
            content = clean_msg.get("content", "")
            note = msg.get("_note", "")
            if note:
                content = content + ("\n" if content else "") + note
            return cast(ChatCompletionToolMessageParam, {
                "role": "tool",
                "tool_call_id": clean_msg.get("tool_call_id", ""),
                "content": content,
            })
        elif role == "system":
            return cast(ChatCompletionSystemMessageParam, {"role": "system", "content": clean_msg.get("content")})
        else:
            raise ValueError(f"Unknown message role: {role}")

    def _convert_openai_message_to_dict(self, message: ChatCompletionMessage) -> HistoryEntry:
        """Convert OpenAI message to our Message dict format."""
        msg: HistoryEntry = {"role": "assistant"}
        
        if message.content is not None:
            msg["content"] = message.content
        else:
            msg["content"] = None

        if message.tool_calls:
            converted_tool_calls = []
            for tc in message.tool_calls:
                if isinstance(tc, ChatCompletionMessageFunctionToolCall):
                    converted_tool_calls.append(self._convert_tool_call_to_dict(tc))
                else:
                    print(f"Warning: Skipping custom tool call: {tc}")
            msg["tool_calls"] = converted_tool_calls

        return msg

    def _invoke_logger(self, logger: Optional[LoggerCallback], event: LogEvent, data: Dict[str, Any]) -> None:
        """Invoke the logger callback, catching and ignoring exceptions."""
        if logger is None:
            return
        try:
            logger(event, data)
        except Exception:
            # Logger callback exceptions are caught and ignored per HLS guarantee
            pass

    def _append_message(self, messages: List[HistoryEntry], message: HistoryEntry, logger: Optional[LoggerCallback]) -> None:
        """Append a message to the conversation and invoke logger if provided."""
        messages.append(message)
        self._invoke_logger(logger, "message_added", {"message": message})

    def _find_existing_tool_result_by_content_id(
        self, 
        messages: List[HistoryEntry], 
        content_id: str
    ) -> List[int]:
        """
        Find indices of all existing non-stubbed tool result messages with the same content_id.
        
        Returns list of indices, empty if none found.
        """
        indices = []
        for i, msg in enumerate(messages):
            # Only consider tool messages that aren't already stubbed and have matching content_id
            if (msg.get("role") == "tool" and 
                msg.get("_content_id") == content_id and
                not msg.get("_stubbed", False)):
                indices.append(i)
        return indices

    def _stub_tool_result(
        self,
        messages: List[HistoryEntry],
        index: int,
        replacement_message: HistoryEntry,
        logger: Optional[LoggerCallback]
    ) -> None:
        """
        Stub a tool result by replacing its content with a placeholder.
        
        The message retains its position and metadata but content is replaced.
        """
        original = messages[index]
        stubbed = dict(original)
        stubbed["content"] = "Content removed because newer version is available"
        stubbed["_stubbed"] = True
        messages[index] = stubbed
        
        self._invoke_logger(logger, "message_stubbed", {
            "content_id": original.get("_content_id"),
            "stubbed_message": stubbed,
            "replacement_message": replacement_message,
        })

    def _add_tool_result(
        self, 
        messages: List[HistoryEntry], 
        tool_call: ToolCall, 
        result: ToolResult,
        logger: Optional[LoggerCallback]
    ) -> None:
        """
        Add a tool result to the conversation with content_id-based stubbing.

        Follows tool_provider semantics exactly:
        - If content_id is None: result appended unconditionally
        - If stub_previous is True: all previous non-stubbed results with same content_id
          have their content replaced with a stub, then new result is appended
        - If stub_previous is False: new result appended without stubbing
        """
        tool_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]
        content_id = result.content_id
        stub_previous = result.stub_previous
        
        # Build message with internal metadata
        new_message: HistoryEntry = {
            "role": "tool",
            "tool_call_id": tool_call["id"],  # Use tool_call_id from the tool call
            "content": result.content,
            "_tool_name": tool_name,
            "_arguments": arguments,
            "_content_id": content_id,
            "_stub_previous": stub_previous,
            "_note": result.note,
        }
        
        # If content_id is None, append unconditionally (opt-out)
        if content_id is None:
            messages.append(new_message)
            self._invoke_logger(logger, "message_added", {"message": new_message})
            return
        
        # If stub_previous is True, stub all previous non-stubbed results with same content_id
        if stub_previous:
            existing_indices = self._find_existing_tool_result_by_content_id(messages, content_id)
            for idx in existing_indices:
                self._stub_tool_result(messages, idx, new_message, logger)
        
        # Append the new result
        messages.append(new_message)
        self._invoke_logger(logger, "message_added", {"message": new_message})

    def _extract_usage(self, response: Any) -> Usage:
        """Extract per-request token usage from an OpenAI API response."""
        if hasattr(response, "usage") and response.usage is not None:
            return {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        return {}

    def _update_cumulative_usage(self, cumulative: CumulativeUsage, usage: Usage) -> CumulativeUsage:
        """Update cumulative usage with per-request usage."""
        return {
            "prompt_tokens": cumulative.get("prompt_tokens", 0) + usage.get("prompt_tokens", 0),
            "completion_tokens": cumulative.get("completion_tokens", 0) + usage.get("completion_tokens", 0),
            "total_tokens": cumulative.get("total_tokens", 0) + usage.get("total_tokens", 0),
            "request_count": cumulative.get("request_count", 0) + 1,
        }

    def _log_api_response(self, logger: Optional[LoggerCallback], response: Any) -> None:
        """Log API response with per-request token usage."""
        if logger is None:
            return
        
        usage = self._extract_usage(response)
        self._invoke_logger(logger, "api_response", {"usage": usage})

    def _log_response_truncated(
        self,
        logger: Optional[LoggerCallback],
        message: HistoryEntry,
        usage: Usage,
    ) -> None:
        """Log a truncated response (the model stopped at the generation limit)."""
        if logger is None:
            return
        
        self._invoke_logger(logger, "response_truncated", {
            "message": message,
            "usage": usage,
        })

    def _log_final_answer(
        self, 
        logger: Optional[LoggerCallback], 
        answer: str, 
        response: Any, 
        cumulative_usage: CumulativeUsage
    ) -> None:
        """Log final answer with per-request, cumulative usage, and final context size."""
        if logger is None:
            return
        
        usage = self._extract_usage(response)
        final_context_size = usage.get("prompt_tokens", 0)
        
        self._invoke_logger(logger, "final_answer", {
            "answer": answer,
            "usage": usage,
            "cumulative_usage": cumulative_usage,
            "final_context_size": final_context_size,
        })

    def _log_run_terminated(
        self,
        logger: Optional[LoggerCallback],
        termination_value: Any,
        response: Any,
        cumulative_usage: CumulativeUsage
    ) -> None:
        """Log run termination with termination value, usage, and cumulative usage."""
        if logger is None:
            return
        
        usage = self._extract_usage(response) if response is not None else {}
        final_context_size = usage.get("prompt_tokens", 0)
        
        self._invoke_logger(logger, "run_terminated", {
            "termination_value": termination_value,
            "usage": usage,
            "cumulative_usage": cumulative_usage,
            "final_context_size": final_context_size,
        })

    def _log_reminder_injected(
        self,
        logger: Optional[LoggerCallback],
        reminder: str
    ) -> None:
        """Log termination reminder injection."""
        if logger is None:
            return
        
        self._invoke_logger(logger, "reminder_injected", {"message": reminder})

    def _log_error(
        self, 
        logger: Optional[LoggerCallback], 
        error_msg: str, 
        usage: Optional[Usage] = None,
        cumulative_usage: Optional[CumulativeUsage] = None
    ) -> None:
        """Log error with optional usage and cumulative usage."""
        if logger is None:
            return
        
        data: Dict[str, Any] = {"error": error_msg}
        
        if usage is not None:
            data["usage"] = usage
            data["last_context_size"] = usage.get("prompt_tokens", 0)
        
        if cumulative_usage is not None:
            data["cumulative_usage"] = cumulative_usage
        
        self._invoke_logger(logger, "error", data)

    def _inject_loop_reminder(
        self,
        messages: List[HistoryEntry],
        logger: Optional[LoggerCallback],
        tool_name: str,
        count: int,
    ) -> None:
        """Inject a reminder when the same tool call repeats without progress."""
        reminder = (
            f"You have called '{tool_name}' with the same arguments {count} "
            f"times in a row. Review the latest tool results and make progress: "
            f"change the file (edit_file/replace_lines/write_file) or finish "
            f"the run with succeed(), fail(), or blame()."
        )
        reminder_message: HistoryEntry = {"role": "user", "content": reminder}
        messages.append(reminder_message)
        # The reminder is appended to the conversation like any other message:
        # report the append via message_added in addition to the reminder event.
        self._invoke_logger(logger, "message_added", {"message": reminder_message})
        self._log_reminder_injected(logger, reminder)

    def _inject_termination_reminder(
        self,
        messages: List[HistoryEntry],
        logger: Optional[LoggerCallback],
        injected: bool
    ) -> bool:
        """
        Inject a termination reminder if configured and not already injected.

        Returns True if reminder was injected, False otherwise.
        """
        if self._config.termination_reminder_generator is None:
            return False
        
        if injected:
            return False
        
        reminder = self._config.termination_reminder_generator()
        reminder_message: HistoryEntry = {"role": "user", "content": reminder}
        messages.append(reminder_message)
        # The reminder is appended to the conversation like any other message:
        # report the append via message_added in addition to the reminder
        # event (per the LLS "invokes the logger after each history update").
        self._invoke_logger(logger, "message_added", {"message": reminder_message})
        self._log_reminder_injected(logger, reminder)
        
        return True

    def _handle_tool_calls(
        self,
        tool_calls: List[ToolCall],
        tool_executor: ToolExecutor,
        messages: List[HistoryEntry],
        logger: Optional[LoggerCallback],
        last_usage: Optional[Usage],
        cumulative_usage: CumulativeUsage,
        reminder_injected: bool,
    ) -> tuple[bool, Optional[AgentResult], bool]:
        """
        Handle tool calls from the model.

        Returns:
            - (False, None, reminder_injected): Continue the loop
            - (True, result, reminder_injected): Stop with result (termination or failure)
        """
        self._invoke_logger(logger, "tool_called", {"tool_calls": tool_calls})

        # The tool executor is per-call (tool_provider.ToolExecutor): invoked
        # once per tool call with (name, arguments), returning a ToolCallOutcome.
        outcomes: List[Tuple[ToolCall, Optional[ToolResult]]] = []

        for tool_call in tool_calls:
            name = tool_call["function"]["name"]
            raw_args = tool_call["function"]["arguments"]
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                arguments = {}

            # Loop-repetition detection: consecutive identical tool calls
            # (same name and arguments) inject a reminder once per run, so the
            # agent cannot spin forever on the same call.
            signature = (name, json.dumps(arguments, sort_keys=True))
            if signature == self._loop_last_signature:
                self._loop_repeat_count += 1
            else:
                self._loop_last_signature = signature
                self._loop_repeat_count = 1
            if self._loop_repeat_count >= 4 and not self._loop_reminder_injected:
                self._loop_reminder_injected = True
                self._inject_loop_reminder(messages, logger, name, self._loop_repeat_count)

            try:
                outcome = tool_executor(name, arguments)
            except Exception as e:
                error_msg = f"Tool executor failed: {str(e)}"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (True, (error_msg, messages), reminder_injected)

            if isinstance(outcome, ToolResult):
                outcomes.append((tool_call, outcome))
            elif isinstance(outcome, Continue):
                # Continue signal - no tool result for this call
                continue
            elif isinstance(outcome, TerminateAgentWithSuccess):
                # Agent-initiated successful termination (success or blame;
                # the value is the TerminateSuccessResult) - stop and return
                # the signal paired with the history
                self._log_run_terminated(logger, outcome.value, None, cumulative_usage)
                return (True, (outcome, messages), reminder_injected)
            elif isinstance(outcome, TerminateAgentWithFailure):
                # Agent-initiated failure termination - the agent decided it
                # cannot complete the task; return the signal paired with the
                # history (a failure termination, not a loop failure)
                self._log_run_terminated(logger, outcome.value, None, cumulative_usage)
                return (True, (outcome, messages), reminder_injected)
            elif isinstance(outcome, ToolFailure):
                # Tool failure - the agent misused a tool. The failure message
                # (e.g., the sandbox's reminder of what the agent can do) is
                # appended to the conversation and the loop continues. Tool
                # failures are recoverable: no session reset, no history
                # clearing, and no agent failure.
                outcomes.append((
                    tool_call,
                    ToolResult(content=outcome.value, content_id=None, stub_previous=False),
                ))
            else:
                error_msg = f"Tool executor returned unexpected type: {type(outcome).__name__}"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (True, (error_msg, messages), reminder_injected)

        if outcomes:
            self._invoke_logger(logger, "tool_result", {"results": [r for _, r in outcomes]})
            # Add each result with stubbing semantics
            for tool_call, tool_result in outcomes:
                if tool_result is not None:
                    self._add_tool_result(messages, tool_call, tool_result, logger)

        return (False, None, reminder_injected)

    def run_agent(
        self,
        prompt: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        logger: Optional[LoggerCallback] = None,
    ) -> AgentResult:
        """
        Run the agent loop to answer a user prompt.

        Operation Implemented: agent_loop.run_agent

        Preconditions:
        - prompt must be a non-empty string
        - tools must be a list of valid tool definitions
        - tool_executor must be a callable that accepts (name, arguments) per tool
          call (tool_provider.ToolExecutor) and returns a ToolCallOutcome
        - logger, if provided, must be a callable that accepts (LogEvent, dict) and returns None
        - Component must be configured with connection parameters
        - No concurrent calls to run_agent (behavior is undefined)

        Postconditions:
        - Returns FinalAnswer, a (signal, history) termination tuple, or an
          (error, history) loop-failure tuple
        - On failure, state remains unchanged
        - Conversation order is maintained across iterations
        - Tool results immediately follow the tool calls they reference
        - At most one non-stubbed tool result per unique content_id when stub_previous=True
        - The operation completes when a final answer is produced, termination is signaled,
          or failure occurs
        - No state persists between calls
        - The component does not cache or persist conversation history
        - If logger is provided, invokes it for significant events in chronological order
        - Catches and ignores logger callback exceptions
        - Internal metadata fields (_content_id, _stub_previous) are stripped before sending to OpenAI
        - Token usage is tracked and included in logger events

        Message Routing:
        - Tool calls are delegated to the tool_executor (once per tool call)
        - Tool results are incorporated into the conversation with content_id-based stubbing
        - ToolFailure outcomes append the failure message and continue (recoverable)

        Ordering:
        - Conversation messages are maintained in chronological order
        - Tool results immediately follow the tool calls they reference
        - Logger callbacks are invoked after data is appended to the conversation
        - When a tool result is stubbed, the stubbed message remains in its original position
        - New results are appended at the end
        - Stubbing occurs before the new result is produced

        Failure Handling:
        - Returns (error, history) if:
          - API call fails
          - API returns malformed response
          - Tool executor raises an exception
          - Maximum iterations exceeded
        - Tool failures (ToolFailure from the tool executor) are recoverable: the
          failure message is appended and the loop continues
        - Logger callback exceptions are caught and ignored
        - Does not raise exceptions for expected failure conditions
        """
        if not prompt or not prompt.strip():
            return ("Prompt must be a non-empty string", [])

        messages: List[HistoryEntry] = [{"role": "user", "content": prompt}]
        self._invoke_logger(logger, "message_added", {"message": messages[0]})

        iterations = 0
        last_usage: Optional[Usage] = None
        cumulative_usage: CumulativeUsage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "request_count": 0,
        }
        reminder_injected = False
        # Reset per-run loop-repetition state (no state persists between runs).
        self._loop_last_signature = None
        self._loop_repeat_count = 0
        self._loop_reminder_injected = False

        while iterations < self._config.max_iterations:
            iterations += 1

            openai_messages = [
                self._convert_message_to_openai(msg) for msg in messages
            ]

            # Prepare API call parameters
            api_params: Dict[str, Any] = {
                "messages": openai_messages,
                "model": self._config.model,
                "temperature": self._config.temperature,
                "max_tokens": self._config.max_tokens,
            }
            
            # Only include tools and tool_choice if tools are provided
            if tools:
                api_params["tools"] = cast(List[ChatCompletionToolParam], tools)
                api_params["tool_choice"] = "auto"

            try:
                response = self._client.chat.completions.create(**api_params)
            except Exception as e:
                error_msg = f"API call failed: {str(e)}"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (error_msg, messages)

            # Extract and track usage
            usage = self._extract_usage(response)
            last_usage = usage
            cumulative_usage = self._update_cumulative_usage(cumulative_usage, usage)

            # Log API response with usage
            self._log_api_response(logger, response)

            if not response.choices or len(response.choices) == 0:
                error_msg = "API returned empty response"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (error_msg, messages)

            choice = response.choices[0]
            message = choice.message

            finish_reason = choice.finish_reason
            assistant_message = self._convert_openai_message_to_dict(message)

            if finish_reason == "length":
                # Truncated response: the model stopped at the generation
                # limit, not because it completed naturally. It is not a
                # final answer. Any tool calls in the truncated response are
                # omitted from the appended assistant message: they may be
                # malformed or incomplete and are never executed or retried.
                # Generation resumes with a follow-up request after the
                # continuation prompt is appended (per the interface LLS).
                truncated_message = dict(assistant_message)
                truncated_message.pop("tool_calls", None)
                content = truncated_message.get("content")
                # Degenerate truncated response: non-empty content whose
                # characters are all identical (a single character repeated).
                # Resuming would feed the degenerate loop, so the run signals
                # failure instead; nothing is appended (per the impl LLS).
                if isinstance(content, str) and len(content) > 0 and len(set(content)) == 1:
                    error_msg = "Degenerate truncated response: single character repeated"
                    self._log_error(logger, error_msg, last_usage, cumulative_usage)
                    return (error_msg, messages)
                if content is not None:
                    self._append_message(messages, truncated_message, logger)
                self._log_response_truncated(logger, truncated_message, usage)

                continuation = (
                    self._config.continuation_prompt or DEFAULT_CONTINUATION_PROMPT
                )
                continuation_message: HistoryEntry = {
                    "role": "user",
                    "content": continuation,
                }
                messages.append(continuation_message)
                self._invoke_logger(logger, "message_added", {"message": continuation_message})
                continue

            self._append_message(messages, assistant_message, logger)

            if finish_reason == "stop":
                # Model provided a final answer
                if message.content is not None:
                    # Check if we should inject a reminder instead
                    if self._config.termination_reminder_generator is not None and not reminder_injected:
                        # Inject reminder and continue loop
                        reminder_injected = self._inject_termination_reminder(messages, logger, reminder_injected)
                        continue
                    
                    # No reminder needed or already injected - return final answer
                    self._log_final_answer(logger, message.content, response, cumulative_usage)
                    return FinalAnswer(answer=message.content, history=messages)
                
                error_msg = "API returned stop but no content"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (error_msg, messages)

            if finish_reason == "tool_calls":
                if not message.tool_calls:
                    error_msg = "API indicated tool_calls but no tool_calls present"
                    self._log_error(logger, error_msg, last_usage, cumulative_usage)
                    return (error_msg, messages)

                converted_tool_calls: List[ToolCall] = []
                for tc in message.tool_calls:
                    if isinstance(tc, ChatCompletionMessageFunctionToolCall):
                        converted_tool_calls.append(self._convert_tool_call_to_dict(tc))
                    else:
                        print(f"Warning: Skipping custom tool call: {tc}")

                if not converted_tool_calls:
                    error_msg = "No valid function tool calls found"
                    self._log_error(logger, error_msg, last_usage, cumulative_usage)
                    return (error_msg, messages)

                # Handle tool calls
                stop, result, reminder_injected = self._handle_tool_calls(
                    converted_tool_calls, tool_executor, messages, logger, last_usage, cumulative_usage, reminder_injected
                )
                if stop and result is not None:
                    return result

                # Continue the loop: no reminder is injected on the tool-call
                # path (the reminder is only injected on the stop path, at
                # most once per run, per the implementation spec).
                continue

            if finish_reason == "content_filter":
                error_msg = f"Incomplete response: {finish_reason}"
                self._log_error(logger, error_msg, last_usage, cumulative_usage)
                return (error_msg, messages)

            error_msg = f"Unknown finish_reason: {finish_reason}"
            self._log_error(logger, error_msg, last_usage, cumulative_usage)
            return (error_msg, messages)

        error_msg = f"Maximum iterations ({self._config.max_iterations}) exceeded"
        self._log_error(logger, error_msg, last_usage, cumulative_usage)
        return (error_msg, messages)