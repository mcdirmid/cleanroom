# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T12:05:00Z
# CHANGE: Rebuild tools payload on each turn to reflect dynamically installed tools
# CODE_HASH: 890a9034cb50
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

import json
import time
from typing import Any, Mapping, Optional, Sequence, Tuple
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib.session import session as agent_session
from update_with_ai.parts.loop.lib import conversation, guard, driver
from . import openai_config
from update_with_ai.parts.loop.lib import logger as loop_logger
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

try:  # pragma: no cover (assumption: the openai dependency is installed in the runtime image)
    import importlib
    _openai: Any = importlib.import_module("openai")
    OpenAI, OpenAIError = _openai.OpenAI, _openai.OpenAIError
except (ImportError, AttributeError):  # pragma: no cover (assumption: the openai dependency is installed in the runtime image)
    OpenAI = None
    class _OpenAIError(Exception): pass
    OpenAIError: Any = _OpenAIError


# Contract: Repeated consecutive truncation failure limit before halting execution.
_CONSECUTIVE_TRUNCATION_LIMIT = 3

# Contract: Preview width used by compact runner log summaries; never dumps file content.
_LOG_PREVIEW_LIMIT = 60

# Contract: Identifies tools that modify workspace files.
_EDITING_TOOL_NAMES = frozenset({"replace_file_content"})

# Contract: Identifies tools that advance the progressive guide step.
_ADVANCING_TOOL_NAMES = frozenset({"advance"})

# Contract: Known suppression keys claimed by tool responses.
_DEDICATED_SUPPRESSION_KEYS = frozenset(
    {"replace_file_content", "advance", "submit", "check_files", "blame", "get_work", "fail"}
)

# Contract: Tool reminder prompt when a model response produces no tool executions.
_MISSING_TOOL_REMINDER = (
    "No tools were executed. A tool (e.g. view_file, replace_file_content, advance, fail, blame) "
    "must be called to make progress or conclude the session."
)

# Contract: Actionable corrective reminder advising strictly smaller edits upon truncation.
_TRUNCATION_REMINDER = (
    "Whole-file, multi-class, or monolithic replacements that exceed output token limits are "
    "prohibited. Make strictly small edits containing at most a single test method or fixture "
    "(at most 30-50 lines of code) using replace_file_content."
)

_INCOMPLETE_TOOL_CALL_ASSISTANT_NOTE = (
    "I attempted to execute a tool call, but the output exceeded the server's token limit and was "
    "rejected by the server."
)

# Contract: Actionable recovery notice directing smaller edits on incomplete tool call errors.
_INCOMPLETE_TOOL_CALL_RECOVERY = (
    "ERROR: Tool call generation exceeded the output token limit (max_tokens). The server rejected "
    "the incomplete tool invocation. Do NOT attempt to rewrite or replace an entire large file in a "
    "single tool call. Make strictly smaller edits: use `replace_file_content` to change small, "
    "targeted line ranges (at most 30-50 lines per call) and then continue."
)



class _RepeatedTruncationError(RuntimeError):
    """Signals that consecutive generations were rejected as incomplete tool calls."""


class _NoCompletionChoicesError(RuntimeError):
    """Signals that a completion response carried no choices."""


# Contract: Repairs unclosed tool arguments into valid JSON upon truncation at generation limit.
def _repair_json(raw: str) -> str:
    raw = raw.strip()
    if not raw: return "{}"
    try:
        if isinstance(json.loads(raw, strict=False), dict): return raw
    except (json.JSONDecodeError, ValueError): pass
    start_idx = raw.find("{")
    if start_idx == -1: return "{}"
    raw = raw[start_idx:]

    def try_close(cand: str) -> Optional[str]:
        in_str, esc, stack = False, False, []
        for ch in cand:
            if esc: esc = False; continue
            if ch == "\\": esc = True; continue
            if ch == '"': in_str = not in_str; continue
            if not in_str:
                if ch in "{[": stack.append("}" if ch == "{" else "]")
                elif ch in "}]" and stack and stack[-1] == ch: stack.pop()
        if esc: cand = cand[:-1]
        if in_str: cand += '"'
        trimmed = cand.rstrip()
        while trimmed.endswith(","): trimmed = trimmed[:-1].rstrip()
        for cand_str in (trimmed + "".join(reversed(stack)), trimmed + ': ""' + "".join(reversed(stack))):
            try:
                if isinstance(json.loads(cand_str, strict=False), dict): return cand_str
            except (json.JSONDecodeError, ValueError): pass
        return None

    res = try_close(raw)
    if res is not None: return res
    for i in range(len(raw) - 1, -1, -1):
        if raw[i] in (",", "{"):
            res = try_close(raw[: i + (1 if raw[i] == "{" else 0)])
            if res is not None: return res
    return "{}"


