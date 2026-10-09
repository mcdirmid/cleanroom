# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-06T12:00:00Z
# CHANGE: refactor openai_driver_impl under 500 lines
# CODE_HASH: 7bb8e4617cdf
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

import json
import time
import traceback
from typing import Any, Mapping, Optional, Sequence, Tuple
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.loop.lib import loop_conversation, loop_guard, loop_driver
from . import openai_config
from update_with_ai.parts.core.lib import runner_logger
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

try:  # pragma: no cover
    import importlib
    _openai: Any = importlib.import_module("openai")
    OpenAI, OpenAIError = _openai.OpenAI, _openai.OpenAIError
except (ImportError, AttributeError):  # pragma: no cover
    OpenAI = None
    class _OpenAIError(Exception): pass
    OpenAIError: Any = _OpenAIError


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


def _format_token_usage(prompt_tokens: Optional[int], cached_tokens: Optional[int]) -> Tuple[str, str]:
    if prompt_tokens is None: return "initial request", "Conversation tokens: initial request"
    size_str = f"{int(round(prompt_tokens / 1000.0))}K tokens"
    pct = int(round((cached_tokens / prompt_tokens) * 100.0)) if cached_tokens and prompt_tokens > 0 else 0
    return f"{size_str}, {pct}% cached", f"Conversation tokens: {size_str} ({pct}% cached on last turn)"


def _format_tool_log(fn_name: str, args_dict: dict[str, Any], resp: tool_provider.ToolResponse, turns: int, is_followup: bool = False) -> Tuple[str, str]:
    prefix = f"[Turn {turns}] Follow-up Tool" if is_followup else f"[Turn {turns}] Tool"
    current_time = time.strftime("%H:%M:%S")
    file_path = args_dict.get("path") or args_dict.get("target_file") or args_dict.get("file") or args_dict.get("file_alias") if isinstance(args_dict, dict) else None
    is_read = fn_name == "view_file"
    is_write = fn_name in ("replace", "update_lines", "replace_file_content")
    if not resp.is_failed and (is_read or is_write) and file_path:
        action = "read" if is_read else "wrote"
        transcript = f"{'Read' if is_read else 'Wrote'} {file_path} at {current_time}"
        if resp.reminder: transcript += f"\n\nReminder: {resp.reminder}"
        return f"{prefix} {fn_name}: {action} {file_path} at {current_time}", transcript

    snippet = (resp.content or "").strip().splitlines()[0] if resp.content else ""
    if len(snippet) > 80: snippet = snippet[:77] + "..."
    status = f"FAILED -> {snippet}" if resp.is_failed else (f"COMPLETED -> {snippet}" if resp.is_terminated else f"OK -> {snippet}")
    transcript = f"{resp.content}\n\nReminder: {resp.reminder}" if resp.reminder else (resp.content or "")
    return f"{prefix} {fn_name}: {status}", transcript


def _find_tool(tool_mgr: Any, fn_name: str) -> Any:
    tools = getattr(tool_mgr, "installed_tools", {})
    if isinstance(tools, dict): return tools.get(fn_name)
    if hasattr(tools, "get") and callable(tools.get): return tools.get(fn_name)
    return next((t for t in tools if getattr(t, "name", None) == fn_name), None)


def _call_append_tool_response(history: Any, tool_response: tool_provider.ToolResponse, tool_call_id: str, tool_name: str, tool_arguments: str, wire_parameter_bindings: Optional[Mapping[tool_provider.ParameterName, tool_provider.WireType]] = None) -> None:
    history.append_tool_response(
        tool_response=tool_response,
        tool_call_id=loop_conversation.ToolCallId(tool_call_id),
        tool_name=tool_provider.ToolName(tool_name),
        tool_arguments=loop_conversation.SerializedArguments(tool_arguments),
    )


def _log_event(event_name: str, summary: str, transcript: str) -> runner_logger.RunnerLogEvent:
    return runner_logger.RunnerLogEvent(
        event_name=runner_logger.EventName(event_name),
        summary=runner_logger.EventSummary(summary),
        transcript=runner_logger.EventTranscript(transcript),
    )


