"""
Build runner — interface-only implementation of the build_runner interface.

This module implements the build_runner operations over component factories
supplied at construction: a graph factory, a clean-logic factory, and a DAG
factory. It holds no component instances and creates them per call; the
concrete implementations the factories provide are selected by the assembly
component, never here.

Library usage:
    from testing.lib.build_runner_impl import BuildRunnerImpl
    runner = BuildRunnerImpl(
        graph_factory=..., clean_logic_factory=..., dag_factory=...,
    )
    success, err = runner.run_dag(root_node, workspace_root)
"""

from __future__ import annotations

import os
import signal
import threading
from typing import Any, Callable, Dict, List, Optional, TypeAlias

from .build_runner import BuildRunner
from .dag_storage import NodeId, NodeMessage
from .dag_cleaner import DagCleaner, CleaningResult
from .dag_clean_logic import (
    CleanResult,
    ChangeResult,
    FeedbackResult,
    NoChangeResult,
    FailureResult,
    DagCleanLogic,
)
from .build_graph_storage import BuildGraphStorage, GraphConfig
from .agent_loop import LogEvent, LoggerCallback
from .build_agent_config import ConfigTarget

# The clean-logic factory: constructs the per-run clean logic from the graph,
# the workspace root, the config target, and the run logger. The factory
# (provided by the assembly) resolves the run's agent configuration and
# supplies the per-node agent loop and sandbox; this module never names the
# concrete agent-loop, sandbox, or configuration components.
CleanLogicFactory: TypeAlias = Callable[
    [BuildGraphStorage, str, Optional[ConfigTarget], Optional[LoggerCallback]],
    DagCleanLogic,
]


def _sigint_handler(signum, frame):
    """Honor ctrl-C: raise KeyboardInterrupt so the run's cleanup (the log
    file close, per-run state) completes and the process exits with the
    interruption status — the interrupt is never ignored or continued past."""
    raise KeyboardInterrupt


# Register only from the main thread; signal.signal() raises ValueError if
# called from a worker thread. The explicit handler guarantees SIGINT is
# honored even if a dependency (e.g. a library) sets it to SIG_IGN.
if threading.current_thread() is threading.main_thread():
    signal.signal(signal.SIGINT, _sigint_handler)


def _format_compact_log(event: LogEvent, data: Dict[str, Any]) -> Optional[str]:
    """Format a one-line event summary for stdout; None skips the event."""
    node = data.get("node_id", "?")

    if event == "tool_called":
        names = [tc.get("function", {}).get("name", "unknown") for tc in data.get("tool_calls", [])]
        return f"[agent {node}] tool calls: {', '.join(names)}"

    if event == "api_response":
        usage = data.get("usage", {})
        return (
            f"[agent {node}] tokens: prompt {usage.get('prompt_tokens', 0)} | "
            f"completion {usage.get('completion_tokens', 0)} | "
            f"total {usage.get('total_tokens', 0)}"
        )


    if event == "run_terminated":
        cumulative = data.get("cumulative_usage", {})
        return (
            f"[agent {node}] terminated ({data.get('termination_value', '?')}); cumulative: "
            f"prompt {cumulative.get('prompt_tokens', 0)} | "
            f"completion {cumulative.get('completion_tokens', 0)} | "
            f"total {cumulative.get('total_tokens', 0)} "
            f"({cumulative.get('request_count', 0)} requests)"
        )

    if event == "error":
        return f"[agent {node}] ERROR: {data.get('error', 'unknown error')}"

    return None