# Contract: Formats text to preview limit to prevent inlining file content in compact log summaries.
def _truncate_text(text: str, limit: int = _LOG_PREVIEW_LIMIT) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 3] + "..."


# Contract: Formats token usage and percentage of cached tokens for compact runner logging.
def _token_usage_summary(prompt_tokens: Optional[int], cached_tokens: Optional[int]) -> Tuple[str, str]:
    if prompt_tokens is None:
        return "initial request", "Conversation tokens: initial request (0% cached)"
    size_str = f"{int(round(prompt_tokens / 1000.0))}K tokens"
    pct = int(round((cached_tokens / prompt_tokens) * 100.0)) if cached_tokens and prompt_tokens > 0 else 0
    return f"{size_str}, {pct}% cached", f"Conversation tokens: {size_str} ({pct}% cached on last turn)"


# Contract: Formats tool invocation arguments compactly without inlining file content.
def _format_tool_call(fn_name: str, raw_arguments: str) -> Tuple[str, str]:
    try:
        parsed = json.loads(raw_arguments, strict=False) if raw_arguments else {}
    except (json.JSONDecodeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        arguments_log = ", ".join(f"{k}={_truncate_text(repr(v), 40)}" for k, v in parsed.items()) or "no arguments"
    else:
        arguments_log = _truncate_text(raw_arguments or "") or "no arguments"
    return f"{fn_name}({arguments_log})", arguments_log


# Contract: Formats tool execution result summary and transcript, including corrective reminders.
def _tool_result_summary(
    fn_name: str,
    arguments_log: str,
    tool_response: tool_provider.ToolResponse,
    turns: int,
    is_followup: bool = False,
) -> Tuple[str, str]:
    kind = "Follow-up Tool" if is_followup else "Tool"
    if tool_response.is_failed:
        status = "FAILED"
    elif tool_response.is_terminated:
        status = "TERMINATED"
    else:
        status = "COMPLETED"
    summary = f"[Turn {turns}] {kind} {fn_name}: {status} ({arguments_log})"
    transcript = (
        f"=== {kind} Result (turn {turns}) ===\n"
        f"Tool: {fn_name}\n"
        f"Status: {status}\n"
        f"Arguments: {arguments_log}\n"
        f"Result: {_truncate_text(str(tool_response.content or ''))}"
    )
    if tool_response.reminder:
        transcript += f"\n\nReminder: {tool_response.reminder}"
    return summary, transcript



def _find_tool(tool_mgr: Any, fn_name: str) -> Optional[tool_provider.Tool]:
    tools: Mapping[str, tool_provider.Tool] = getattr(tool_mgr, "installed_tools", {})
    found: Optional[tool_provider.Tool] = tools.get(fn_name)
    if found is not None: return found
    return next((t for t in tools.values() if str(t.name) == fn_name), None)


def _call_append_tool_response(
    history: Any,
    tool_response: tool_provider.ToolResponse,
    tool_call_id: str,
    tool_name: str,
    tool_arguments: str,
) -> None:
    history.append_tool_response(
        tool_response=tool_response,
        tool_call_id=conversation.ToolCallId(tool_call_id),
        tool_name=tool_provider.ToolName(tool_name),
        tool_arguments=conversation.SerializedArguments(tool_arguments),
    )


def _log_event(event_name: str, summary: str, transcript: str) -> loop_logger.RunnerLogEvent:
    return loop_logger.RunnerLogEvent(
        event_name=loop_logger.EventName(event_name),
        summary=loop_logger.EventSummary(summary),
        transcript=loop_logger.EventTranscript(transcript),
    )


def _conv_msg(role: str, content: str, tool_call_id: Optional[str] = None, tool_name: Optional[str] = None, tool_arguments: Optional[str] = None) -> conversation.ConversationMessage:
    return conversation.ConversationMessage(
        role=conversation.MessageRole(role),
        content=conversation.ConversationContent(content),
        tool_call_id=conversation.ToolCallId(tool_call_id) if tool_call_id is not None else None,
        tool_name=tool_provider.ToolName(tool_name) if tool_name is not None else None,
        tool_arguments=conversation.SerializedArguments(tool_arguments) if tool_arguments is not None else None,
    )


def _make_tool_response(is_failed: bool, is_terminated: bool, content: str, reminder: Optional[str] = None, suppression_key: Optional[str] = None) -> tool_provider.ToolResponse:
    return tool_provider.ToolResponse(
        is_failed=is_failed,
        is_terminated=is_terminated,
        content=tool_provider.ToolResponseContent(content),
        reminder=tool_provider.ToolReminder(reminder) if reminder is not None else None,
        suppression_key=tool_provider.SuppressionKey(suppression_key) if suppression_key is not None else None,
    )


def _build_actual_bindings(tool: Optional[tool_provider.Tool], args_dict: Mapping[str, Any]) -> Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]:
    res: dict[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType] = {}
    if tool is not None:
        tool_params = getattr(tool, "parameters", {})
        for k, v in args_dict.items():
            param = tool_params.get(tool_provider.ParameterName(k))
            if param is not None:
                pt = getattr(param, "parameter_type", None)
                if pt is not None:
                    try: res[param] = pt.convert(v)
                    except (ValueError, TypeError, KeyError): res[param] = v
                else:
                    res[param] = v
    return res


