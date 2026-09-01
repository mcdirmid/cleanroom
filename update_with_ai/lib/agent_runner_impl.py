"""Agent runner implementation executing multi-turn tool loops."""

import json
from typing import Optional, Sequence, Any, Dict
from .tool_provider import (
    ToolProvider,
    TerminationOutcome,
    ToolResult,
    ToolFailure,
    ToolOutcome,
    Tool,
)
from .conversation_history import ConversationHistory, HistoryMessage
from .loop_guard import LoopGuard, LoopFailure, LoopReminder
from .runner_logger import RunnerLogger, LogEvent
from .openai_ext import OpenAiExt, ModelName, CompletionRequest, CompletionResponse
from .agent_runner import (
    AgentRunner,
    AgentOutcome,
    IterationLimit,
)


class AgentRunnerImpl(AgentRunner):
    def __init__(self, openai_ext: OpenAiExt, model: ModelName) -> None:
        self.openai_ext = openai_ext
        self.model = model

    def run(
        self,
        tool_provider: ToolProvider,
        history: ConversationHistory,
        logger: Optional[RunnerLogger] = None,
        loop_guard: Optional[LoopGuard] = None,
        iteration_limit: IterationLimit = 20,
    ) -> AgentOutcome:
        if logger:
            history_text = "\n".join(
                f"[{m.role.upper()}]: {m.content}" for m in history.get_messages()
            )
            logger.log(
                LogEvent(
                    name="session_start",
                    summary="",
                    transcript=f"=== Agent Session Started ===\n{history_text}",
                )
            )

        iterations = 0
        while iterations < iteration_limit:
            iterations += 1
            tools = tool_provider.get_tools()
            tool_metadata_list = [t.get_metadata() for t in tools] if tools else ()

            if logger:
                logger.log(
                    LogEvent(
                        name="turn_start",
                        summary="",
                        transcript=f"\n--- Turn {iterations} ---",
                    )
                )

            req = CompletionRequest(
                messages=history.get_messages(),
                model=self.model,
                tools=tool_metadata_list,
            )

            resp = self.openai_ext.create_chat_completion(req)
            assistant_msg = resp.message
            history.append(assistant_msg)

            # If response is truncated at the generation limit, resume with continuation turn
            if assistant_msg.metadata and assistant_msg.metadata.get("finish_reason") in ("length", "max_tokens", "truncated"):
                history.append(HistoryMessage(role="user", content="continue"))
                continue

            # Check if assistant message contains tool calls
            tool_calls = None
            if assistant_msg.metadata and "tool_calls" in assistant_msg.metadata:
                tool_calls = assistant_msg.metadata["tool_calls"]

            if logger:
                logger.log(
                    LogEvent(
                        name="assistant_response",
                        summary="",
                        transcript=f"[ASSISTANT]: {assistant_msg.content or ''}"
                        + (f"\nTool Calls: {tool_calls}" if tool_calls else ""),
                    )
                )

            if not tool_calls:
                if not tools:
                    # Tool provider offers no tools, concluding with assistant content
                    term = TerminationOutcome(
                        content=str(assistant_msg.content or "Completed successfully"),
                        is_terminal=True,
                    )
                    if logger:
                        logger.log(
                            LogEvent(
                                name="session_end",
                                summary=f"Run finished: {term.content}",
                                transcript=f"\n=== Session Concluded: {term.content} ===",
                            )
                        )
                    return AgentOutcome(
                        termination=term, history=history.get_messages()
                    )

                # Tools are available, model produced no tool calls: record turn and prompt to use tools
                if assistant_msg.content:
                    if loop_guard:
                        guard_res = loop_guard.record_tool_call(
                            "text_response", {"content": assistant_msg.content}
                        )
                        if isinstance(guard_res, LoopFailure):
                            term = TerminationOutcome(
                                content="Loop limit exceeded: fatal repetition",
                                is_terminal=True,
                            )
                            if logger:
                                logger.log(
                                    LogEvent(
                                        name="session_end",
                                        summary=f"Run finished: {term.content}",
                                        transcript=f"\n=== Session Concluded: {term.content} ===",
                                    )
                                )
                            return AgentOutcome(
                                termination=term, history=history.get_messages()
                            )
                        elif isinstance(guard_res, LoopReminder):
                            history.append(
                                HistoryMessage(
                                    role="system",
                                    content=getattr(guard_res, "content", "Loop reminder"),
                                )
                            )
                history.append(
                    HistoryMessage(
                        role="user",
                        content="Please proceed by calling the available tools to complete the task.",
                    )
                )
                continue

            tool_map = {t.get_metadata().name: t for t in tools}

            for tc in tool_calls:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                call_name = fn.get("name", "")
                call_id = tc.get("id", "") if isinstance(tc, dict) else ""
                raw_args = fn.get("arguments", "{}")
                try:
                    call_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    call_args = {}

                if loop_guard:
                    guard_res = loop_guard.record_tool_call(call_name, call_args)
                    if isinstance(guard_res, LoopFailure):
                        term = TerminationOutcome(
                            content="Loop limit exceeded: fatal repetition",
                            is_terminal=True,
                        )
                        if logger:
                            logger.log(
                                LogEvent(
                                    name="session_end",
                                    summary=f"Run finished: {term.content}",
                                    transcript=f"\n=== Session Concluded: {term.content} ===",
                                )
                            )
                        return AgentOutcome(
                            termination=term, history=history.get_messages()
                        )
                    elif isinstance(guard_res, LoopReminder):
                        history.append(
                            HistoryMessage(
                                role="system",
                                content=getattr(guard_res, "content", "Loop reminder"),
                            )
                        )

                tool = tool_map.get(call_name)
                if not tool:
                    fail = ToolFailure(feedback=f"Unknown tool: {call_name}")
                    meta = {"tool_call_id": call_id} if call_id else None
                    history.append(
                        HistoryMessage(role="tool", content=fail.feedback, metadata=meta)
                    )
                    if logger:
                        logger.log(
                            LogEvent(
                                name="tool_execution",
                                summary=f"Tool call: {call_name}({call_args})",
                                transcript=f"[TOOL CALL] {call_name}({json.dumps(call_args)})\n[TOOL ERROR]: {fail.feedback}",
                            )
                        )
                    continue

                res = tool.execute(call_args)
                tool_content = getattr(res, "content", getattr(res, "feedback", str(res)))
                meta = {"tool_call_id": call_id} if call_id else None
                if getattr(res, "guidance", None):
                    meta = meta or {}
                    meta["guidance"] = getattr(res, "guidance")
                history.append(
                    HistoryMessage(
                        role="tool",
                        content=tool_content,
                        metadata=meta,
                    )
                )
                if logger:
                    logger.log(
                        LogEvent(
                            name="tool_execution",
                            summary=f"Tool call: {call_name}({call_args})",
                            transcript=f"[TOOL CALL] {call_name}({json.dumps(call_args)})\n[TOOL RESULT]: {tool_content}",
                        )
                    )

                if isinstance(res, TerminationOutcome):
                    if logger:
                        logger.log(
                            LogEvent(
                                name="session_end",
                                summary=f"Run finished: {res.content}",
                                transcript=f"\n=== Session Concluded: {res.content} ===",
                            )
                        )
                    return AgentOutcome(
                        termination=res, history=history.get_messages()
                    )

        term = TerminationOutcome(
            content="Iteration limit exceeded", is_terminal=True
        )
        if logger:
            logger.log(
                LogEvent(
                    name="session_end",
                    summary=f"Run finished: {term.content}",
                    transcript=f"\n=== Session Concluded: {term.content} ===",
                )
            )
        return AgentOutcome(
            termination=term, history=history.get_messages()
        )
