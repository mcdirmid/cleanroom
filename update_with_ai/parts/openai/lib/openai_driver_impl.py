import json
import time
from typing import Any, Optional, Set, Tuple
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
    import openai

    OpenAI = openai.OpenAI
    OpenAIError = openai.OpenAIError
except ImportError:  # pragma: no cover
    OpenAI: Any = None

    class _OpenAIError(Exception):
        pass

    OpenAIError: Any = _OpenAIError


_DEFAULT_CONVERTER = tool_provider.STRING_PARAMETER_TYPE


def _repair_json(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "{}"
    try:
        json.loads(raw)
        return raw
    except Exception:
        pass

    in_string = False
    escape = False
    stack = []
    for ch in raw:
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
            elif ch in "}]":
                if stack and stack[-1] == ch:
                    stack.pop()

    candidate = raw
    if escape:
        candidate = candidate[:-1]
    if in_string:
        candidate += '"'

    trimmed = candidate.rstrip()
    while trimmed and trimmed[-1] in (",", ":"):
        trimmed = trimmed[:-1].rstrip()
    candidate = trimmed

    for close_char in reversed(stack):
        candidate += close_char

    try:
        json.loads(candidate)
        return candidate
    except Exception:
        return "{}"


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
        else 0
    )
    summary = f"{size_str}, {cache_pct}% cached"
    transcript = f"Conversation tokens: {size_str} ({cache_pct}% cached on last turn)"
    return summary, transcript