def _format_full_log(event: LogEvent, data: Dict[str, Any]) -> str:
    """Format a verbose transcript line for the agent log file."""
    node = data.get("node_id", "?")

    if event == "message_added":
        msg = data.get("message", {})
        role = msg.get("role", "unknown")
        content = msg.get("content")
        if content is not None:
            preview = str(content).replace("\n", "\\n")
            if len(preview) > 200:
                preview = preview[:200] + "..."
            return f"[{node}] message_added ({role}): {preview}"
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            names = [tc.get("function", {}).get("name", "unknown") for tc in tool_calls]
            return f"[{node}] message_added ({role}): tool_calls={', '.join(names)}"
        return f"[{node}] message_added ({role}): (no content)"

    if event == "message_stubbed":
        stubbed = data.get("stubbed_message", {})
        content = str(stubbed.get("content", "")).replace("\n", "\\n")[:80]
        return f"[{node}] message_stubbed: content={content!r}"

    if event == "tool_result":
        parts = []
        for r in data.get("results", []):
            supersedes = getattr(r, "supersedes", False)
            content = str(getattr(r, "content", "")).replace("\n", "\\n")[:80]
            parts.append(f"supersedes={supersedes!r} content={content!r}")
        return f"[{node}] tool_result ({len(parts)}): {'; '.join(parts)}"

    if event == "tool_called":
        parts = []
        for tc in data.get("tool_calls", []):
            name = tc.get("function", {}).get("name", "unknown")
            args = tc.get("function", {}).get("arguments", "{}")
            parts.append(f"{name}({str(args)[:100]})")
        return f"[{node}] tool_called: {'; '.join(parts)}"

    if event == "api_response":
        usage = data.get("usage", {})
        return (
            f"[{node}] api_response: prompt {usage.get('prompt_tokens', 0)} | "
            f"completion {usage.get('completion_tokens', 0)} | "
            f"total {usage.get('total_tokens', 0)}"
        )

    if event == "reminder_injected":
        return f"[{node}] reminder_injected: {data.get('message', '')}"


    if event == "run_terminated":
        cumulative = data.get("cumulative_usage", {})
        return (
            f"[{node}] run_terminated: {data.get('termination_value', '?')} | "
            f"cumulative: prompt {cumulative.get('prompt_tokens', 0)} "
            f"completion {cumulative.get('completion_tokens', 0)} "
            f"total {cumulative.get('total_tokens', 0)} "
            f"({cumulative.get('request_count', 0)} requests) "
            f"context {data.get('final_context_size', 0)}"
        )

    if event == "error":
        return f"[{node}] error: {data.get('error', 'unknown error')}"

    return f"[{node}] {event}: {data}"