# Contract: Serializes tool parameters into JSON schema, deterministically preserving declared parameter sequence.
def _tool_parameters_schema(tool: tool_provider.Tool) -> dict[str, Any]:
    """Serializes tool parameters into a JSON schema preserving their declared sequence."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for parameter in tool.parameters.values():
        properties[str(parameter.name)] = {
            "type": "string",
            "description": str(parameter.description),
        }
        if parameter.is_required:
            required.append(str(parameter.name))
    return {"type": "object", "properties": properties, "required": required}


# Contract: Builds the wire tools payload ordering tools deterministically by tool name on each turn.
def _build_tools_payload(tool_mgr: Any) -> list[dict[str, Any]]:
    """Builds the wire tools payload ordering tools deterministically by tool name."""
    installed = list(tool_mgr.installed_tools.values())
    payload: list[dict[str, Any]] = []
    for tool in sorted(installed, key=lambda candidate: str(candidate.name)):
        payload.append({
            "type": "function",
            "function": {
                "name": str(tool.name),
                "description": str(tool.description),
                "parameters": _tool_parameters_schema(tool),
            },
        })
    return payload


# Contract: Formats conversation history into OpenAI-conforming messages payload.
def _build_messages_payload(history: Any) -> list[dict[str, Any]]:
    payload = []
    for m in history.get_model_request().messages:
        if m.role == "assistant" and m.tool_name:
            payload.append({"role": "assistant", "content": m.content or None, "tool_calls": [{
                "id": m.tool_call_id or "call_0", "type": "function", "function": {"name": m.tool_name, "arguments": m.tool_arguments or "{}"}
            }]})
        elif m.role == "tool":
            payload.append({"role": "tool", "content": m.content, "tool_call_id": m.tool_call_id or ""})
        else:
            payload.append({"role": m.role, "content": m.content})
    return payload


# Contract: Resolves tool suppression key for truncated tool failure responses.
def _truncated_suppression_key(fn_name: str, args_dict: Optional[Mapping[str, Any]]) -> str:
    if fn_name in _DEDICATED_SUPPRESSION_KEYS:
        return fn_name
    if args_dict:
        target_file = args_dict.get("path") or args_dict.get("target_file")
        if target_file:
            return str(target_file).split("/")[-1]
    return fn_name



class LoopDriver(driver.LoopDriver, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._truncation_identifier: int = 0
        self._turn_count: int = 0

    # Contract: Recovers truncated tool invocations by repairing unclosed arguments into valid JSON and resuming with continuation turn.
    def _handle_length_truncation(self, tool_calls: Sequence[Any], turns: int, history: Any, logger: Any, guard: Any, tool_mgr: Any) -> None:
        """Recovers a generation truncated at the token limit and resumes with a continuation turn."""
        if not tool_calls:
            # Contract: Append prompt reminding of generation limit and directing smaller edits.
            history.append_message(_conv_msg("user", "Generation limit reached: response was truncated due to length. " + _TRUNCATION_REMINDER))
            return

        for tc in tool_calls:
            if not tc or not getattr(tc, "function", None): continue
            fn_name = tc.function.name or ""
            raw_arguments = tc.function.arguments or ""
            # Contract: Recover truncated tool invocations by repairing unclosed arguments into valid JSON.
            repaired_raw = _repair_json(raw_arguments)
            try: salvaged = json.loads(repaired_raw, strict=False)
            except (json.JSONDecodeError, ValueError): salvaged = {}
            salvaged_args = salvaged if isinstance(salvaged, dict) else {}
            target_file = salvaged_args.get("target_file") or salvaged_args.get("path")
            tool_call_id = tc.id or f"truncated_{turns}"
            failure_diagnostic = ""

            # Contract: Replace partial replace_file_content payload with sentinel raising NotImplementedError with incrementing session truncation identifier.
            if fn_name == "replace_file_content" and target_file and "target_content" in salvaged_args and "replacement_content" in salvaged_args:
                self._truncation_identifier += 1
                sentinel = f'raise NotImplementedError("TRUNCATED_{self._truncation_identifier}_")'
                partial_content = str(salvaged_args["replacement_content"])
                if partial_content.endswith("\n"):
                    # Contract: When last line of partial replacement content is complete, append sentinel on next line matching indentation.
                    lines = partial_content.splitlines()
                    last = lines[-1] if lines else ""
                    indent = len(last) - len(last.lstrip())
                    repaired_content = partial_content + f"{' ' * indent}{sentinel}\n"
                else:
                    # Contract: Delete trailing incomplete line lacking terminating newline and replace with sentinel matching indentation.
                    lines = partial_content.splitlines(keepends=True)
                    if lines:
                        last = lines[-1]
                        indent = len(last) - len(last.lstrip())
                        lines[-1] = f"{' ' * indent}{sentinel}\n"
                        repaired_content = "".join(lines)
                    else:
                        repaired_content = f"{sentinel}\n"
                salvaged_args["replacement_content"] = repaired_content
                salvaged_args["target_file"] = target_file

                tool = _find_tool(tool_mgr, fn_name)
                if tool is not None:
                    # Contract: Execute repaired tool to persist partial modifications.
                    tool_response = tool.execute_tool(_build_actual_bindings(tool, salvaged_args))
                    if not tool_response.is_failed:
                        guard.reset()
                        # Contract: Return actionable notice directing model to resume implementation targeting sentinel.
                        notice = (
                            f"Notice: the generation for '{fn_name}' was truncated at the token limit. "
                            f"The partial modification was persisted to '{target_file}' and the incomplete "
                            f"code was replaced with '{sentinel}'. Resume implementation by calling "
                            f"replace_file_content with target_content '{sentinel}'."
                        )
                        notice_response = _make_tool_response(
                            False,
                            False,
                            notice,
                            reminder=f"Resume implementation by targeting '{sentinel}' with replace_file_content.",
                            suppression_key="replace_file_content",
                        )
                        _call_append_tool_response(history, notice_response, tool_call_id, fn_name, repaired_raw)
                        logger.consume(_log_event("tool_execution", f"[Turn {turns}] Tool {fn_name}: RECOVERED (truncated partial persisted to {target_file})", f"=== Tool Result (turn {turns}) ===\nTool: {fn_name}\nStatus: RECOVERED\nTarget file: {target_file}\nSentinel: {sentinel}\nResult: {_truncate_text(notice)}"))
                        continue
                    failure_diagnostic = f" The repaired partial modification was rejected: {_truncate_text(str(tool_response.content))}"

            # Contract: When truncated invocation is any other tool, terminate by appending tool failure response with tool suppression key.


            failure_response = _make_tool_response(
                True,
                False,
                f"Tool execution for '{fn_name}' was truncated at the generation limit before completion. The tool was not executed.{failure_diagnostic}",
                reminder=_TRUNCATION_REMINDER,
                suppression_key=_truncated_suppression_key(fn_name, salvaged_args),
            )
            _call_append_tool_response(history, failure_response, tool_call_id, fn_name, repaired_raw)
            arguments_log = _format_tool_call(fn_name, repaired_raw)[1]
            summary, transcript = _tool_result_summary(fn_name, arguments_log, failure_response, turns)
            logger.consume(_log_event("tool_execution", summary, transcript))

    # Contract: LoopDriver.run - drives iterative turns until tool termination or conversation limit exhaustion.
    def run(self) -> driver.LoopOutcome:
        openai_cfg = get_singleton(openai_config.OpenAIConfig)
        agent_cfg = get_singleton(agent_config.AgentConfig)
        logger = get_singleton(loop_logger.RunnerLogger)
        history = get_singleton(conversation.Conversation)
        guard_svc = get_singleton(guard.LoopGuard)
        tool_mgr = get_singleton(tool_provider.ToolManager)

        # Contract: Transmits completion requests following OpenAI chat completion conventions.
        client: Any = OpenAI(api_key=openai_cfg.api_key or "none", base_url=openai_cfg.base_url, timeout=float(openai_cfg.timeout)) if OpenAI is not None else None
        limit = agent_cfg.conversation_limit
        self._turn_count = 0
        consecutive_truncations = 0
        last_turn_prompt_tokens: Optional[int] = None
        last_turn_cached_tokens: Optional[int] = None

        while self._turn_count < limit:
            self._turn_count += 1
            turns = self._turn_count
            # Contract: Order tools exposed by the tool manager deterministically by tool name.
            tools_payload = _build_tools_payload(tool_mgr)
            messages_payload = _build_messages_payload(history)
            token_summary, token_transcript = _token_usage_summary(last_turn_prompt_tokens, last_turn_cached_tokens)
            # Contract: Log turn request to the runner logger with compact summary.
            logger.consume(_log_event("model_request", f"[Turn {turns}] Model request: {token_summary}", f"=== Turn {turns} Request ===\nMessages: {len(messages_payload)}\nTools: {len(tools_payload)}\n{token_transcript}"))

            if client is None:  # pragma: no cover (assumption: the openai dependency is installed in the runtime image)
                raise RuntimeError("OpenAI client could not be initialized. Please ensure 'openai' is installed and credentials are configured.")

            try:
                # Contract: Bind model parameters from OpenAI configuration into the transmitted request.
                kw: dict[str, Any] = {"model": openai_cfg.model_name, "messages": messages_payload, "tools": tools_payload or None, "temperature": openai_cfg.temperature, "timeout": float(openai_cfg.timeout)}
                if openai_cfg.max_tokens is not None: kw["max_tokens"] = openai_cfg.max_tokens
                completion = client.chat.completions.create(**kw)

                err_payload = getattr(completion, "error", None)
                if not getattr(completion, "choices", None):
                    is_incomplete, err_msg = False, ""
                    if isinstance(err_payload, dict):
                        code = err_payload.get("code")
                        msg = str(err_payload.get("message", ""))
                        if code == "incomplete_tool_call" or "unrecoverable tool call" in msg.lower():
                            is_incomplete, err_msg = True, msg or str(code)
                    if is_incomplete:
                        consecutive_truncations += 1
                        # Contract: WHEN repeated consecutive truncation failures occur, MUST halt execution with an unexpected failure.
                        if consecutive_truncations > _CONSECUTIVE_TRUNCATION_LIMIT:
                            raise _RepeatedTruncationError(f"Model repeatedly failed with incomplete tool calls: {err_msg}")
                        logger.consume(_log_event("model_completion", f"[Turn {turns}] Truncation error: incomplete tool call (limit exceeded)", f"=== Assistant Response (turn {turns}) ===\nServer error: incomplete tool call (output exceeded max tokens)\n{_truncate_text(err_msg)}"))
                        # Contract: WHEN model completion response fails with incomplete tool call error, append actionable recovery notice and resume with continuation turn.
                        history.append_message(_conv_msg("assistant", _INCOMPLETE_TOOL_CALL_ASSISTANT_NOTE))
                        history.append_message(_conv_msg("user", _INCOMPLETE_TOOL_CALL_RECOVERY))
                        continue
                    raise _NoCompletionChoicesError("Model returned no choices in completion response")
            except _RepeatedTruncationError as truncation_error:
                raise RuntimeError(str(truncation_error)) from truncation_error
            except _NoCompletionChoicesError as no_choices_error:
                raise RuntimeError(str(no_choices_error)) from no_choices_error
            except (OpenAIError, OSError, RuntimeError, ValueError) as e:
                err_str = str(e).lower()
                if isinstance(e, OpenAIError) and ("incomplete_tool_call" in err_str or "unrecoverable tool call" in err_str):
                    consecutive_truncations += 1
                    # Contract: WHEN repeated consecutive truncation failures occur, MUST halt execution with an unexpected failure.
                    if consecutive_truncations > _CONSECUTIVE_TRUNCATION_LIMIT:
                        raise RuntimeError(f"Model repeatedly failed with incomplete tool calls: {e}") from e
                    logger.consume(_log_event("model_completion", f"[Turn {turns}] Truncation error: incomplete tool call (limit exceeded)", f"=== Assistant Response (turn {turns}) ===\nServer error: incomplete tool call (output exceeded max tokens)\n{_truncate_text(str(e))}"))
                    # Contract: WHEN model completion response fails with incomplete tool call error, append actionable recovery notice and resume with continuation turn.
                    history.append_message(_conv_msg("assistant", _INCOMPLETE_TOOL_CALL_ASSISTANT_NOTE))
                    history.append_message(_conv_msg("user", _INCOMPLETE_TOOL_CALL_RECOVERY))
                    continue
                logger.consume(_log_event("model_error", f"[Turn {turns}] Model error: {_truncate_text(str(e))}", f"=== Turn {turns} Model Error ===\n{type(e).__name__}: {_truncate_text(str(e))}"))
                raise RuntimeError(f"Model error: {e}") from e

            consecutive_truncations = 0
            usage = getattr(completion, "usage", None)
            if usage is not None:
                if isinstance(usage, dict):
                    last_turn_prompt_tokens = usage.get("prompt_tokens")
                    last_turn_cached_tokens = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                else:
                    last_turn_prompt_tokens = getattr(usage, "prompt_tokens", None)
                    details = getattr(usage, "prompt_tokens_details", None)
                    last_turn_cached_tokens = getattr(details, "cached_tokens", 0) if details is not None else 0

            choice = completion.choices[0]
            finish_reason = choice.finish_reason
            assistant_msg = choice.message
            tool_calls = assistant_msg.tool_calls or []
            truncated = finish_reason == "length"

            if truncated:
                for tc in tool_calls:
                    tc_func = getattr(tc, "function", None)
                    raw_args = getattr(tc_func, "arguments", "") or "{}" if tc_func else "{}"
                    raw_args = _repair_json(raw_args)
                    if tc_func is not None:
                        try: tc_func.arguments = raw_args
                        except (AttributeError, TypeError): pass
                    history.append_message(_conv_msg("assistant", assistant_msg.content or "", getattr(tc, "id", None), getattr(tc_func, "name", "") if tc_func else "", raw_args))
                if not tool_calls:
                    # A length-truncated generation must still be appended as a model response
                    # so that the continuation turn follows the response it continues.
                    history.append_message(_conv_msg("assistant", assistant_msg.content or ""))
            elif tool_calls:
                for tc in tool_calls:
                    tc_func = getattr(tc, "function", None)
                    history.append_message(_conv_msg("assistant", assistant_msg.content or "", getattr(tc, "id", None), getattr(tc_func, "name", "") if tc_func else "", getattr(tc_func, "arguments", "") or "{}" if tc_func else "{}"))
            else:
                history.append_message(_conv_msg("assistant", assistant_msg.content or ""))

            # Contract: Log compact completion summary and transcript to runner logger without inlining file content.
            call_logs = [
                _format_tool_call(getattr(getattr(tc, "function", None), "name", "") or "", getattr(getattr(tc, "function", None), "arguments", "") or "")
                for tc in tool_calls
            ]
            if tool_calls:
                completion_summary = f"[Turn {turns}] Assistant: {', '.join(log[0] for log in call_logs)}"
                completion_transcript = f"=== Assistant Response (turn {turns}) ===\nFinish: {finish_reason}\nTool calls:\n" + "\n".join(f"  {log[0]}" for log in call_logs)
            else:
                content_preview = _truncate_text(assistant_msg.content or "")
                completion_summary = f"[Turn {turns}] Assistant (text): {json.dumps(content_preview)}"
                completion_transcript = f"=== Assistant Response (turn {turns}) ===\nFinish: {finish_reason}\nContent: {content_preview}"
            logger.consume(_log_event("model_completion", completion_summary, completion_transcript))

            # Contract: WHEN truncated at generation limit, recover and resume generation with continuation turn.
            if truncated:
                self._handle_length_truncation(tool_calls, turns, history, logger, guard_svc, tool_mgr)
                continue

            # Contract: WHEN a model response produces no tool executions, MUST append a prompt reminding that progress requires invoking tools.
            if not tool_calls:
                history.append_message(_conv_msg("user", _MISSING_TOOL_REMINDER))
                logger.consume(_log_event("tool_reminder", f"[Turn {turns}] No tools executed; reminding the model that progress requires tool calls", _MISSING_TOOL_REMINDER))
                continue

            # Contract: Dispatches model-invoked tool calls and records each ToolResponse against its originating call identifier.
            for tc in tool_calls:
                if not tc or not getattr(tc, "function", None): continue
                fn_name = tc.function.name or ""
                fn_args_str = tc.function.arguments or ""
                try: args_dict = json.loads(fn_args_str, strict=False) if fn_args_str else {}
                except (json.JSONDecodeError, ValueError): args_dict = {}
                if not isinstance(args_dict, dict): args_dict = {}
                wire_bindings: Mapping[tool_provider.ParameterName, tool_provider.WireType] = {tool_provider.ParameterName(k): v for k, v in args_dict.items()}
                arguments_log = _format_tool_call(fn_name, fn_args_str)[1]
                tool_call_id = tc.id or ""

                tool = _find_tool(tool_mgr, fn_name)
                # Contract: Tracks consecutive tool invocations through guard.evaluate.
                guard_outcome = guard_svc.evaluate(tool_provider.ToolName(fn_name), _build_actual_bindings(tool, args_dict))
                if isinstance(guard_outcome, guard.LoopFailure):
                    # Contract: WHEN loop guard produces a loop failure, halt execution with an unexpected failure.
                    logger.consume(_log_event("loop_failure", f"[Turn {turns}] Loop failure: {_truncate_text(str(guard_outcome.explanation))}", f"=== Loop Failure (turn {turns}) ===\n{guard_outcome.explanation}"))
                    raise RuntimeError(f"Unexpected loop failure: {guard_outcome.explanation}")

                resp = tool_mgr.execute_tool(tool_provider.ToolName(fn_name), wire_bindings)
                summary, transcript = _tool_result_summary(fn_name, arguments_log, resp, turns)
                logger.consume(_log_event("tool_execution", summary, transcript))
                # Contract: Correlates tool results with model invocations by their tool call identifiers.
                _call_append_tool_response(history, resp, tool_call_id, fn_name, fn_args_str)

                # Contract: WHEN loop guard produces a loop reminder, append the reminder to the conversation.
                if isinstance(guard_outcome, guard.LoopReminder):
                    logger.consume(_log_event("loop_reminder", f"[Turn {turns}] Loop reminder: {_truncate_text(str(guard_outcome.feedback))}", f"=== Loop Reminder (turn {turns}) ===\n{guard_outcome.feedback}"))
                    history.append_message(_conv_msg("user", guard_outcome.feedback))

                # Contract: Clear repetition tracking through loop guard when execution modifies workspace files or advances guide step.
                self._clear_repetition(guard_svc, resp, fn_name)

                current_response = resp
                current_call_id = tool_call_id
                followup_count = 0
                # Contract: WHEN agent configuration directs follow-up injection and response specifies follow-up tool call, execute designated tool.
                while agent_cfg.inject_followups and current_response.follow_up_tool_call is not None and not current_response.is_terminated:
                    followup_count += 1
                    followup = current_response.follow_up_tool_call
                    followup_call_id = f"{current_call_id}_followup_{followup_count}"
                    followup_args = {str(k): v for k, v in followup.wire_parameter_bindings.items()}
                    followup_args_json = json.dumps(followup_args)
                    # Contract: Append synthetic assistant invocation carrying reasoning text as prior thought.
                    history.append_message(_conv_msg("assistant", followup.reasoning_text or "", followup_call_id, followup.tool_name, followup_args_json))
                    followup_response = tool_mgr.execute_tool(followup.tool_name, followup.wire_parameter_bindings)
                    followup_summary, followup_transcript = _tool_result_summary(
                        str(followup.tool_name),
                        _format_tool_call(str(followup.tool_name), followup_args_json)[1],
                        followup_response,
                        turns,
                        is_followup=True,
                    )
                    logger.consume(_log_event("tool_execution", followup_summary, followup_transcript))
                    # Contract: Append follow-up tool response immediately following originating response.
                    _call_append_tool_response(history, followup_response, followup_call_id, str(followup.tool_name), followup_args_json)
                    self._clear_repetition(guard, followup_response, str(followup.tool_name))
                    current_response = followup_response
                    current_call_id = followup_call_id
                    if current_response.is_terminated:
                        # Contract: WHEN tool execution produces a terminating failure response, MUST halt with unexpected failure.
                        if current_response.is_failed:
                            raise RuntimeError(f"Unexpected tool failure: {current_response.content}")
                        # Contract: WHEN tool execution produces successful termination response, return successful loop outcome.
                        return driver.LoopOutcome(response=current_response, conversation=history.get_model_request())

                if resp.is_terminated:
                    # Contract: WHEN tool execution produces a terminating failure response, MUST halt with unexpected failure.
                    if resp.is_failed:
                        raise RuntimeError(f"Unexpected tool failure: {resp.content}")
                    # Contract: WHEN tool execution produces successful termination response, return successful loop outcome.
                    return driver.LoopOutcome(response=resp, conversation=history.get_model_request())

        # Contract: WHEN interaction turns reach conversation limit, halt execution with unexpected failure indicating limit reached.
        raise RuntimeError(f"Unexpected failure: conversation limit reached ({limit} turns)")

    # Contract: Clears repetition tracking when an execution modified workspace files or advanced the guide step.
    def _clear_repetition(self, guard: Any, tool_response: tool_provider.ToolResponse, tool_name: str) -> None:
        """Clears repetition tracking when an execution modified workspace files or advanced the guide step."""
        if tool_response.is_failed:
            return
        if tool_name in _EDITING_TOOL_NAMES or tool_name in _ADVANCING_TOOL_NAMES:
            guard.reset()



# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopDriver,
        keys=[LoopDriver, driver.LoopDriver],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