def _conv_msg(role: str, content: str, tool_call_id: Optional[str] = None, tool_name: Optional[str] = None, tool_arguments: Optional[str] = None) -> loop_conversation.ConversationMessage:
    return loop_conversation.ConversationMessage(
        role=loop_conversation.MessageRole(role),
        content=loop_conversation.ConversationContent(content),
        tool_call_id=loop_conversation.ToolCallId(tool_call_id) if tool_call_id is not None else None,
        tool_name=tool_provider.ToolName(tool_name) if tool_name is not None else None,
        tool_arguments=loop_conversation.SerializedArguments(tool_arguments) if tool_arguments is not None else None,
    )


def _make_tool_response(is_failed: bool, is_terminated: bool, content: str, reminder: Optional[str] = None, suppression_key: Optional[str] = None) -> tool_provider.ToolResponse:
    return tool_provider.ToolResponse(
        is_failed=is_failed,
        is_terminated=is_terminated,
        content=tool_provider.ToolResponseContent(content),
        reminder=tool_provider.ToolReminder(reminder) if reminder is not None else None,
        suppression_key=tool_provider.SuppressionKey(suppression_key) if suppression_key is not None else None,
    )


def _build_actual_bindings(tool: Optional[tool_provider.Tool], args_dict: dict[str, Any]) -> Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]:
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


def _build_tools_payload(tool_mgr: Any) -> list[dict[str, Any]]:
    raw_tools = tool_mgr.installed_tools
    sorted_tools = sorted([(str(k), v) for k, v in raw_tools.items()], key=lambda x: x[0])
    payload = []
    for _, t in sorted_tools:
        props = {p.name: {"type": "string", "description": str(p.description)} for p in t.parameters.values()}
        reqs = [p.name for p in t.parameters.values() if p.is_required]
        payload.append({
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": {"type": "object", "properties": props, "required": reqs}},
        })
    return json.loads(json.dumps(payload)) if payload else []


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
    return json.loads(json.dumps(payload))