class BuildRunnerImpl(BuildRunner):
    """
    Interface-only implementation of the build_runner interface.

    Constructed with the component factories (the graph factory, the
    clean-logic factory, and the DAG factory); the concrete implementations
    the factories provide are selected by the assembly, never here. All
    components are created per call through the factories; no persistent
    state is held across calls.
    """

    def __init__(
        self,
        graph_factory: Callable[[GraphConfig], BuildGraphStorage],
        clean_logic_factory: CleanLogicFactory,
        dag_factory: Callable[[BuildGraphStorage, DagCleanLogic], DagCleaner],
    ) -> None:
        """Configure the runner with the component factories (see the
        implementation LLS; the concrete implementations are the assembly's
        concern)."""
        self._graph_factory = graph_factory
        self._clean_logic_factory = clean_logic_factory
        self._dag_factory = dag_factory

    def _resolve_log_path(self) -> str:
        """Resolve the agent log path: CLEANROOM_AGENT_LOG (absolute, or a
        name relative to the log base directory), else agent_loop.log in the
        log base directory; the base is BUILD_WORKSPACE_DIRECTORY, else
        BUILD_WORKING_DIRECTORY, else the current working directory."""
        log_dir = (
            os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            or os.environ.get("BUILD_WORKING_DIRECTORY")
            or os.getcwd()
        )
        log_override = os.environ.get("CLEANROOM_AGENT_LOG")
        if log_override:
            if os.path.isabs(log_override):
                return log_override
            return os.path.join(log_dir, log_override)
        return os.path.join(log_dir, "agent_loop.log")

    def run_dag(
        self,
        root_node: NodeId,
        workspace_root: str,
        config_target: Optional[str] = None,
    ) -> CleaningResult:
        """
        Run a DAG cleaning pass starting from root_node.

        The graph and message store come from the graph factory; the clean
        logic comes from the clean-logic factory (which resolves the run's
        agent configuration from the config target and supplies the per-node
        agent loop and sandbox); the DAG comes from the DAG factory over the
        graph and the clean logic. The log file is always written and closed,
        regardless of the result.

        Args:
            root_node: Label of the root node to clean.
            workspace_root: Workspace/runfiles root for loading manifests.
            config_target: Agent/model configuration target (an `agent_config`
                Bazel target label, e.g. "//agent_configs:default"). If None,
                the selection falls back to AGENT_CONFIG_TARGET and then
                //agent_configs:default (resolved by the clean-logic factory).

        Returns a CleaningResult:
            (True, CleanResult)  — all nodes in subgraph cleaned (a
                                   ChangeResult, FeedbackResult, or
                                   NoChangeResult)
            (False, FailureResult) — failure at some node
        """
        print(f"Loading graph from {root_node}...")

        # Step 1: Build the graph storage from manifest files (it serves as
        # both the graph and the message store) through the graph factory.
        graph = self._graph_factory(GraphConfig(workspace_root=workspace_root))

        # Step 2: Agent logging — compact events on stdout, full transcript
        # to a file in the directory where bazel was invoked (override with
        # CLEANROOM_AGENT_LOG, e.g. an absolute path or a name relative to the
        # workspace root). The log file is created after graph construction:
        # a failure during assembly (e.g. graph construction) propagates
        # without a log file.
        log_path = self._resolve_log_path()
        log_file = open(log_path, "w", encoding="utf-8")
        print(f"Agent log: {log_path}")

        def _agent_logger(event: LogEvent, data: Dict[str, Any]) -> None:
            line = _format_compact_log(event, data)
            if line is not None:
                print(line)
            log_file.write(_format_full_log(event, data) + "\n")
            # Flush each line immediately so the transcript reflects the run
            # in real time (specs/low/build_runner_impl.md: log writes are
            # unbuffered).
            log_file.flush()

        # Step 3: Clean logic through the clean-logic factory: the factory
        # resolves the run's agent configuration (config target argument,
        # then AGENT_CONFIG_TARGET, then //agent_configs:default) with the
        # API key resolved from the environment, and supplies the per-node
        # agent loop and sandbox (configuration failures are unexpected
        # failures signaled by the build_agent_config component before the
        # cleaning pass starts).
        clean_logic = self._clean_logic_factory(
            graph, workspace_root, config_target, _agent_logger
        )

        # Step 4: Build the DAG through the DAG factory and run.
        dag_cleaner = self._dag_factory(graph, clean_logic)

        print(f"\nRunning DAG from {root_node}...")
        try:
            result = dag_cleaner.clean_subgraph(root_node)
        finally:
            log_file.close()
        print(f"Full agent transcript: {log_path}")
        print(f"DAG result: {result}")
        return result

    def inject_feedback(
        self,
        node_id: NodeId,
        workspace_root: str,
        messages: List[str],
    ) -> CleaningResult:
        """
        Deliver feedback messages to a node's own pending message store.

        Each message is added to the node's pending messages (the same store
        the DAG reads), so a subsequent clean treats the node as dirty and
        processes the feedback. A fresh graph is constructed through the
        graph factory for this call, separate from the one used by run_dag.

        Returns:
            (True, NoChangeResult()) on success,
            (False, FailureResult()) on failure (node does not exist in graph)
        """
        print(f"Loading graph from {node_id}...")
        graph = self._graph_factory(GraphConfig(workspace_root=workspace_root))

        try:
            graph.resolve_package_directory(node_id)
        except ValueError:
            return (False, FailureResult())

        graph.add_messages(
            node_id,
            [NodeMessage(kind="feedback", text=m) for m in messages],
        )
        for message in messages:
            print(f"Delivered feedback to {node_id}: {message}")
        return (True, NoChangeResult())

    def add_change(
        self,
        node_id: NodeId,
        workspace_root: str,
        change: str = "check",
    ) -> CleaningResult:
        """
        Deliver a change message to a node's own pending message store,
        marking the node dirty for a subsequent cleaning pass. The node may
        succeed without changing when cleaned; the change text defaults to
        "check" when not provided. A fresh graph is constructed through the
        graph factory for this call.

        Returns:
            (True, NoChangeResult()) on success,
            (False, FailureResult()) on failure (node does not exist in graph)
        """
        print(f"Loading graph from {node_id}...")
        graph = self._graph_factory(GraphConfig(workspace_root=workspace_root))

        try:
            graph.resolve_package_directory(node_id)
        except ValueError:
            return (False, FailureResult())

        graph.add_messages(node_id, [NodeMessage(kind="change", text=change)])
        print(f"Delivered change to {node_id}: {change}")
        return (True, NoChangeResult())

    def broadcast_change(
        self,
        node_id: NodeId,
        workspace_root: str,
        change: str,
    ) -> CleaningResult:
        """
        Pretend the node was cleaned with changes: broadcast a change message
        to the node's known reverse dependencies and clear the node's data,
        without cleaning the node.

        The broadcast message is the node's declared source file name (its
        sandbox configuration's first writable path) followed by the change
        text; when the node declares no source file, the message is the
        change text alone. A known reverse dependency that is not in the
        graph is skipped (per the dag_cleaner routing rule). A fresh graph is
        constructed through the graph factory for this call.

        Returns:
            (True, NoChangeResult()) on success,
            (False, FailureResult()) on failure (node does not exist in graph)
        """
        print(f"Loading graph from {node_id}...")
        graph = self._graph_factory(GraphConfig(workspace_root=workspace_root))

        try:
            graph.resolve_package_directory(node_id)
        except ValueError:
            return (False, FailureResult())

        writable = graph.resolve_node_definition(node_id).sandbox_config.writable_paths
        src = writable[0] if writable else ""
        message_text = "{}: {}".format(src, change) if src else change
        broadcast = [NodeMessage(kind="change", text=message_text)]
        for target in graph.get_known_reverse_dependencies(node_id):
            try:
                graph.add_messages(target, broadcast)
            except ValueError:
                continue
        graph.delete_node_data(node_id)
        print(
            f"Broadcast change from {node_id} to its reverse dependencies: "
            f"{message_text}"
        )
        return (True, NoChangeResult())
