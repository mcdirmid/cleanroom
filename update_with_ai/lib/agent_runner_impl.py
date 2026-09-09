import json
from typing import Any, Optional
from . import agent_conversation_history
from . import agent_loop_guard
from . import agent_runner
from . import model_config
from . import runner_logger
from . import tool_provider
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

try:  # pragma: no cover
    import openai
    OpenAI = openai.OpenAI
    OpenAIError = openai.OpenAIError
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore
    class OpenAIError(Exception):  # type: ignore
        pass



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


        limit = model_cfg.conversation_limit
        turns = 0
        last_response: tool_provider.Response = tool_provider.Response(
            is_failed=False, is_terminated=False, content="Initialized"
        )

        # Requirement: Executes agent turns bounded by conversation limit
        while turns < limit:
            turns += 1
            model_req = history.get_model_request()
            # Requirement: Logs model request events to runner logger
            logger.consume(
                runner_logger.LogEvent(
                    event_name="model_request",
                    summary=f"Turn {turns}: Requesting completion with {len(model_req.messages)} messages",
                    transcript_representation=f"=== Turn {turns} ===\nMessages: {len(model_req.messages)}",
                )
            )

            if client is None:  # pragma: no cover
                # Fallback for environments without live OpenAI network / mock
                break

            messages_payload = [
                {"role": m.role, "content": m.content}
                for m in model_req.messages
            ]

            # Requirement: Translates tool schemas for model function calling
            tools_payload = []
            for t in tool_mgr.installed_tools:
                props = {}
                req_props = []
                for p in t.parameters:
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

            try:
                # Requirement: Queries model completion using configured parameters
                completion = client.chat.completions.create(
                    model=model_cfg.model_name,
                    messages=messages_payload,  # type: ignore
                    tools=tools_payload if tools_payload else None,  # type: ignore
                    temperature=0.0,
                )
            except OpenAIError as e:
                logger.consume(
                    runner_logger.LogEvent(
                        event_name="model_error",
                        summary=f"Model error: {e}",
                        transcript_representation=str(e),
                    )
                )
                last_response = tool_provider.Response(
                    is_failed=True, is_terminated=True, content=f"Model error: {e}"
                )
                return agent_runner.AgentOutcome(
                    is_success=False,
                    response=last_response,
                    conversation_history=history,
                )

            choice = completion.choices[0]
            finish_reason = choice.finish_reason
            assistant_msg = choice.message
            tool_calls = assistant_msg.tool_calls or []

            # Requirement: Appends assistant message to conversation history
            history.append_message(
                agent_conversation_history.Message(
                    role="assistant",
                    content=assistant_msg.content or "",
                )
            )

            # Requirement: Records log event for model completion
            logger.consume(
                runner_logger.LogEvent(
                    event_name="model_completion",
                    summary=f"Turn {turns}: finish_reason={finish_reason}, {len(tool_calls)} tool calls",
                    transcript_representation=f"=== Assistant Response (turn {turns}) ===\nFinish: {finish_reason}\nContent: {assistant_msg.content}\nTool calls: {[tc.function.name for tc in tool_calls]}",
                )
            )

            # Requirement: Appends continue user prompt on length truncation
            if finish_reason == "length":
                history.append_message(
                    agent_conversation_history.Message(
                        role="user",
                        content="Response was truncated due to length. Please continue.",
                    )
                )
                continue

            if not tool_calls:
                # Requirement: Concludes successfully when assistant emits a response without tool calls
                last_response = tool_provider.Response(
                    is_failed=False,
                    is_terminated=True,
                    content=assistant_msg.content or "",
                )
                break

            # Requirement: Dispatches model tool calls to tool manager
            for tc in tool_calls:
                fn_name = tc.function.name
                fn_args_str = tc.function.arguments
                args_dict = json.loads(fn_args_str) if fn_args_str else {}

                wire_bindings = {(k, v) for k, v in args_dict.items()}

                resp = tool_mgr.execute_tool(
                    fn_name, tool_provider.WireParameterBindings(bindings=wire_bindings)
                )
                last_response = resp

                logger.consume(
                    runner_logger.LogEvent(
                        event_name="tool_execution",
                        summary=f"Executed {fn_name}: failed={resp.is_failed}, terminated={resp.is_terminated}",
                        transcript_representation=resp.content,
                    )
                )

                # Requirement: Records tool execution responses in conversation history
                history.append_tool_response(
                    response=resp,
                    tool_name=fn_name,
                    tool_call_id=tc.id,
                )

                # Requirement: Terminates runner loop when tool response signals termination
                if resp.is_terminated:
                    return agent_runner.AgentOutcome(
                        is_success=not resp.is_failed,
                        response=resp,
                        conversation_history=history,
                    )

        # Requirement: Returns final agent outcome when turns exhausted or complete
        return agent_runner.AgentOutcome(
            is_success=not last_response.is_failed,
            response=last_response,
            conversation_history=history,
        )

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AgentRunner,
        keys=[AgentRunner, agent_runner.AgentRunner],
        tier="agent_session",
    )
