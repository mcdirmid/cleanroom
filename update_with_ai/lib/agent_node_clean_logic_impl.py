"""
Implementation LLS: agent_node_clean_logic_impl
Provides the agent_node_clean_logic_impl implementation that fulfills the dag_clean_logic contract.
"""

from __future__ import annotations
from typing import List, Optional, Callable, Dict, Any
import dataclasses
import os

from .dag_clean_logic import (
    DagCleanLogic,
    NodeId,
    CleanResult,
    ChangeResult,
    FeedbackResult,
    NoChangeResult,
    FailureResult,
)
from .dag_storage import NodeMessage
from .build_graph_storage import BuildGraphStorage, NodeDefinition
from .agent_loop import (
    AgentLoop,
    AgentResult,
    LoggerCallback,
    LogEvent,
)
from .agent_loop_config import AgentLoopConfig
from .sandbox import SandboxConfig, Sandbox
from .agent_node_tool_executor import AgentNodeToolExecutor
from .tool_provider import (
    ToolCallOutcome,
    ToolDefinition,
    ToolFailure,
    TerminateAgentWithSuccess,
)


class AgentNodeCleanLogicImpl(DagCleanLogic):
    """
    Implementation of dag_clean_logic.DagCleanLogic (agent-loop-based).
    """

    def __init__(
        self,
        graph: BuildGraphStorage,
        agent_loop_config: AgentLoopConfig,
        make_sandbox: Callable[[SandboxConfig], Sandbox],
        make_agent_loop: Callable[[AgentLoopConfig], AgentLoop],
        make_tool_executor: Optional[Callable[[Sandbox], AgentNodeToolExecutor]] = None,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        self._graph = graph
        self._agent_loop_config = agent_loop_config
        self._make_sandbox = make_sandbox
        self._make_agent_loop = make_agent_loop
        self._make_tool_executor = make_tool_executor
        self._logger = logger

    def clean(self, node_id: NodeId, messages: List[NodeMessage]) -> CleanResult:
        node_def: NodeDefinition = self._graph.resolve_node_definition(node_id)
        has_feedback = any(m.kind == "feedback" for m in messages)
        sandbox_config = dataclasses.replace(
            node_def.sandbox_config,
            feedback_pending=has_feedback,
        )
        sandbox: Sandbox = self._make_sandbox(sandbox_config)

        if self._make_tool_executor is not None:
            tool_executor_instance = self._make_tool_executor(sandbox)
            def _tool_executor(name: str, arguments: Dict[str, Any]) -> ToolCallOutcome:
                return tool_executor_instance.execute_tool(name, arguments)
            _tool_executor.get_tool_definitions = tool_executor_instance.get_tool_definitions  # type: ignore[attr-defined]
            session_start_reads = tool_executor_instance.get_session_start_reads()
            tools = tool_executor_instance.get_tool_definitions()
        else:
            tools = sandbox.get_tool_definitions()
            def _tool_executor(name: str, arguments: Dict[str, Any]) -> ToolCallOutcome:
                method = getattr(sandbox, name, None)
                if method is None:
                    return ToolFailure[str](f"Tool {name} not found")
                try:
                    if arguments:
                        return method(**arguments)
                    return method()
                except Exception as e:
                    return ToolFailure[str](str(e))
            _tool_executor.get_tool_definitions = lambda: sandbox.get_tool_definitions()  # type: ignore[attr-defined]
            session_start_reads = sandbox.get_session_start_reads()

        readable = sorted(set(node_def.sandbox_config.readable_paths))
        writable = sorted(set(node_def.sandbox_config.writable_paths))
        file_lines: List[str] = []
        if readable:
            file_lines.append(f"Files you can read: {', '.join(readable)}")
        if writable:
            file_lines.append(f"Files you can write: {', '.join(writable)}")

        system_prompt = node_def.prompt
        if file_lines:
            system_prompt += "\n\n" + "\n".join(file_lines)

        user_prompt_lines = [m.text for m in messages]
        if node_def.sandbox_config.step_sections_enabled and node_def.sandbox_config.guide:
            user_prompt_lines.append(
                "Step mode is enabled: the guide arrives through the advance operation — the guide summary at run start, then a step section after each advance that passed verification; call advance after each section."
            )
        user_prompt = "\n".join(user_prompt_lines)

        run_logger: Optional[LoggerCallback] = None
        if self._logger is not None:
            captured_logger = self._logger
            def _node_logger(event: LogEvent, data: Dict[str, Any]) -> None:
                enriched = dict(data)
                enriched["node_id"] = node_id
                captured_logger(event, enriched)
            run_logger = _node_logger

        agent_loop: AgentLoop = self._make_agent_loop(self._agent_loop_config)
        outcome, _ = agent_loop.run_agent(
            prompt=user_prompt,
            tools=tools,
            tool_executor=_tool_executor,
            system_prompt=system_prompt,
            session_start_results=session_start_reads,
            logger=run_logger,
        )

        if isinstance(outcome, TerminateAgentWithSuccess):
            val = outcome.value
            if isinstance(val, (ChangeResult, FeedbackResult, NoChangeResult)):
                return val
            return NoChangeResult()

        return FailureResult()

    def is_dirty(self, node_id: NodeId, pending_messages: List[NodeMessage]) -> bool:
        if pending_messages:
            return True

        node_def: NodeDefinition = self._graph.resolve_node_definition(node_id)
        templates = node_def.sandbox_config.templates or {}
        file_mappings = node_def.sandbox_config.file_mappings

        for virt_path in node_def.sandbox_config.writable_paths:
            real_path = file_mappings.get(virt_path)
            if real_path is None:
                continue

            template_content = templates.get(virt_path)
            if not os.path.exists(real_path):
                if template_content != "":
                    self._deliver_template_feedback(node_id, pending_messages)
                    return True
            else:
                if template_content is not None and template_content != "":
                    try:
                        with open(real_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        if content == template_content:
                            self._deliver_template_feedback(node_id, pending_messages)
                            return True
                    except OSError:
                        pass
        return False

    def _deliver_template_feedback(
        self, node_id: NodeId, pending_messages: List[NodeMessage]
    ) -> None:
        already_pending = any(
            m.kind == "feedback" and m.text == "update target file from template"
            for m in pending_messages
        )
        if not already_pending:
            self._graph.add_messages(
                node_id,
                [NodeMessage(kind="feedback", text="update target file from template")],
            )