class LoopDriver(loop_driver.LoopDriver, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._truncation_counter: int = 0

    def _handle_length_truncation(self, tool_calls: Sequence[Any], turns: int, history: Any, logger: Any, guard: Any, tool_mgr: Any) -> None:
        if not tool_calls:
            history.append_message(_conv_msg("user", "Generation limit reached: response was truncated due to length. Whole-file, multi-class, or monolithic replacements that exceed output token limits are prohibited. Make strictly small edits containing at most a single test method or fixture (at most 30–50 lines of code) using replace_file_content."))
            return

        for tc in tool_calls:
            if not tc or not getattr(tc, "function", None): continue
            fn_name = tc.function.name or ""
            repaired_raw = _repair_json(tc.function.arguments or "")
            try: salvaged = json.loads(repaired_raw, strict=False)
            except (json.JSONDecodeError, ValueError): salvaged = {}
            salvaged_args = salvaged if isinstance(salvaged, dict) else None

            target_file = salvaged_args.get("target_file") or salvaged_args.get("path") if salvaged_args else None
            if fn_name == "replace_file_content" and salvaged_args and "replacement_content" in salvaged_args and target_file and "target_content" in salvaged_args:
                self._truncation_counter += 1
                sentinel = f'raise NotImplementedError("TRUNCATED_{self._truncation_counter}_")'
                raw_repl = str(salvaged_args["replacement_content"])
                if raw_repl.endswith("\n"):
                    lines = [l for l in raw_repl.splitlines() if l.strip()]
                    last = lines[-1] if lines else ""
                    indent = len(last) - len(last.lstrip())
                    salvaged_repl = raw_repl + f"{' ' * indent}{sentinel}\n"
                else:
                    lines = raw_repl.splitlines(keepends=True)
                    if lines:
                        last = lines[-1]; indent = len(last) - len(last.lstrip())
                        lines[-1] = f"{' ' * indent}{sentinel}\n"
                        salvaged_repl = "".join(lines)
                    else:
                        salvaged_repl = f"{sentinel}\n"

                salvaged_args["replacement_content"] = salvaged_repl
                salvaged_args["target_file"] = salvaged_args["path"] = target_file
                tool = _find_tool(tool_mgr, fn_name)
                if tool is not None:
                    tool_resp = tool.execute_tool(_build_actual_bindings(tool, salvaged_args))
                    if not tool_resp.is_failed:
                        guard.reset()
                        notice = f"Notice: Tool execution for '{fn_name}' was truncated at the generation limit. Partial content was written to '{target_file}', and incomplete code was replaced with '{sentinel}'. Use replace_file_content targeting '{sentinel}' to continue implementation."
                        _call_append_tool_response(history, _make_tool_response(False, False, notice, reminder=f"Use replace_file_content targeting '{sentinel}' to resume.", suppression_key="replace_file_content"), tc.id or f"truncated_{turns}", fn_name, repaired_raw)
                        s_sum, t_rep = _format_tool_log(fn_name, salvaged_args, _make_tool_response(False, False, notice, reminder=f"Use replace_file_content targeting '{sentinel}' to resume."), turns)
                        logger.consume(_log_event("tool_execution", s_sum, t_rep))
                        continue

            if fn_name == "replace_file_content" or fn_name in ("advance", "submit", "check_file", "run_tests"):
                supp_key = fn_name
            elif salvaged_args and ("path" in salvaged_args or "target_file" in salvaged_args):
                supp_key = str(salvaged_args.get("path") or salvaged_args.get("target_file")).split("/")[-1]
            else:
                supp_key = fn_name
            _call_append_tool_response(history, _make_tool_response(True, False, f"Tool execution for '{fn_name}' was truncated at the generation limit before completion. The tool was not executed.", reminder="Whole-file, multi-class, or monolithic replacements that exceed output token limits are prohibited. Make strictly small edits containing at most a single test method or fixture (at most 30–50 lines of code) using replace_file_content.", suppression_key=supp_key), tc.id or f"truncated_{turns}", fn_name, repaired_raw)

    def run(self) -> loop_driver.LoopOutcome:
        openai_cfg = get_singleton(openai_config.OpenAIConfig)
        agent_cfg = get_singleton(agent_config.AgentConfig)
        logger = get_singleton(runner_logger.RunnerLogger)
        history = get_singleton(loop_conversation.Conversation)
        guard = get_singleton(loop_guard.LoopGuard)
        tool_mgr = get_singleton(tool_provider.ToolManager)

        client: Any = OpenAI(api_key=openai_cfg.api_key or "none", base_url=openai_cfg.base_url, timeout=float(openai_cfg.timeout)) if OpenAI is not None else None
        tools_payload = _build_tools_payload(tool_mgr)

        limit, turns, consecutive_truncations = agent_cfg.conversation_limit, 0, 0
        last_turn_prompt_tokens, last_turn_cached_tokens = None, None

        while turns < limit:
            turns += 1
            messages_payload = _build_messages_payload(history)
            tok_sum, tok_trans = _format_token_usage(last_turn_prompt_tokens, last_turn_cached_tokens)
            logger.consume(_log_event("model_request", f"[Turn {turns}] {tok_sum}", f"=== Turn {turns} ===\nMessages: {len(messages_payload)}\n{tok_trans}"))

            if client is None:  # pragma: no cover
                raise RuntimeError("OpenAI client could not be initialized. Please ensure 'openai' is installed and credentials are configured.")

            try:
                kw: dict[str, Any] = {"model": openai_cfg.model_name, "messages": messages_payload, "tools": tools_payload or None, "temperature": openai_cfg.temperature, "timeout": float(openai_cfg.timeout)}
                if openai_cfg.max_tokens is not None: kw["max_tokens"] = openai_cfg.max_tokens
                completion = client.chat.completions.create(**kw)

                err_payload = getattr(completion, "error", None)
                if not getattr(completion, "choices", None):
                    is_inc, err_msg = False, ""
                    if isinstance(err_payload, dict):
                        code = err_payload.get("code")
                        msg = str(err_payload.get("message", ""))
                        if code == "incomplete_tool_call" or "unrecoverable tool call" in msg.lower():
                            is_inc, err_msg = True, msg or str(code)
                    if is_inc:
                        consecutive_truncations += 1
                        if consecutive_truncations > 3: raise RuntimeError(f"Model repeatedly failed with incomplete tool call: {err_msg}")
                        logger.consume(_log_event("model_completion", f"[Turn {turns}] Truncation error: incomplete tool call (limit exceeded)", f"=== Assistant Response (turn {turns}) ===\nServer error: incomplete tool call (output exceeded max tokens)\n{err_msg}"))
                        history.append_message(_conv_msg("assistant", "I attempted to execute a tool call, but the output exceeded the server's token limit and was rejected by the server."))
                        history.append_message(_conv_msg("user", "ERROR: Tool call generation exceeded output token limit (max_tokens). The server rejected the incomplete tool invocation. Do NOT attempt to rewrite or replace an entire large file in a single tool call. Instead, use `replace_file_content` to make smaller, targeted chunk edits on specific line ranges."))
                        continue
                    raise RuntimeError("Model returned no choices in completion response")
            except (OpenAIError, OSError, RuntimeError, ValueError) as e:
                err_str = str(e).lower()
                if isinstance(e, OpenAIError) and ("incomplete_tool_call" in err_str or "unrecoverable tool call" in err_str):
                    consecutive_truncations += 1
                    if consecutive_truncations > 3: raise RuntimeError(f"Model repeatedly failed with incomplete tool call: {e}") from e
                    logger.consume(_log_event("model_completion", f"[Turn {turns}] Truncation error: incomplete tool call (limit exceeded)", f"=== Assistant Response (turn {turns}) ===\nServer error: incomplete tool call (output exceeded max tokens)\n{e}"))
                    history.append_message(_conv_msg("assistant", "I attempted to execute a tool call, but the output exceeded the server's token limit and was rejected by the server."))
                    history.append_message(_conv_msg("user", "ERROR: Tool call generation exceeded output token limit (max_tokens). The server rejected the incomplete tool invocation. Do NOT attempt to rewrite or replace an entire large file in a single tool call. Instead, use `replace_file_content` to make smaller, targeted chunk edits on specific line ranges."))
                    continue
                logger.consume(_log_event("model_error", f"[Turn {turns}] Model error: {e}", f"=== Turn {turns} Model Error ===\n{traceback.format_exc().strip()}"))
                raise RuntimeError(f"Model error: {e}") from e

            consecutive_truncations = 0
            usage = getattr(completion, "usage", None)
            if usage is not None:
                if isinstance(usage, dict):
                    last_turn_prompt_tokens = usage.get("prompt_tokens")
                    last_turn_cached_tokens = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                else:
                    last_turn_prompt_tokens = getattr(usage, "prompt_tokens", None)
                    det = getattr(usage, "prompt_tokens_details", None)
                    last_turn_cached_tokens = getattr(det, "cached_tokens", 0) if det is not None else 0

            choice = completion.choices[0]
            finish_reason = choice.finish_reason
            assistant_msg = choice.message
            tool_calls = assistant_msg.tool_calls or []

            if tool_calls:
                for tc in tool_calls:
                    tc_func = getattr(tc, "function", None)
                    raw_args = getattr(tc_func, "arguments", "") or "{}" if tc_func else "{}"
                    if finish_reason == "length":
                        raw_args = _repair_json(raw_args)
                        if tc_func is not None:
                            try: tc_func.arguments = raw_args
                            except (AttributeError, TypeError): pass
                    history.append_message(_conv_msg("assistant", assistant_msg.content or "", getattr(tc, "id", None), getattr(tc_func, "name", "") if tc_func else "", raw_args))
                call_strs = []
                for tc in tool_calls:
                    fn = getattr(tc.function, "name", "")
                    r_args = getattr(tc.function, "arguments", "")
                    if finish_reason == "length": r_args = _repair_json(r_args)
                    try:
                        d = json.loads(r_args, strict=False) if r_args else {}
                        f_args = ", ".join(f"{k}={repr(v)}" for k, v in d.items()) if isinstance(d, dict) else str(d)
                    except (json.JSONDecodeError, ValueError): f_args = r_args
                    call_strs.append(f"{fn}({f_args[:57] + '...' if len(f_args) > 60 else f_args})")
                comp_summary = f"[Turn {turns}] Assistant: {', '.join(call_strs)}"
            else:
                history.append_message(_conv_msg("assistant", assistant_msg.content or ""))
                preview = (assistant_msg.content or "").strip().replace("\n", " ")
                comp_summary = f"[Turn {turns}] Assistant (text): {json.dumps(preview[:77] + '...' if len(preview) > 80 else preview)}"

            logger.consume(_log_event("model_completion", comp_summary, f"=== Assistant Response (turn {turns}) ===\nFinish: {finish_reason}\nContent: {assistant_msg.content}\nTool calls: {[tc.function.name for tc in tool_calls]}"))

            if finish_reason == "length":
                self._handle_length_truncation(tool_calls, turns, history, logger, guard, tool_mgr)
                continue

            if not tool_calls:
                history.append_message(_conv_msg("user", "No tools were executed. A tool (e.g. view_file, replace, advance, fail, blame) must be called to make progress or conclude the session."))
                continue

            for tc in tool_calls:
                if not tc or not getattr(tc, "function", None): continue
                fn_name, fn_args_str = tc.function.name or "", tc.function.arguments
                try: args_dict = json.loads(fn_args_str, strict=False) if fn_args_str else {}
                except (json.JSONDecodeError, ValueError): args_dict = {}
                if not isinstance(args_dict, dict): args_dict = {}
                wire_bindings: Mapping[tool_provider.ParameterName, tool_provider.WireType] = {tool_provider.ParameterName(k): v for k, v in args_dict.items()}

                tool = _find_tool(tool_mgr, fn_name)
                guard_outcome = guard.evaluate(tool_provider.ToolName(fn_name), _build_actual_bindings(tool, args_dict))
                if isinstance(guard_outcome, loop_guard.LoopFailure):
                    logger.consume(_log_event("loop_failure", f"[Turn {turns}] Loop failure: {guard_outcome.explanation}", guard_outcome.explanation))
                    raise RuntimeError(f"Loop failure: {guard_outcome.explanation}")

                resp = tool_mgr.execute_tool(tool_provider.ToolName(fn_name), wire_bindings)
                status_sum, t_rep = _format_tool_log(fn_name, args_dict, resp, turns)
                logger.consume(_log_event("tool_execution", status_sum, t_rep))
                _call_append_tool_response(history, resp, tc.id or "", fn_name, tc.function.arguments or "", wire_bindings)

                if isinstance(guard_outcome, loop_guard.LoopReminder):
                    logger.consume(_log_event("loop_reminder", f"[Turn {turns}] Loop reminder: {guard_outcome.feedback}", guard_outcome.feedback))
                    history.append_message(_conv_msg("user", guard_outcome.feedback))

                if not resp.is_failed and fn_name in ("replace", "update_lines", "replace_file_content", "advance"):
                    guard.reset()

                curr_resp, curr_id, f_count = resp, tc.id or "", 0
                while agent_cfg.inject_followups and curr_resp.follow_up_tool_call and not curr_resp.is_terminated:
                    followup = curr_resp.follow_up_tool_call
                    f_count += 1
                    s_id = f"{curr_id}_followup_{f_count}"
                    f_args = {str(k): v for k, v in followup.wire_parameter_bindings.items()}
                    history.append_message(_conv_msg("assistant", followup.reasoning_text or "", s_id, followup.tool_name, json.dumps(f_args)))
                    f_resp = tool_mgr.execute_tool(followup.tool_name, followup.wire_parameter_bindings)
                    f_sum, f_rep = _format_tool_log(followup.tool_name, f_args, f_resp, turns, is_followup=True)
                    logger.consume(_log_event("tool_execution", f_sum, f_rep))
                    _call_append_tool_response(history, f_resp, s_id, followup.tool_name, json.dumps(f_args), followup.wire_parameter_bindings)
                    if not f_resp.is_failed and followup.tool_name in ("replace", "update_lines", "replace_file_content", "advance"):
                        guard.reset()
                    curr_resp = f_resp
                    if curr_resp.is_terminated:
                        if curr_resp.is_failed: raise RuntimeError(f"Agent failed: {curr_resp.content}")
                        return loop_driver.LoopOutcome(response=curr_resp, conversation=history.get_model_request())

                if resp.is_terminated:
                    if resp.is_failed: raise RuntimeError(f"Agent failed: {resp.content}")
                    return loop_driver.LoopOutcome(response=resp, conversation=history.get_model_request())

        raise RuntimeError(f"Conversation limit reached ({limit} turns)")


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(LoopDriver, keys=[LoopDriver, loop_driver.LoopDriver], tier=agent_session)
