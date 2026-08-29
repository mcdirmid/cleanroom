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
from .tool_provider import (
    ToolCallOutcome,
    ToolDefinition,
    ToolExecutor,
    ToolFailure,
    TerminateAgentWithSuccess,
)


class AgentNodeCleanLogicImpl(DagCleanLogic):
    """
    Implementation of dag_clean_logic.DagCleanLogic (agent-loop-based).

    Note: the dag_clean_logic interface admits multiple implementations, so
    the implementation name does not match the interface name (per the LLS
    naming rule); the class still extends the DagCleanLogic protocol.

    Operation Implemented: dag_clean_logic.clean, dag_clean_logic.is_dirty
    """

    def __init__(
        self,
        graph: BuildGraphStorage,
        agent_loop_config: AgentLoopConfig,
        make_sandbox: Callable[[SandboxConfig], Sandbox],
        make_agent_loop: Callable[[AgentLoopConfig], AgentLoop],
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        self._graph = graph
        self._agent_loop_config = agent_loop_config
        self._make_sandbox = make_sandbox
        self._make_agent_loop = make_agent_loop
        self._logger = logger

    def clean(self, node_id: NodeId, messages: List[NodeMessage]) -> CleanResult:
        """
        Process a node's pending messages by running the agent loop.

        Operation Implemented: dag_clean_logic.clean

        Preconditions:
        - node_id is a valid Bazel target label
        - messages are pending messages for the node

        Postconditions:
        - Returns CleanResult mapping the agent run outcome per the HLS contract
        - ChangeResult/NoChangeResult/FeedbackResult from the termination signal's value
        - FailureResult on agent failure (including a loop failure: there is no
          free-text final answer — a run completes only via a termination tool)

        Failure Handling:
        - Agent failures signal failure per the dag_clean_logic contract,
          leaving pending messages unchanged.
        """
        node_def: NodeDefinition = self._graph.resolve_node_definition(node_id)
        # The sandbox is configured with whether the run is processing
        # feedback (per the impl LLS): a pending feedback message obligates
        # the node to change, blame, or fail — advance enforces it.
        has_feedback = any(m.kind == "feedback" for m in messages)
        sandbox_config = dataclasses.replace(
            node_def.sandbox_config,
            feedback_pending=has_feedback,
        )
        sandbox: Sandbox = self._make_sandbox(sandbox_config)
        tools: List[ToolDefinition] = sandbox.get_tool_definitions()

        def _get_tool_definitions() -> List[ToolDefinition]:
            """Current tool definitions (tool_provider.ToolExecutor): the
            sandbox's definitions, re-requested before each agent-loop request
            so a tool's definition may change during the run (per the
            sandbox's step mode, the advance tool's definition gains the
            change argument when the run reaches its final step)."""
            return sandbox.get_tool_definitions()

        def _tool_executor(name: str, arguments: Dict[str, Any]) -> ToolCallOutcome:
            """Per-call tool executor (tool_provider.ToolExecutor): dispatch a
            single tool call to the sandbox operation of the same name."""
            if name == "blame":
                # Additional validation layer: a blame target is the virtual
                # name of a blameable artifact; resolve it to its owning node
                # via the sandbox configuration's blame_targets mapping, then
                # validate the owning node is a dependency of the node (the
                # sandbox itself resolves and validates the targets at call
                # time). An invalid target is a tool failure, not an agent
                # failure: the agent may correct its blame and continue.
                deps = set(self._graph.get_node_dependencies(node_id))
                valid_targets = [
                    t for t, owner in sandbox_config.blame_targets.items() if owner in deps
                ]
                for item in arguments.get("blames", []):
                    if isinstance(item, dict):
                        target = str(item.get("target") or "")
                    elif isinstance(item, (tuple, list)) and len(item) == 2:
                        target = str(item[0])
                    else:
                        target = ""
                    owner = sandbox_config.blame_targets.get(target)
                    if owner is None or owner not in deps:
                        return ToolFailure[str](
                            f"Blame target '{target}' is invalid. Valid blame targets are: {valid_targets}"
                        )
            method = getattr(sandbox, name, None)
            if method is None:
                return ToolFailure[str](f"Tool {name} not found")

            try:
                if arguments:
                    return method(**arguments)
                return method()
            except TypeError as e:
                # A parameter-name slip (e.g. "new_str" instead of
                # "new_str"): tell the agent which parameters the tool
                # actually accepts so it can retry without re-reading.
                params = "unknown"
                for td in tools:
                    fn = td.get("function", {})
                    if fn.get("name") == name:
                        props = fn.get("parameters", {}).get("properties", {})
                        params = ", ".join(sorted(props))
                hint = ""
                err_str = str(e)
                if name == "update_lines" and "old_str" in err_str:
                    hint = " (note: 'old_str' belongs to replace; update_lines takes start_line, end_line, new_str, file_path)"
                elif name == "replace" and ("start_line" in err_str or "end_line" in err_str):
                    hint = " (note: line numbers belong to update_lines; replace takes file_path, old_str, new_str)"
                return ToolFailure[str](
                    f"Invalid parameters for {name}: {e} — valid parameters: {params}{hint}"
                )
            except Exception as e:
                return ToolFailure[str](str(e))

        # Expose the current-definitions getter on the executor (per
        # tool_provider.ToolExecutor): the agent loop re-requests the tool
        # definitions before each request.
        _tool_executor.get_tool_definitions = _get_tool_definitions  # type: ignore[attr-defined]

        # Prompt composition (per the impl LLS): the run's system prompt is the
        # node's prompt augmented with lines naming the readable and writable
        # files (bare names; the sandbox resolves them to real paths); the
        # run's user prompt is the node's pending messages joined by newlines
        # (empty when there are no pending messages), so feedback delivered
        # via a *_feedback target is actually acted on during cleaning.
        readable = sorted(set(node_def.sandbox_config.readable_paths))
        writable = sorted(set(node_def.sandbox_config.writable_paths))
        file_lines: List[str] = []
        if readable:
            file_lines.append(f"Files you can read: {', '.join(readable)}")
        if writable:
            file_lines.append(f"Files you can write: {', '.join(writable)} (reading an existing writable file requires include_line_numbers=True to enable editing via update_lines)")

        system_prompt = node_def.prompt
        if file_lines:
            system_prompt = f"{system_prompt}\n\n" + "\n".join(file_lines)
        prompt = "\n".join(m.text for m in messages)
        if node_def.sandbox_config.step_sections_enabled and node_def.sandbox_config.guide:
            # Step mode (per the impl LLS): the run's user prompt includes the
            # step-mode protocol — the guide arrives through the advance
            # operation (the guide summary at run start, then a step section
            # after each advance that passed verification); call advance after
            # each section.
            step_protocol = (
                "The guide arrives through the advance operation: the guide "
                "summary is provided at run start, then a step section after "
                "each advance that passed verification. Work through each "
                "step's checklist before calling advance again."
            )
            prompt = f"{prompt}\n\n{step_protocol}" if prompt else step_protocol

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
            system_prompt=system_prompt,
            session_start_results=sandbox.get_session_start_reads(),
            logger=logger,
        )

        return self._map_result(agent_result, node_id)

    def is_dirty(self, node_id: NodeId, pending_messages: List[NodeMessage]) -> bool:
        """
        Determine if a node requires cleaning.

        Operation Implemented: dag_clean_logic.is_dirty

        Postconditions:
        - Returns True if the node has pending messages, if a writable output
          file does not exist on disk, or if a writable output file with a
          configured template holds exactly its template's content.
        - When the file-based condition holds, delivers the template-update
          feedback message (pinned to "update target file from template") to
          the node's pending set via the graph's add_messages, at most once
          per pending set (only when the passed pending_messages lacks it), so
          the node remains dirty until a cleaning succeeds.
        """
        node_def = self._graph.resolve_node_definition(node_id)
        config = node_def.sandbox_config

        # The file-based dirty condition: a writable output file missing on
        # disk, or (when a template is configured for it) holding exactly its
        # template's content. writable_paths are virtual names; resolve to the
        # real on-disk location via file_mappings before checking.
        file_dirty = False
        for path in config.writable_paths:
            real_path = config.file_mappings.get(path, path)
            template_content = config.templates.get(path)
            if template_content is not None and template_content.strip() == "":
                continue
            if not os.path.exists(real_path):
                file_dirty = True
                break
            if template_content is not None and template_content.strip() != "":
                try:
                    with open(real_path, "r", encoding="utf-8") as f:
                        if f.read() == template_content:
                            file_dirty = True
                            break
                except OSError:
                    continue  # unreadable file: not a template-state signal

        # The template-update feedback keeps the node in a dirty state until a
        # cleaning succeeds: a failed cleaning leaves it pending (per the
        # dag_clean_logic contract), and a successful cleaning consumes the
        # node's pending messages. Delivered at most once per pending set.
        template_feedback = NodeMessage(
            kind="feedback",
            text="update target file from template",
        )
        if file_dirty and template_feedback not in pending_messages:
            self._graph.add_messages(node_id, [template_feedback])

        return len(pending_messages) > 0 or file_dirty

    def _map_result(
        self,
        result: AgentResult,
        node_id: NodeId,
    ) -> CleanResult:
        """Map the agent run outcome to a CleanResult per the HLS contract.

        There is no free-text final answer: a run either terminates via a
        termination tool (advance/fail/blame) or fails in the loop, so the
        change message is always the sandbox's bounded change summary.
        """
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
