import json
from typing import Any, Optional, Set, Tuple
from . import agent_conversation_history
from . import agent_loop_guard
from . import agent_runner
from . import model_config
from . import runner_logger
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

try:  # pragma: no cover
    import openai
    OpenAI = openai.OpenAI
    OpenAIError = openai.OpenAIError
except ImportError:  # pragma: no cover
    OpenAI: Any = None
    class _OpenAIError(Exception):
        pass
    OpenAIError: Any = _OpenAIError




class _SimpleParameterConverter:
    @property
    def actual_type(self) -> type:
        return str
    @property
    def wire_type(self) -> tool_provider.WireType:
        return tool_provider.String()
    def convert(self, wire_value: Any) -> Any:
        return wire_value

_DEFAULT_CONVERTER = _SimpleParameterConverter()


def _measure_prefix_reuse(
    prev_payload: Optional[list[dict[str, Any]]],
    curr_payload: list[dict[str, Any]],
    tools_payload: Optional[list[dict[str, Any]]] = None,
) -> Tuple[str, str]:
    if prev_payload is None:
        curr_wire = json.dumps(curr_payload, ensure_ascii=False)
        tools_info = f", {len(tools_payload)} tools" if tools_payload is not None else ""
        summary = f"initial request ({len(curr_payload)} messages sent to OpenAI)"
        transcript = (
            f"Prefix reuse: N/A (initial request, {len(curr_payload)} messages"
            f"{tools_info}, {len(curr_wire)} chars sent to OpenAI)"
        )
        return summary, transcript

    matched_messages = 0
    divergence_idx: Optional[int] = None
    min_msg_count = min(len(prev_payload), len(curr_payload))
    for i in range(min_msg_count):
        if prev_payload[i] == curr_payload[i]:
            matched_messages += 1
        else:
            divergence_idx = i
            break
    if divergence_idx is None and len(prev_payload) > len(curr_payload):
        divergence_idx = len(curr_payload)

    prev_wire = json.dumps(prev_payload, ensure_ascii=False)
    curr_wire = json.dumps(curr_payload, ensure_ascii=False)
    common_prefix_chars = 0
    min_wire_len = min(len(prev_wire), len(curr_wire))
    while (
        common_prefix_chars < min_wire_len
        and prev_wire[common_prefix_chars] == curr_wire[common_prefix_chars]
    ):
        common_prefix_chars += 1

    reuse_pct = (common_prefix_chars / len(curr_wire) * 100.0) if curr_wire else 100.0
    prev_retained_pct = (common_prefix_chars / len(prev_wire) * 100.0) if prev_wire else 100.0

    if divergence_idx is None:
        summary = (
            f"Prefix reuse: {reuse_pct:.1f}% "
            f"({matched_messages}/{len(curr_payload)} messages, 100% of prev request retained)"
        )
    else:
        summary = (
            f"Prefix reuse: {reuse_pct:.1f}% "
            f"({matched_messages}/{len(curr_payload)} messages, diverged at msg {divergence_idx})"
        )

    transcript_lines = [
        f"Prefix reuse: {reuse_pct:.1f}% "
        f"({common_prefix_chars}/{len(curr_wire)} chars wire match, "
        f"{matched_messages}/{len(curr_payload)} messages matched, "
        f"{prev_retained_pct:.1f}% of prev request retained)"
    ]
    if tools_payload is not None:
        transcript_lines.append(f"Tools payload: {len(tools_payload)} tools, static canonical schema.")

    if divergence_idx is not None:
        p_m = prev_payload[divergence_idx] if divergence_idx < len(prev_payload) else None
        c_m = curr_payload[divergence_idx] if divergence_idx < len(curr_payload) else None
        transcript_lines.append(f"Divergence detected at message index {divergence_idx}:")
        if p_m is not None and c_m is not None:
            if p_m.get("role") != c_m.get("role"):
                transcript_lines.append(
                    f"  Role mismatch: prev={p_m.get('role')!r} vs curr={c_m.get('role')!r}"
                )
            if p_m.get("tool_call_id") != c_m.get("tool_call_id"):
                transcript_lines.append(
                    f"  tool_call_id mismatch: prev={p_m.get('tool_call_id')!r} vs curr={c_m.get('tool_call_id')!r}"
                )
            p_content = p_m.get("content") or ""
            c_content = c_m.get("content") or ""
            if p_content != c_content:
                p_preview = p_content[:120].replace("\n", "\\n")
                c_preview = c_content[:120].replace("\n", "\\n")
                transcript_lines.append(
                    f"  Content changed (prev_len={len(p_content)}, curr_len={len(c_content)}):"
                )
                transcript_lines.append(f"    prev: {p_preview!r}")
                transcript_lines.append(f"    curr: {c_preview!r}")
            if p_m.get("tool_calls") != c_m.get("tool_calls"):
                transcript_lines.append(
                    f"  tool_calls mismatch: prev={p_m.get('tool_calls')} vs curr={c_m.get('tool_calls')}"
                )
        elif p_m is not None:
            transcript_lines.append(
                f"  Current conversation is shorter than previous conversation ({len(curr_payload)} < {len(prev_payload)})"
            )
        else:
            transcript_lines.append(
                f"  Previous conversation was shorter ({len(prev_payload)} < {len(curr_payload)})"
            )
    else:
        transcript_lines.append(
            f"Prefix intact: All {len(prev_payload)} messages from previous request matched as exact prefix."
        )

    return summary, "\n".join(transcript_lines)


