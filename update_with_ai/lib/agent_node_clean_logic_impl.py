"""
Implementation LLS: agent_node_clean_logic_impl
Provides the agent_node_clean_logic_impl implementation that fulfills the dag_clean_logic contract.
"""

from __future__ import annotations
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass
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
from .bazel_graph_storage import BazelGraphStorage, NodeDefinition
from .agent_loop import (
    AgentLoop,
    AgentLoopConfig,
    AgentResult,
    FinalAnswer,
    LoggerCallback,
    LogEvent,
)
from .sandbox import SandboxConfig, Sandbox
from .tool_provider import (
    ToolCallOutcome,
    ToolDefinition,
    ToolExecutor,
    ToolFailure,
    TerminateAgentWithSuccess,
)


@dataclass
class Config:
    graph: BazelGraphStorage
    agent_loop_config: AgentLoopConfig
    make_sandbox: Callable[[SandboxConfig], Sandbox]
    make_agent_loop: Callable[[AgentLoopConfig], AgentLoop]
    logger: Optional[LoggerCallback] = None


class AgentNodeCleanLogicImpl(DagCleanLogic):
    """
    Implementation of dag_clean_logic.DagCleanLogic (agent-loop-based).

    Note: the dag_clean_logic interface admits multiple implementations, so
    the implementation name does not match the interface name (per the LLS
    naming rule); the class still extends the DagCleanLogic protocol.

    Operation Implemented: dag_clean_logic.clean, dag_clean_logic.is_dirty
    """

    def __init__(self, config: Config) -> None:
        self._graph = config.graph
        self._agent_loop_config = config.agent_loop_config
        self._make_sandbox = config.make_sandbox
        self._make_agent_loop = config.make_agent_loop
        self._logger = config.logger

    def clean(self, node_id: NodeId, messages: List[NodeMessage]) -> CleanResult:
        """
        Process a node's pending messages by running the agent loop.

        Operation Implemented: dag_clean_logic.clean

        Preconditions:
        - node_id is a valid Bazel target label
        - messages are pending messages for the node

        Postconditions:
        - Returns CleanResult mapping the agent run outcome per the HLS contract
        - ChangeResult if FinalAnswer and write_occurred
        - FeedbackResult if the termination value is a FeedbackResult and targets are valid dependencies
        - NoChangeResult otherwise
        - FailureResult on agent failure

        Failure Handling:
        - Agent failures signal failure per the dag_clean_logic contract,
          leaving pending messages unchanged.
        """
        node_def: NodeDefinition = self._graph.resolve_node_definition(node_id)
        sandbox: Sandbox = self._make_sandbox(node_def.sandbox_config)
        tools: List[ToolDefinition] = sandbox.get_tool_definitions()

        def _tool_executor(name: str, arguments: Dict[str, Any]) -> ToolCallOutcome:
            """Per-call tool executor (tool_provider.ToolExecutor): dispatch a
            single tool call to the sandbox operation of the same name."""
            if name == "blame":
                # Additional validation layer: a blame target must be a
                # dependency of the node (the sandbox already validated the
                # targets against the configured blame_targets). An invalid
                # target is a tool failure, not an agent failure: the agent
                # may correct its blame and continue.
                deps = set(self._graph.get_node_dependencies(node_id))
                for target, _feedback in arguments.get("blames", []):
                    if target not in deps:
                        return ToolFailure[str](
                            f"Blame target {target} is not a dependency of {node_id}"
                        )
            method = getattr(sandbox, name, None)
            if method is None:
                return ToolFailure[str](f"Tool {name} not found")

            try:
                if arguments:
                    return method(**arguments)
                return method()
            except Exception as e:
                return ToolFailure[str](str(e))

        context: List[dict] = [
            {"role": "user", "content": msg} for msg in messages
        ]

        # The initial instructions name the files the agent may read and
        # write (bare names; the sandbox resolves them to real paths).
        readable = sorted(set(node_def.sandbox_config.readable_paths))
        writable = sorted(set(node_def.sandbox_config.writable_paths))
        file_lines: List[str] = []
        if readable:
            file_lines.append(f"Files you can read: {', '.join(readable)}")
        if writable:
            file_lines.append(f"Files you can write: {', '.join(writable)}")

        prompt = node_def.prompt
        if file_lines:
            prompt = f"{prompt}\n\n" + "\n".join(file_lines)

        # Pending messages (change/feedback received from other nodes) are
        # surfaced to the agent as context on top of the node's prompt, so
        # feedback delivered via a *_feedback target is actually acted on
        # during cleaning.
        if context:
            feedback_text = "\n".join(f"- {m}" for m in messages)
            prompt = f"{prompt}\n\nFeedback from dependents:\n{feedback_text}"

        # Wrap the configured logger with the node id so consumers (stdout
        # printer, transcript file) can attribute events to the cleaned node.
        logger: Optional[LoggerCallback] = None
        logger_cb = self._logger
        if logger_cb is not None:
            def _node_logger(event: LogEvent, data: Dict[str, Any]) -> None:
                logger_cb(event, {**data, "node_id": node_id})
            logger = _node_logger

        agent_loop = self._make_agent_loop(self._agent_loop_config)
        agent_result: AgentResult = agent_loop.run_agent(
            prompt=prompt,
            tools=tools,
            tool_executor=_tool_executor,
            logger=logger,
        )

        write_occurred = sandbox.get_write_occurred()
        return self._map_result(agent_result, node_id, write_occurred)

    def is_dirty(self, node_id: NodeId, pending_messages: List[NodeMessage]) -> bool:
        """
        Determine if a node requires cleaning.

        Operation Implemented: dag_clean_logic.is_dirty

        Postconditions:
        - Returns True if the node has pending messages, or if any writable
          output file (declared via srcs) does not exist on disk.
        """
        node_def = self._graph.resolve_node_definition(node_id)
        config = node_def.sandbox_config
        for path in config.writable_paths:
            # writable_paths are virtual names; resolve to the real on-disk
            # location via file_mappings before checking existence.
            real_path = config.file_mappings.get(path, path)
            if not os.path.exists(real_path):
                return True
        return len(pending_messages) > 0

    def _map_result(
        self,
        result: AgentResult,
        node_id: NodeId,
        write_occurred: bool,
    ) -> CleanResult:
        """Map the agent run outcome to a CleanResult per the HLS contract."""
        if isinstance(result, FinalAnswer):
            if write_occurred:
                return ChangeResult(messages=[str(result.answer)])
            return NoChangeResult()

        if isinstance(result, tuple):
            # Termination outcomes pair the tool-provider termination signal
            # with the conversation history; a loop failure pairs an error
            # string with the history.
            signal, _history = result
            if isinstance(signal, TerminateAgentWithSuccess):
                # The termination value is the TerminateSuccessResult formed by
                # the sandbox's termination tool (succeed: ChangeResult if the
                # run modified the workspace, otherwise NoChangeResult; blame:
                # FeedbackResult). Blame targets were validated at call time;
                # an invalid target produced a tool failure instead. Per the
                # LLS the value is always one of these three; the NoChangeResult
                # fallback is defensive for out-of-contract values.
                value = signal.value
                if isinstance(value, FeedbackResult):
                    return value
                if isinstance(value, (ChangeResult, NoChangeResult)):
                    return value
                return NoChangeResult()
            # A loop failure (error string) or a failure termination
            # (TerminateAgentWithFailure): cleaning failed.
            return FailureResult()

        return NoChangeResult()
