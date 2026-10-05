# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: afc7002dbb23
# COVERAGE_AUDIT: 2026-10-05T02:07:35Z
# QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

import json
import time
import traceback
from typing import Any, Mapping, Optional, Set, Tuple
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.loop.lib import loop_conversation
from update_with_ai.parts.loop.lib import loop_guard
from update_with_ai.parts.loop.lib import loop_driver
from . import openai_config
from update_with_ai.parts.core.lib import runner_logger
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)

try:  # pragma: no cover
    import importlib

    _openai: Any = importlib.import_module("openai")
    OpenAI = _openai.OpenAI
    OpenAIError = _openai.OpenAIError
except (ImportError, AttributeError):  # pragma: no cover
    OpenAI: Any = None

    class _OpenAIError(Exception):
        pass

    OpenAIError: Any = _OpenAIError


_DEFAULT_CONVERTER = tool_provider.STRING_PARAMETER_TYPE


def _repair_json(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "{}"  # pragma: no cover (assumption: model response conforms to json syntax)
    try:
        val = json.loads(raw, strict=False)
        if isinstance(val, dict):
            return raw
    except (json.JSONDecodeError, ValueError):
        pass

    start_idx = raw.find("{")
    if start_idx == -1:
        return "{}"
    raw = raw[start_idx:]

    def try_close(cand: str) -> Optional[str]:
        in_string = False
        escape = False
        stack = []
        for ch in cand:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string:
                if ch in "{[":
                    stack.append("}" if ch == "{" else "]")
                elif (
                    ch in "}]"
                ):  # pragma: no cover (assumption: model response conforms to json syntax)
                    if stack and stack[-1] == ch:
                        stack.pop()

        if escape:
            cand = cand[
                :-1
            ]  # pragma: no cover (assumption: model response conforms to json syntax)
        if in_string:
            cand += '"'

        trimmed = cand.rstrip()
        while trimmed and trimmed[-1] == ",":
            trimmed = (
                trimmed[:-1].rstrip()
            )  # pragma: no cover (assumption: model response conforms to json syntax)

        c1 = trimmed
        for close_char in reversed(stack):
            c1 += close_char
        try:
            v = json.loads(c1, strict=False)
            if isinstance(v, dict):
                return c1
        except (json.JSONDecodeError, ValueError):
            pass

        c2 = trimmed + ': ""'
        for close_char in reversed(stack):
            c2 += close_char
        try:
            v = json.loads(c2, strict=False)
            if isinstance(
                v, dict
            ):  # pragma: no cover (assumption: model response conforms to json syntax)
                return c2
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    res = try_close(raw)
    if res is not None:
        return res

    for i in range(len(raw) - 1, -1, -1):
        if raw[i] in (",", "{"):
            res = try_close(raw[: i + (1 if raw[i] == "{" else 0)])
            if res is not None:
                return res

    return "{}"  # pragma: no cover (assumption: model response conforms to json syntax)


def _format_token_usage(
    prompt_tokens: Optional[int], cached_tokens: Optional[int]
) -> Tuple[str, str]:
    if prompt_tokens is None:
        summary = "initial request"
        transcript = "Conversation tokens: initial request"
        return summary, transcript

    size_kb = int(round(prompt_tokens / 1000.0))
    size_str = f"{size_kb}K tokens"
    cache_pct = (
        int(round((cached_tokens / prompt_tokens) * 100.0))
        if (cached_tokens is not None and prompt_tokens > 0)
        else 0  # pragma: no cover (assumption: standard completion response format)
    )
    summary = f"{size_str}, {cache_pct}% cached"
    transcript = f"Conversation tokens: {size_str} ({cache_pct}% cached on last turn)"
    return summary, transcript


def _format_tool_log(
    fn_name: str,
    args_dict: dict[str, Any],
    resp: tool_provider.ToolResponse,
    turns: int,
    is_followup: bool = False,
) -> Tuple[str, str]:
    prefix = f"[Turn {turns}] Follow-up Tool" if is_followup else f"[Turn {turns}] Tool"
    current_time = time.strftime("%H:%M:%S")

    file_path = None
    if isinstance(args_dict, dict):
        file_path = (
            args_dict.get("path")
            or args_dict.get("target_file")
            or args_dict.get("file")
            or args_dict.get("file_alias")
        )
    is_read = fn_name == "view_file"
    is_write = fn_name in ("replace", "update_lines", "replace_file_content")

    if not resp.is_failed and (is_read or is_write) and file_path:
        action = "read" if is_read else "wrote"
        action_title = "Read" if is_read else "Wrote"
        summary = f"{prefix} {fn_name}: {action} {file_path} at {current_time}"
        transcript = f"{action_title} {file_path} at {current_time}"
        if resp.reminder:
            transcript += f"\n\nReminder: {resp.reminder}"
        return summary, transcript

    raw_snippet = (resp.content or "").strip()
    first_line = raw_snippet.splitlines()[0] if raw_snippet else ""
    if len(first_line) > 80:
        first_line = first_line[:77] + "..."

    if resp.is_failed:
        status_str = f"FAILED -> {first_line}"
    elif resp.is_terminated:
        status_str = f"COMPLETED -> {first_line}"
    else:
        status_str = f"OK -> {first_line}"

    summary = f"{prefix} {fn_name}: {status_str}"
    transcript = (
        f"{resp.content}\n\nReminder: {resp.reminder}"
        if resp.reminder
        else (resp.content or "")
    )
    return summary, transcript


def _find_tool(tool_mgr: Any, fn_name: str) -> Any:
    tools = getattr(tool_mgr, "installed_tools", None)
    if tools is None:
        return None
    if isinstance(tools, dict):
        return tools.get(fn_name)
    if hasattr(tools, "get") and callable(tools.get):
        return tools.get(fn_name)
    for t in tools:
        if getattr(t, "name", None) == fn_name:
            return t
    return None


def _call_append_tool_response(
    history: Any,
    tool_response: tool_provider.ToolResponse,
    tool_call_id: str,
    tool_name: str,
    tool_arguments: str,
    wire_parameter_bindings: Optional[
        Mapping[tool_provider.ParameterName, tool_provider.WireType]
    ] = None,
) -> None:
    history.append_tool_response(
        tool_response=tool_response,
        tool_call_id=loop_conversation.ToolCallId(tool_call_id),
        tool_name=tool_provider.ToolName(tool_name),
        tool_arguments=loop_conversation.SerializedArguments(tool_arguments),
    )


def _log_event(
    event_name: str,
    summary: str,
    transcript: str,
) -> runner_logger.RunnerLogEvent:
    return runner_logger.RunnerLogEvent(
        event_name=runner_logger.EventName(event_name),
        summary=runner_logger.EventSummary(summary),
        transcript=runner_logger.EventTranscript(transcript),
    )


def _conv_msg(
    role: str,
    content: str,
    tool_call_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_arguments: Optional[str] = None,
) -> loop_conversation.ConversationMessage:
    return loop_conversation.ConversationMessage(
        role=loop_conversation.MessageRole(role),
        content=loop_conversation.ConversationContent(content),
        tool_call_id=loop_conversation.ToolCallId(tool_call_id)
        if tool_call_id is not None
        else None,
        tool_name=tool_provider.ToolName(tool_name) if tool_name is not None else None,
        tool_arguments=loop_conversation.SerializedArguments(tool_arguments)
        if tool_arguments is not None
        else None,
    )


def _make_tool_response(
    is_failed: bool,
    is_terminated: bool,
    content: str,
    reminder: Optional[str] = None,
    suppression_key: Optional[str] = None,
    follow_up_tool_call: Optional[tool_provider.FollowUpToolCall] = None,
) -> tool_provider.ToolResponse:
    return tool_provider.ToolResponse(
        is_failed=is_failed,
        is_terminated=is_terminated,
        content=tool_provider.ToolResponseContent(content),
        reminder=tool_provider.ToolReminder(reminder) if reminder is not None else None,
        suppression_key=tool_provider.SuppressionKey(suppression_key)
        if suppression_key is not None
        else None,
        follow_up_tool_call=follow_up_tool_call,
    )


def _build_actual_bindings(
    tool: Optional[tool_provider.Tool],
    args_dict: dict[str, Any],
) -> Mapping[
    tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
]:
    res: dict[
        tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
    ] = {}
    if tool is not None:
        tool_params = getattr(tool, "parameters", {})
        for k, v in args_dict.items():
            param = tool_params.get(tool_provider.ParameterName(k))
            if param is not None:
                if getattr(param, "parameter_type", None) is not None:
                    try:
                        conv_val = param.parameter_type.convert(v)
                    except (ValueError, TypeError, KeyError):
                        conv_val = v
                else:  # pragma: no cover (assumption: standard completion response format)
                    conv_val = v
                res[param] = conv_val
    return res


class LoopDriver(loop_driver.LoopDriver, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._truncation_counter: int = 0

    def run(self) -> loop_driver.LoopOutcome:
        openai_cfg = get_singleton(openai_config.OpenAIConfig)
        agent_cfg = get_singleton(agent_config.AgentConfig)
        logger = get_singleton(runner_logger.RunnerLogger)
        history = get_singleton(loop_conversation.Conversation)
        guard = get_singleton(loop_guard.LoopGuard)
        tool_mgr = get_singleton(tool_provider.ToolManager)

        client: Any = None
        if OpenAI is not None:
            client = OpenAI(
                api_key=openai_cfg.api_key if openai_cfg.api_key else "none",
                base_url=openai_cfg.base_url,
                timeout=float(openai_cfg.timeout),
            )

        tools_payload: list[dict[str, Any]] = []
        raw_tools = tool_mgr.installed_tools
        tools_list: list[tuple[str, tool_provider.Tool]] = []
        for t_name, t in raw_tools.items():
            tools_list.append((str(t_name), t))
        for tool_name, t in sorted(tools_list, key=lambda x: x[0]):
            props = {}
            req_props = []
            for p_name, p in t.parameters.items():
                props[p.name] = {"type": "string", "description": str(p.description)}
                if p.is_required:
                    req_props.append(p.name)
            tools_payload.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": {
                            "type": "object",
                            "properties": props,
                            "required": req_props,
                        },
                    },
                }
            )
        if tools_payload:
            tools_payload = json.loads(json.dumps(tools_payload))

        limit = agent_cfg.conversation_limit
        turns = 0
        consecutive_truncations = 0
        last_turn_prompt_tokens: Optional[int] = None
        last_turn_cached_tokens: Optional[int] = None

        while turns < limit:
            turns += 1
            model_req = history.get_model_request()
            messages_payload = []
            for m in model_req.messages:
                if m.role == "assistant" and m.tool_name:
                    messages_payload.append(
                        {
                            "role": "assistant",
                            "content": m.content if m.content else None,
                            "tool_calls": [
                                {
                                    "id": m.tool_call_id or "call_0",
                                    "type": "function",
                                    "function": {
                                        "name": m.tool_name,
                                        "arguments": m.tool_arguments or "{}",
                                    },
                                }
                            ],
                        }
                    )
                elif m.role == "tool":
                    messages_payload.append(
                        {
                            "role": "tool",
                            "content": m.content,
                            "tool_call_id": m.tool_call_id or "",
                        }
                    )
                else:
                    messages_payload.append({"role": m.role, "content": m.content})

            messages_payload = json.loads(json.dumps(messages_payload))

            token_summary, token_transcript = _format_token_usage(
                last_turn_prompt_tokens, last_turn_cached_tokens
            )
            logger.consume(
                _log_event(
                    event_name="model_request",
                    summary=f"[Turn {turns}] {token_summary}",
                    transcript=f"=== Turn {turns} ===\nMessages: {len(messages_payload)}\n{token_transcript}",
                )
            )

            if client is None:  # pragma: no cover
                break

            try:
                create_kwargs: dict[str, Any] = {
                    "model": openai_cfg.model_name,
                    "messages": messages_payload,
                    "tools": tools_payload if tools_payload else None,
                    "temperature": openai_cfg.temperature,
                    "timeout": float(openai_cfg.timeout),
                }
                if openai_cfg.max_tokens is not None:
                    create_kwargs["max_tokens"] = openai_cfg.max_tokens

                completion = client.chat.completions.create(**create_kwargs)
                error_payload = getattr(completion, "error", None)
                if not getattr(completion, "choices", None):
                    is_incomplete = False
                    err_msg = ""
                    if isinstance(error_payload, dict):
                        code = error_payload.get("code")
                        msg = str(error_payload.get("message", ""))
                        if (
                            code == "incomplete_tool_call"
                            or "unrecoverable tool call" in msg.lower()
                        ):
                            is_incomplete = True
                            err_msg = msg or str(code)
                    if is_incomplete:
                        consecutive_truncations += 1
                        if consecutive_truncations > 3:
                            raise RuntimeError(
                                f"Model repeatedly failed with incomplete tool call: {err_msg}"
                            )
                        logger.consume(
                            _log_event(
                                event_name="model_completion",
                                summary=f"[Turn {turns}] Truncation error: incomplete tool call (limit exceeded)",
                                transcript=f"=== Assistant Response (turn {turns}) ===\nServer error: incomplete tool call (output exceeded max tokens)\n{err_msg}",
                            )
                        )
                        history.append_message(
                            _conv_msg(
                                role="assistant",
                                content="I attempted to execute a tool call, but the output exceeded the server's token limit and was rejected by the server.",
                            )
                        )
                        history.append_message(
                            _conv_msg(
                                role="user",
                                content=(
                                    "ERROR: Tool call generation exceeded output token limit (max_tokens). "
                                    "The server rejected the incomplete tool invocation. "
                                    "Do NOT attempt to rewrite or replace an entire large file in a single tool call. "
                                    "Instead, use `replace_file_content` to make smaller, targeted chunk edits on specific line ranges."
                                ),
                            )
                        )
                        continue
                    raise RuntimeError(
                        "Model returned no choices in completion response"
                    )
            except (OpenAIError, OSError, RuntimeError, ValueError) as e:
                err_str = str(e).lower()
                if isinstance(e, OpenAIError) and (
                    "incomplete_tool_call" in err_str
                    or "unrecoverable tool call" in err_str
                ):
                    consecutive_truncations += 1
                    if consecutive_truncations > 3:
                        raise RuntimeError(
                            f"Model repeatedly failed with incomplete tool call: {e}"
                        ) from e
                    logger.consume(
                        _log_event(
                            event_name="model_completion",
                            summary=f"[Turn {turns}] Truncation error: incomplete tool call (limit exceeded)",
                            transcript=f"=== Assistant Response (turn {turns}) ===\nServer error: incomplete tool call (output exceeded max tokens)\n{e}",
                        )
                    )
                    history.append_message(
                        _conv_msg(
                            role="assistant",
                            content="I attempted to execute a tool call, but the output exceeded the server's token limit and was rejected by the server.",
                        )
                    )
                    history.append_message(
                        _conv_msg(
                            role="user",
                            content=(
                                "ERROR: Tool call generation exceeded output token limit (max_tokens). "
                                "The server rejected the incomplete tool invocation. "
                                "Do NOT attempt to rewrite or replace an entire large file in a single tool call. "
                                "Instead, use `replace_file_content` to make smaller, targeted chunk edits on specific line ranges."
                            ),
                        )
                    )
                    continue
                logger.consume(
                    _log_event(
                        event_name="model_error",
                        summary=f"[Turn {turns}] Model error: {e}",
                        transcript=f"=== Turn {turns} Model Error ===\n{traceback.format_exc().strip()}",
                    )
                )
                raise RuntimeError(f"Model error: {e}") from e

            consecutive_truncations = 0

            usage = getattr(completion, "usage", None)
            if usage is not None:
                if isinstance(usage, dict):
                    last_turn_prompt_tokens = usage.get("prompt_tokens")
                    details = usage.get("prompt_tokens_details") or {}
                    last_turn_cached_tokens = details.get("cached_tokens", 0)
                else:
                    last_turn_prompt_tokens = getattr(usage, "prompt_tokens", None)
                    details = getattr(usage, "prompt_tokens_details", None)
                    last_turn_cached_tokens = (
                        getattr(details, "cached_tokens", 0)
                        if details is not None
                        else 0
                    )

            choice = completion.choices[0]
            finish_reason = choice.finish_reason
            assistant_msg = choice.message
            tool_calls = assistant_msg.tool_calls or []

            if tool_calls:
                for tc in tool_calls:
                    tc_func = getattr(tc, "function", None)
                    tc_name = getattr(tc_func, "name", "") if tc_func else ""
                    raw_args = (
                        getattr(tc_func, "arguments", "") or "{}"
                        if tc_func
                        else "{}"  # pragma: no cover (assumption: standard completion response format)
                    )
                    if finish_reason == "length":
                        raw_args = _repair_json(raw_args)
                        if tc_func is not None:
                            try:
                                tc_func.arguments = raw_args
                            except (
                                AttributeError,
                                TypeError,
                            ):  # pragma: no cover (assumption: tool call arguments are valid JSON)
                                pass
                    history.append_message(
                        _conv_msg(
                            role="assistant",
                            content=assistant_msg.content or "",
                            tool_call_id=getattr(tc, "id", None),
                            tool_name=tc_name,
                            tool_arguments=raw_args,
                        )
                    )
            else:
                history.append_message(
                    _conv_msg(
                        role="assistant",
                        content=assistant_msg.content or "",
                    )
                )

            if tool_calls:
                call_strs = []
                for tc in tool_calls:
                    tc_func = getattr(tc, "function", None)
                    tc_name = getattr(tc_func, "name", "") if tc_func else ""
                    tc_raw_args = (
                        getattr(tc_func, "arguments", "") or ""
                        if tc_func
                        else ""  # pragma: no cover (assumption: standard completion response format)
                    )
                    if finish_reason == "length":
                        tc_raw_args = _repair_json(tc_raw_args)
                    try:
                        tc_args = (
                            json.loads(tc_raw_args, strict=False)
                            if tc_raw_args
                            else {}  # pragma: no cover (assumption: standard completion response format)
                        )
                        if isinstance(tc_args, dict):
                            formatted_args = ", ".join(
                                f"{k}={repr(v)}" for k, v in tc_args.items()
                            )
                        else:  # pragma: no cover (assumption: standard completion response format)
                            formatted_args = str(tc_args)
                    except (
                        json.JSONDecodeError,
                        ValueError,
                    ):  # pragma: no cover (assumption: tool call arguments are valid JSON)
                        formatted_args = tc_raw_args
                    if len(formatted_args) > 60:
                        formatted_args = formatted_args[:57] + "..."
                    call_strs.append(f"{tc_name}({formatted_args})")
                completion_summary = f"[Turn {turns}] Assistant: {', '.join(call_strs)}"
            else:
                text_preview = (assistant_msg.content or "").strip().replace("\n", " ")
                if len(text_preview) > 80:
                    text_preview = text_preview[:77] + "..."
                completion_summary = (
                    f"[Turn {turns}] Assistant (text): {json.dumps(text_preview)}"
                )

            logger.consume(
                _log_event(
                    event_name="model_completion",
                    summary=completion_summary,
                    transcript=f"=== Assistant Response (turn {turns}) ===\nFinish: {finish_reason}\nContent: {assistant_msg.content}\nTool calls: {[tc.function.name for tc in tool_calls]}",
                )
            )

            if finish_reason == "length":
                if tool_calls:
                    for tc in tool_calls:
                        if (
                            not tc or not getattr(tc, "function", None)
                        ):  # pragma: no cover (assumption: standard completion response format)
                            continue
                        fn_name = tc.function.name or ""
                        repaired_raw = _repair_json(tc.function.arguments or "")
                        try:
                            salvaged = json.loads(repaired_raw, strict=False)
                        except (
                            json.JSONDecodeError,
                            ValueError,
                        ):  # pragma: no cover (assumption: tool call arguments are valid JSON)
                            salvaged = {}
                        salvaged_args: Optional[dict[str, Any]] = (
                            salvaged if isinstance(salvaged, dict) else None
                        )

                        handled_truncation = False
                        target_file = (
                            salvaged_args.get("target_file")
                            or salvaged_args.get("path")
                            if salvaged_args is not None
                            else None  # pragma: no cover (assumption: standard completion response format)
                        )
                        if (
                            fn_name == "replace_file_content"
                            and salvaged_args is not None
                            and "replacement_content" in salvaged_args
                            and target_file is not None
                            and "target_content" in salvaged_args
                        ):
                            self._truncation_counter += 1
                            sentinel = f'raise NotImplementedError("TRUNCATED_{self._truncation_counter}_")'
                            raw_repl = str(salvaged_args["replacement_content"])
                            if raw_repl.endswith("\n"):
                                non_empty_lines = [
                                    l for l in raw_repl.splitlines() if l.strip()
                                ]
                                last_line = (
                                    non_empty_lines[-1] if non_empty_lines else ""
                                )
                                indent = len(last_line) - len(last_line.lstrip())
                                salvaged_repl = raw_repl + f"{' ' * indent}{sentinel}\n"
                            else:
                                repl_lines = raw_repl.splitlines(keepends=True)
                                if repl_lines:
                                    last_line = repl_lines[-1]
                                    indent = len(last_line) - len(last_line.lstrip())
                                    repl_lines[-1] = f"{' ' * indent}{sentinel}\n"
                                    salvaged_repl = "".join(repl_lines)
                                else:
                                    salvaged_repl = f"{sentinel}\n"

                            salvaged_args["replacement_content"] = salvaged_repl
                            salvaged_args["target_file"] = target_file
                            salvaged_args["path"] = target_file

                            tool = _find_tool(tool_mgr, fn_name)
                            if tool is not None:
                                actual_bindings = _build_actual_bindings(
                                    tool, salvaged_args
                                )
                                tool_resp = tool.execute_tool(actual_bindings)
                                if not tool_resp.is_failed:
                                    guard.reset()
                                    target_path = str(target_file)
                                    notice_content = (
                                        f"Notice: Tool execution for '{fn_name}' was truncated at the generation limit. "
                                        f"Partial content was written to '{target_path}', and incomplete code was replaced with '{sentinel}'. "
                                        f"Use replace_file_content targeting '{sentinel}' to continue implementation."
                                    )
                                    _call_append_tool_response(
                                        history,
                                        tool_response=_make_tool_response(
                                            is_failed=False,
                                            is_terminated=False,
                                            content=notice_content,
                                            reminder=f"Use replace_file_content targeting '{sentinel}' to resume.",
                                            suppression_key="replace_file_content",
                                        ),
                                        tool_call_id=tc.id or f"truncated_{turns}",
                                        tool_name=fn_name,
                                        tool_arguments=repaired_raw,
                                    )
                                    status_sum, t_rep = _format_tool_log(
                                        fn_name,
                                        salvaged_args,
                                        _make_tool_response(
                                            is_failed=False,
                                            is_terminated=False,
                                            content=notice_content,
                                            reminder=f"Use replace_file_content targeting '{sentinel}' to resume.",
                                        ),
                                        turns,
                                    )
                                    logger.consume(
                                        _log_event(
                                            event_name="tool_execution",
                                            summary=status_sum,
                                            transcript=t_rep,
                                        )
                                    )
                                    handled_truncation = True

                        if not handled_truncation:
                            supp_key: Optional[str] = None
                            if fn_name == "replace_file_content":
                                supp_key = "replace_file_content"
                            elif fn_name in (
                                "advance",
                                "submit",
                                "check_file",
                                "run_tests",
                            ):
                                supp_key = fn_name
                            else:
                                if salvaged_args is not None and (
                                    "path" in salvaged_args
                                    or "target_file" in salvaged_args
                                ):
                                    p = str(
                                        salvaged_args.get("path")
                                        or salvaged_args.get("target_file")
                                    )
                                    supp_key = p.split("/")[-1]
                                if supp_key is None:
                                    supp_key = fn_name

                            _call_append_tool_response(
                                history,
                                tool_response=_make_tool_response(
                                    is_failed=True,
                                    is_terminated=False,
                                    content=(
                                        f"Tool execution for '{fn_name}' was truncated at the generation limit before completion. "
                                        "The tool was not executed."
                                    ),
                                    reminder=(
                                        "Whole-file, multi-class, or monolithic replacements that exceed output token limits are prohibited. "
                                        "Make strictly small edits containing at most a single test method or fixture (at most 30–50 lines of code) using replace_file_content."
                                    ),
                                    suppression_key=supp_key,
                                ),
                                tool_call_id=tc.id or f"truncated_{turns}",
                                tool_name=fn_name,
                                tool_arguments=repaired_raw,
                            )
                else:
                    history.append_message(
                        _conv_msg(
                            role="user",
                            content=(
                                "Generation limit reached: response was truncated due to length. "
                                "Whole-file, multi-class, or monolithic replacements that exceed output token limits are prohibited. "
                                "Make strictly small edits containing at most a single test method or fixture (at most 30–50 lines of code) using replace_file_content."
                            ),
                        )
                    )
                continue

            if not tool_calls:
                history.append_message(
                    _conv_msg(
                        role="user",
                        content="No tools were executed. A tool (e.g. view_file, replace, advance, fail, blame) must be called to make progress or conclude the session.",
                    )
                )
                continue

            for tc in tool_calls:
                if not tc or not getattr(
                    tc, "function", None
                ):  # pragma: no cover (assumption: standard completion response format)
                    continue
                fn_name = tc.function.name or ""
                fn_args_str = tc.function.arguments
                try:
                    args_dict = (
                        json.loads(fn_args_str, strict=False)
                        if fn_args_str
                        else {}  # pragma: no cover (assumption: standard completion response format)
                    )
                    if not isinstance(
                        args_dict, dict
                    ):  # pragma: no cover (assumption: standard completion response format)
                        args_dict = {}
                except (
                    json.JSONDecodeError,
                    ValueError,
                ):  # pragma: no cover (assumption: tool call arguments are valid JSON)
                    args_dict = {}

                wire_bindings: Mapping[
                    tool_provider.ParameterName, tool_provider.WireType
                ] = {tool_provider.ParameterName(k): v for k, v in args_dict.items()}

                tool = _find_tool(tool_mgr, fn_name)
                actual_bindings = _build_actual_bindings(tool, args_dict)

                guard_outcome = guard.evaluate(
                    tool_provider.ToolName(fn_name), actual_bindings
                )
                if isinstance(guard_outcome, loop_guard.LoopFailure):
                    logger.consume(
                        _log_event(
                            event_name="loop_failure",
                            summary=f"[Turn {turns}] Loop failure: {guard_outcome.explanation}",
                            transcript=guard_outcome.explanation,
                        )
                    )
                    raise RuntimeError(f"Loop failure: {guard_outcome.explanation}")

                resp = tool_mgr.execute_tool(
                    tool_provider.ToolName(fn_name), wire_bindings
                )

                tool_status_summary, transcript_rep = _format_tool_log(
                    fn_name, args_dict, resp, turns, is_followup=False
                )

                logger.consume(
                    _log_event(
                        event_name="tool_execution",
                        summary=tool_status_summary,
                        transcript=transcript_rep,
                    )
                )

                _call_append_tool_response(
                    history,
                    tool_response=resp,
                    tool_call_id=tc.id or "",
                    tool_name=fn_name,
                    tool_arguments=tc.function.arguments or "",
                    wire_parameter_bindings=wire_bindings,
                )

                if isinstance(guard_outcome, loop_guard.LoopReminder):
                    logger.consume(
                        _log_event(
                            event_name="loop_reminder",
                            summary=f"[Turn {turns}] Loop reminder: {guard_outcome.feedback}",
                            transcript=guard_outcome.feedback,
                        )
                    )
                    history.append_message(
                        _conv_msg(
                            role="user",
                            content=guard_outcome.feedback,
                        )
                    )

                if not resp.is_failed and fn_name in (
                    "replace",
                    "update_lines",
                    "replace_file_content",
                    "advance",
                ):
                    guard.reset()

                curr_resp = resp
                curr_call_id = tc.id or ""
                followup_count = 0
                while (
                    agent_cfg.inject_followups
                    and curr_resp.follow_up_tool_call is not None
                    and not curr_resp.is_terminated
                ):
                    followup = curr_resp.follow_up_tool_call
                    followup_count += 1
                    synth_call_id = f"{curr_call_id}_followup_{followup_count}"
                    args_dict = {
                        str(k): v for k, v in followup.wire_parameter_bindings.items()
                    }
                    history.append_message(
                        _conv_msg(
                            role="assistant",
                            content=followup.reasoning_text or "",
                            tool_call_id=synth_call_id,
                            tool_name=followup.tool_name,
                            tool_arguments=json.dumps(args_dict),
                        )
                    )
                    follow_resp = tool_mgr.execute_tool(
                        followup.tool_name, followup.wire_parameter_bindings
                    )
                    follow_args = {
                        str(k): v for k, v in followup.wire_parameter_bindings.items()
                    }
                    status_sum, t_rep = _format_tool_log(
                        followup.tool_name,
                        follow_args,
                        follow_resp,
                        turns,
                        is_followup=True,
                    )
                    logger.consume(
                        _log_event(
                            event_name="tool_execution",
                            summary=status_sum,
                            transcript=t_rep,
                        )
                    )
                    _call_append_tool_response(
                        history,
                        tool_response=follow_resp,
                        tool_call_id=synth_call_id,
                        tool_name=followup.tool_name,
                        tool_arguments=json.dumps(follow_args),
                        wire_parameter_bindings=followup.wire_parameter_bindings,
                    )
                    if not follow_resp.is_failed and followup.tool_name in (
                        "replace",
                        "update_lines",
                        "replace_file_content",
                        "advance",
                    ):
                        guard.reset()
                    curr_resp = follow_resp
                    if curr_resp.is_terminated:
                        if curr_resp.is_failed:
                            raise RuntimeError(f"Agent failed: {curr_resp.content}")
                        return loop_driver.LoopOutcome(
                            response=curr_resp,
                            conversation=history.get_model_request(),
                        )

                if resp.is_terminated:
                    if resp.is_failed:
                        raise RuntimeError(f"Agent failed: {resp.content}")
                    return loop_driver.LoopOutcome(
                        response=resp,
                        conversation=history.get_model_request(),
                    )

        raise RuntimeError(f"Conversation limit reached ({limit} turns)")


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopDriver,
        keys=[LoopDriver, loop_driver.LoopDriver],
        tier=agent_session,
    )