def _format_tool_log(
    fn_name: str,
    args_dict: dict[str, Any],
    resp: tool_provider.Response,
    turns: int,
    is_followup: bool = False,
) -> Tuple[str, str]:
    prefix = f"[Turn {turns}] Follow-up Tool" if is_followup else f"[Turn {turns}] Tool"
    current_time = time.strftime("%H:%M:%S")

    file_path = (
        args_dict.get("path")
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


class LoopDriver(loop_driver.LoopDriver, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    def run(self) -> loop_driver.AgentOutcome:
        openai_cfg = get_singleton(openai_config.OpenaiConfig)
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

        # Requirement: When driving a turn, the loop driver transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from openai config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter sequence, and correlates tool results with model invocations according to OpenAI tool calling conventions.
        tools_payload: list[dict[str, Any]] = []
        for t in sorted(tool_mgr.installed_tools, key=lambda x: x.name):
            props = {}
            req_props = []
            for p in t.parameters:
                props[p.name] = {"type": "string", "description": p.description}
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
        last_response: tool_provider.Response = tool_provider.Response(
            is_failed=False, is_terminated=False, content="Initialized"
        )
        last_turn_prompt_tokens: Optional[int] = None
        last_turn_cached_tokens: Optional[int] = None

        # Requirement: [AgentDriver] The agent driver drives turns by sending model requests to a language model and executing requested tools.
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
            # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
            logger.consume(
                runner_logger.LogEvent(
                    event_name="model_request",
                    summary=f"[Turn {turns}] {token_summary}",
                    transcript_representation=f"=== Turn {turns} ===\nMessages: {len(messages_payload)}\n{token_transcript}",
                )
            )

            if client is None:  # pragma: no cover
                # Fallback for environments without live OpenAI network / mock
                break

            try:
                # Requirement: When driving a turn, the loop driver transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from openai config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter sequence, and correlates tool results with model invocations according to OpenAI tool calling conventions.
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
            except OpenAIError as e:
                logger.consume(
                    runner_logger.LogEvent(
                        event_name="model_error",
                        summary=f"[Turn {turns}] Model error: {e}",
                        transcript_representation=str(e),
                    )
                )
                raise RuntimeError(f"Model error: {e}")

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

            # Requirement: [AgentDriver] The agent driver appends model responses and correlates tool responses with tool call identifiers in the conversation.
            if tool_calls:
                for tc in tool_calls:
                    raw_args = tc.function.arguments or "{}"
                    if finish_reason == "length":
                        raw_args = _repair_json(raw_args)
                    history.append_message(
                        loop_conversation.Message(
                            role="assistant",
                            content=assistant_msg.content or "",
                            tool_call_id=tc.id,
                            tool_name=tc.function.name,
                            tool_arguments=raw_args,
                        )
                    )
            else:
                history.append_message(
                    loop_conversation.Message(
                        role="assistant",
                        content=assistant_msg.content or "",
                    )
                )

            if tool_calls:
                call_strs = []
                for tc in tool_calls:
                    tc_name = tc.function.name
                    tc_raw_args = tc.function.arguments or ""
                    try:
                        tc_args = json.loads(tc_raw_args) if tc_raw_args else {}
                        formatted_args = ", ".join(
                            f"{k}={repr(v)}" for k, v in tc_args.items()
                        )
                    except (json.JSONDecodeError, TypeError):
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

            # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
            logger.consume(
                runner_logger.LogEvent(
                    event_name="model_completion",
                    summary=completion_summary,
                    transcript_representation=f"=== Assistant Response (turn {turns}) ===\nFinish: {finish_reason}\nContent: {assistant_msg.content}\nTool calls: {[tc.function.name for tc in tool_calls]}",
                )
            )

            # Requirement: When a model response is truncated at the generation limit, the loop driver terminates any truncated tool invocation by repairing unclosed arguments into valid JSON and appending a tool failure response with the tool's suppression key, and resumes generation with a continuation turn.
            if finish_reason == "length":
                if tool_calls:
                    for tc in tool_calls:
                        fn_name = tc.function.name
                        supp_key: Optional[str] = None
                        if fn_name == "replace_file_content":
                            supp_key = "replace_file_content"
                        elif fn_name in ("advance", "submit", "check_file", "run_tests"):
                            supp_key = fn_name
                        else:
                            repaired_raw = _repair_json(tc.function.arguments or "")
                            try:
                                parsed = json.loads(repaired_raw)
                                if isinstance(parsed, dict) and "path" in parsed:
                                    supp_key = str(parsed["path"]).split("/")[-1]
                            except Exception:
                                pass
                            if supp_key is None:
                                supp_key = fn_name

                        history.append_tool_response(
                            response=tool_provider.Response(
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
                            tool_name=fn_name,
                            tool_call_id=tc.id or f"truncated_{turns}",
                        )
                else:
                    history.append_message(
                        loop_conversation.Message(
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
                # Requirement: When a model response produces no tool executions, the agent driver appends a prompt to the conversation reminding that progress and conclusion require invoking tools, and continues the turn loop.
                history.append_message(
                    loop_conversation.Message(
                        role="user",
                        content="No tools were executed. A tool (e.g. view_file, replace, advance, fail, blame) must be called to make progress or conclude the session.",
                    )
                )
                continue

            # Requirement: [AgentDriver] The agent driver drives turns by sending model requests to a language model and executing requested tools.
            for tc in tool_calls:
                fn_name = tc.function.name
                fn_args_str = tc.function.arguments
                args_dict = json.loads(fn_args_str) if fn_args_str else {}

                wire_bindings = {(k, v) for k, v in args_dict.items()}

                tools_by_name = {t.name: t for t in tool_mgr.installed_tools}
                tool = tools_by_name.get(fn_name)
                actual_bindings_set: Set[Tuple[tool_provider.Parameter, Any]] = set()
                if tool is not None:
                    params_by_name = {p.name: p for p in tool.parameters}
                    for k, v in args_dict.items():
                        if k in params_by_name:
                            p = params_by_name[k]
                            if p.parameter_converter is not None:
                                try:
                                    conv_val = p.parameter_converter.convert(v)
                                except (ValueError, TypeError, KeyError):
                                    conv_val = v
                            else:
                                conv_val = v  # pragma: no cover (assumption: parameter_converter is non-null under tool_provider.Parameter grounding contract)
                            actual_bindings_set.add((p, conv_val))
                        else:
                            dummy_p = tool_provider.Parameter(
                                name=k,
                                description="",
                                parameter_converter=_DEFAULT_CONVERTER,
                            )
                            actual_bindings_set.add((dummy_p, v))
                else:
                    for k, v in args_dict.items():
                        dummy_p = tool_provider.Parameter(
                            name=k,
                            description="",
                            parameter_converter=_DEFAULT_CONVERTER,
                        )
                        actual_bindings_set.add((dummy_p, v))

                actual_bindings = tool_provider.ActualParameterBindings(
                    bindings=actual_bindings_set
                )

                # Requirement: Before executing each tool call, the agent driver records the tool execution in the loop guard, injecting a loop reminder into the conversation when a reminder is produced, or concluding the run with an unexpected failure when a loop failure is produced.
                # Requirement: [AgentDriver] The agent driver evaluates tool executions with the loop guard, injecting reminders or halting with an unexpected failure on runaway repetition.
                guard_outcome = guard.record_tool_execution(fn_name, actual_bindings)
                if isinstance(guard_outcome, loop_guard.LoopFailure):
                    logger.consume(
                        runner_logger.LogEvent(
                            event_name="loop_failure",
                            summary=f"[Turn {turns}] Loop failure: {guard_outcome.explanation}",
                            transcript_representation=guard_outcome.explanation,
                        )
                    )
                    raise RuntimeError(f"Loop failure: {guard_outcome.explanation}")

                resp = tool_mgr.execute_tool(
                    fn_name, tool_provider.WireParameterBindings(bindings=wire_bindings)
                )
                last_response = resp

                tool_status_summary, transcript_rep = _format_tool_log(
                    fn_name, args_dict, resp, turns, is_followup=False
                )

                # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
                logger.consume(
                    runner_logger.LogEvent(
                        event_name="tool_execution",
                        summary=tool_status_summary,
                        transcript_representation=transcript_rep,
                    )
                )

                # Requirement: [AgentDriver] The agent driver appends model responses and correlates tool responses with tool call identifiers in the conversation.
                history.append_tool_response(
                    response=resp,
                    tool_name=fn_name,
                    tool_call_id=tc.id,
                )

                if isinstance(guard_outcome, loop_guard.LoopReminder):
                    logger.consume(
                        runner_logger.LogEvent(
                            event_name="loop_reminder",
                            summary=f"[Turn {turns}] Loop reminder: {guard_outcome.feedback}",
                            transcript_representation=guard_outcome.feedback,
                        )
                    )
                    history.append_message(
                        loop_conversation.Message(
                            role="user",
                            content=guard_outcome.feedback,
                        )
                    )

                # Requirement: Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard.
                if not resp.is_failed and fn_name in (
                    "replace",
                    "update_lines",
                    "replace_file_content",
                    "advance",
                ):
                    guard.record_progress()

                # Requirement: When configured by agent configuration to inject followups, a tool response specifying a follow-up tool call prompts execution of the designated tool, appending a synthetic assistant invocation carrying the follow-up tool call's reasoning text as prior thought preceding the requested tool execution and the resulting follow-up response to the conversation immediately following the originating response.
                # Requirement: [AgentDriver] The agent driver can dispatch follow-up tool calls specified by tool responses, recording the follow-up execution in the conversation.
                curr_resp = resp
                curr_call_id = tc.id
                followup_count = 0
                while (
                    agent_cfg.inject_followups
                    and curr_resp.follow_up_tool_call is not None
                    and not curr_resp.is_terminated
                ):
                    followup = curr_resp.follow_up_tool_call
                    followup_count += 1
                    synth_call_id = f"{curr_call_id}_followup_{followup_count}"
                    args_dict = dict(followup.wire_parameter_bindings.bindings)
                    history.append_message(
                        loop_conversation.Message(
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
                    last_response = follow_resp
                    follow_args = dict(followup.wire_parameter_bindings.bindings)
                    status_sum, t_rep = _format_tool_log(
                        followup.tool_name,
                        follow_args,
                        follow_resp,
                        turns,
                        is_followup=True,
                    )
                    logger.consume(
                        runner_logger.LogEvent(
                            event_name="tool_execution",
                            summary=status_sum,
                            transcript_representation=t_rep,
                        )
                    )
                    history.append_tool_response(
                        response=follow_resp,
                        tool_name=followup.tool_name,
                        tool_call_id=synth_call_id,
                    )
                    if not follow_resp.is_failed and followup.tool_name in (
                        "replace",
                        "update_lines",
                        "replace_file_content",
                        "advance",
                    ):
                        guard.record_progress()
                    curr_resp = follow_resp
                    if curr_resp.is_terminated:
                        if curr_resp.is_failed:
                            raise RuntimeError(f"Agent failed: {curr_resp.content}")
                        return loop_driver.AgentOutcome(
                            is_success=True,
                            response=curr_resp,
                            conversation=history,
                        )

                # Requirement: When tool execution produces a non-terminating failure response, the failure feedback is appended to the conversation and the run continues.
                # Requirement: When tool execution produces a terminating response, the agent driver concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
                # Requirement: [AgentDriver] When tool execution produces a termination outcome, the agent driver concludes and returns an agent outcome, or halts with an unexpected failure if the termination indicates a failing outcome.
                if resp.is_terminated:
                    if resp.is_failed:
                        raise RuntimeError(f"Agent failed: {resp.content}")
                    return loop_driver.AgentOutcome(
                        is_success=True,
                        response=resp,
                        conversation=history,
                    )

        # Requirement: When turns reach the conversation limit from agent config, the agent driver halts with an unexpected failure.
        # Requirement: [AgentDriver] When the conversation limit from agent config is exceeded, the agent driver halts with an unexpected failure.
        raise RuntimeError(f"Conversation limit reached ({limit} turns)")


AgentDriver = LoopDriver


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopDriver,
        keys=[LoopDriver, loop_driver.LoopDriver, loop_driver.AgentDriver],
        tier=agent_session,
    )