class AgentRunner(agent_runner.AgentRunner, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    def run(self) -> agent_runner.AgentOutcome:
        model_cfg = get_singleton(model_config.ModelConfig)
        logger = get_singleton(runner_logger.RunnerLogger)
        history = get_singleton(agent_conversation_history.ConversationHistory)
        guard = get_singleton(agent_loop_guard.LoopGuard)
        tool_mgr = get_singleton(tool_provider.ToolManager)

        client: Any = None
        if OpenAI is not None:
            client = OpenAI(
                api_key=model_cfg.api_key if model_cfg.api_key else "none",
                base_url=model_cfg.base_url,
                timeout=float(model_cfg.timeout),
            )


        # Requirement: When driving a turn, the agent runner transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
        tools_payload: list[dict[str, Any]] = []
        for t in sorted(tool_mgr.installed_tools, key=lambda x: x.name):
            props = {}
            req_props = []
            for p in sorted(t.parameters, key=lambda x: x.name):
                props[p.name] = {"type": "string", "description": p.description}
                if p.is_required:
                    req_props.append(p.name)
            tools_payload.append({
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
            })
        if tools_payload:
            tools_payload = json.loads(json.dumps(tools_payload, sort_keys=True))

        limit = model_cfg.conversation_limit
        turns = 0
        last_response: tool_provider.Response = tool_provider.Response(
            is_failed=False, is_terminated=False, content="Initialized"
        )
        prev_messages_payload: Optional[list[dict[str, Any]]] = None

        # Requirement: [AgentRunner] The agent runner drives turns by sending model requests to a language model and executing requested tools.
        while turns < limit:
            turns += 1
            model_req = history.get_model_request()
            messages_payload = []
            for m in model_req.messages:
                if m.role == "assistant" and m.tool_name:
                    messages_payload.append({
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
                    })
                elif m.role == "tool":
                    messages_payload.append({
                        "role": "tool",
                        "content": m.content,
                        "tool_call_id": m.tool_call_id or "",
                    })
                else:
                    messages_payload.append({"role": m.role, "content": m.content})

            messages_payload = json.loads(json.dumps(messages_payload, sort_keys=True))

            reuse_summary, reuse_transcript = _measure_prefix_reuse(
                prev_messages_payload, messages_payload, tools_payload=tools_payload
            )
            # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool names and arguments or text previews, and execution outcomes, including corrective reminders in tool result transcripts when present.
            logger.consume(
                runner_logger.LogEvent(
                    event_name="model_request",
                    summary=f"[Turn {turns}] {reuse_summary}",
                    transcript_representation=f"=== Turn {turns} ===\nMessages: {len(messages_payload)}\n{reuse_transcript}",
                )
            )

            if client is None:  # pragma: no cover
                # Fallback for environments without live OpenAI network / mock
                break

            prev_messages_payload = json.loads(json.dumps(messages_payload))

            try:
                # Requirement: When driving a turn, the agent runner transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
                create_kwargs: dict[str, Any] = {
                    "model": model_cfg.model_name,
                    "messages": messages_payload,
                    "tools": tools_payload if tools_payload else None,
                    "temperature": model_cfg.temperature,
                    "timeout": float(model_cfg.timeout),
                }
                if model_cfg.max_tokens is not None:
                    create_kwargs["max_tokens"] = model_cfg.max_tokens

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

            choice = completion.choices[0]
            finish_reason = choice.finish_reason
            assistant_msg = choice.message
            tool_calls = assistant_msg.tool_calls or []

            # Requirement: [AgentRunner] The agent runner appends model responses and correlates tool responses with tool call identifiers in conversation history.
            if tool_calls:
                for tc in tool_calls:
                    history.append_message(
                        agent_conversation_history.Message(
                            role="assistant",
                            content=assistant_msg.content or "",
                            tool_call_id=tc.id,
                            tool_name=tc.function.name,
                            tool_arguments=tc.function.arguments or "{}",
                        )
                    )
            else:
                history.append_message(
                    agent_conversation_history.Message(
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
                        formatted_args = ", ".join(f"{k}={repr(v)}" for k, v in tc_args.items())
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
                completion_summary = f"[Turn {turns}] Assistant (text): {json.dumps(text_preview)}"

            # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool names and arguments or text previews, and execution outcomes, including corrective reminders in tool result transcripts when present.
            logger.consume(
                runner_logger.LogEvent(
                    event_name="model_completion",
                    summary=completion_summary,
                    transcript_representation=f"=== Assistant Response (turn {turns}) ===\nFinish: {finish_reason}\nContent: {assistant_msg.content}\nTool calls: {[tc.function.name for tc in tool_calls]}",
                )
            )

            # Requirement: When a model response is truncated at the generation limit, the agent runner resumes generation with a continuation turn.
            if finish_reason == "length":
                history.append_message(
                    agent_conversation_history.Message(
                        role="user",
                        content="Response was truncated due to length. Please continue.",
                    )
                )
                continue

            if not tool_calls:
                # Requirement: When a model response produces no tool executions, the agent runner appends a prompt to the conversation history reminding that progress and conclusion require invoking tools, and continues the turn loop.
                history.append_message(
                    agent_conversation_history.Message(
                        role="user",
                        content="No tools were executed. You must call a tool (e.g. read_file, replace, advance, fail, blame) to make progress or conclude the session.",
                    )
                )
                continue

            # Requirement: [AgentRunner] The agent runner drives turns by sending model requests to a language model and executing requested tools.
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
                                conv_val = v
                            actual_bindings_set.add((p, conv_val))
                        else:
                            dummy_p = tool_provider.Parameter(name=k, description="", parameter_converter=_DEFAULT_CONVERTER)
                            actual_bindings_set.add((dummy_p, v))
                else:
                    for k, v in args_dict.items():
                        dummy_p = tool_provider.Parameter(name=k, description="", parameter_converter=_DEFAULT_CONVERTER)
                        actual_bindings_set.add((dummy_p, v))

                actual_bindings = tool_provider.ActualParameterBindings(bindings=actual_bindings_set)

                # Requirement: Before executing each tool call, the agent runner records the tool execution in the loop guard, injecting a loop reminder into the conversation history when a reminder is produced, or concluding the run with an unexpected failure when a loop failure is produced.
                # Requirement: [AgentRunner] The agent runner evaluates tool executions with the loop guard, injecting reminders or halting with an unexpected failure on runaway repetition.
                guard_outcome = guard.record_tool_execution(fn_name, actual_bindings)
                if isinstance(guard_outcome, agent_loop_guard.LoopFailure):
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

                raw_snippet = (resp.content or "").strip()
                first_line = raw_snippet.splitlines()[0] if raw_snippet else ""
                if len(first_line) > 80:
                    first_line = first_line[:77] + "..."

                if resp.is_failed:
                    tool_status_summary = f"[Turn {turns}] Tool {fn_name}: FAILED -> {first_line}"
                elif resp.is_terminated:
                    tool_status_summary = f"[Turn {turns}] Tool {fn_name}: COMPLETED -> {first_line}"
                else:
                    tool_status_summary = f"[Turn {turns}] Tool {fn_name}: OK -> {first_line}"

                transcript_rep = (
                    f"{resp.content}\n\nReminder: {resp.reminder}"
                    if resp.reminder
                    else resp.content
                )
                # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool names and arguments or text previews, and execution outcomes, including corrective reminders in tool result transcripts when present.
                logger.consume(
                    runner_logger.LogEvent(
                        event_name="tool_execution",
                        summary=tool_status_summary,
                        transcript_representation=transcript_rep,
                    )
                )

                # Requirement: [AgentRunner] The agent runner appends model responses and correlates tool responses with tool call identifiers in conversation history.
                history.append_tool_response(
                    response=resp,
                    tool_name=fn_name,
                    tool_call_id=tc.id,
                )

                if isinstance(guard_outcome, agent_loop_guard.LoopReminder):
                    logger.consume(
                        runner_logger.LogEvent(
                            event_name="loop_reminder",
                            summary=f"[Turn {turns}] Loop reminder: {guard_outcome.feedback}",
                            transcript_representation=guard_outcome.feedback,
                        )
                    )
                    history.append_message(
                        agent_conversation_history.Message(
                            role="user",
                            content=guard_outcome.feedback,
                        )
                    )

                # Requirement: Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard.
                if not resp.is_failed and fn_name in ("replace", "update_lines", "advance"):
                    guard.record_progress()

                # Requirement: When configured by model config to inject followups, a tool response specifying a follow-up tool call prompts execution of the designated tool through the tool manager, appending a synthetic assistant invocation and the resulting follow-up response to the conversation history immediately following the originating response.
                # Requirement: [AgentRunner] The agent runner can dispatch follow-up tool calls specified by tool responses, recording the follow-up execution in the conversation history.
                curr_resp = resp
                curr_call_id = tc.id
                followup_count = 0
                while model_cfg.inject_followups and curr_resp.follow_up_tool_call is not None and not curr_resp.is_terminated:
                    followup = curr_resp.follow_up_tool_call
                    followup_count += 1
                    synth_call_id = f"{curr_call_id}_followup_{followup_count}"
                    args_dict = dict(followup.wire_parameter_bindings.bindings)
                    history.append_message(
                        agent_conversation_history.Message(
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
                    raw_snippet = (follow_resp.content or "").strip()
                    first_line = raw_snippet.splitlines()[0] if raw_snippet else ""
                    if len(first_line) > 80:
                        first_line = first_line[:77] + "..."
                    if follow_resp.is_failed:
                        status_sum = f"[Turn {turns}] Follow-up Tool {followup.tool_name}: FAILED -> {first_line}"
                    elif follow_resp.is_terminated:
                        status_sum = f"[Turn {turns}] Follow-up Tool {followup.tool_name}: COMPLETED -> {first_line}"
                    else:
                        status_sum = f"[Turn {turns}] Follow-up Tool {followup.tool_name}: OK -> {first_line}"
                    t_rep = (
                        f"{follow_resp.content}\n\nReminder: {follow_resp.reminder}"
                        if follow_resp.reminder
                        else follow_resp.content
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
                    if not follow_resp.is_failed and followup.tool_name in ("replace", "update_lines", "advance"):
                        guard.record_progress()
                    curr_resp = follow_resp
                    if curr_resp.is_terminated:
                        if curr_resp.is_failed:
                            raise RuntimeError(f"Agent failed: {curr_resp.content}")
                        return agent_runner.AgentOutcome(
                            is_success=True,
                            response=curr_resp,
                            conversation_history=history,
                        )

                # Requirement: When tool execution produces a non-terminating failure response, the failure feedback is appended to the conversation history and the run continues.
                # Requirement: When tool execution produces a terminating response, the agent runner concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
                # Requirement: [AgentRunner] When tool execution produces a termination outcome, the agent runner concludes and returns an agent outcome, or halts with an unexpected failure if the termination indicates a failing outcome.
                if resp.is_terminated:
                    if resp.is_failed:
                        raise RuntimeError(f"Agent failed: {resp.content}")
                    return agent_runner.AgentOutcome(
                        is_success=True,
                        response=resp,
                        conversation_history=history,
                    )

        # Requirement: When turns reach the conversation limit from model config, the agent runner halts with an unexpected failure.
        # Requirement: [AgentRunner] When the conversation limit from model config is exceeded, the agent runner halts with an unexpected failure.
        raise RuntimeError(f"Conversation limit reached ({limit} turns)")

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AgentRunner,
        keys=[AgentRunner, agent_runner.AgentRunner],
        tier="agent_session",
    )
