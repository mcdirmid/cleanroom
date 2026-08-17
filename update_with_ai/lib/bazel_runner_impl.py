"""
Bazel runner — assembler for running the cleanroom system.

This module assembles the cleanroom components (graph storage,
agent loop, DAG clean logic) and runs a topological cleaning pass
over a target node and its transitive dependencies.

Library usage:
    from update_with_ai.lib.bazel_runner_impl import BazRunnerImpl
    success, err = BazRunnerImpl().run_dag(root_node, workspace_root)

Script usage (CLI entry point):
    bazel run //pkg:target  # where target is a update_with_ai with clean target
"""

from update_with_ai.lib.dag_impl import DagImpl
from update_with_ai.lib.dag_impl import Config as DagConfig
from update_with_ai.lib.dag import CleaningResult
from update_with_ai.lib.dag_clean_logic import NoChangeResult, FailureResult
from update_with_ai.lib.dag_storage import NodeId
from update_with_ai.lib.bazel_graph_storage_impl import BazelGraphStorageFileImpl
from update_with_ai.lib.bazel_graph_storage import GraphConfig
from update_with_ai.lib.agent_node_clean_logic_impl import (
    AgentNodeCleanLogicImpl,
    Config as CleanLogicConfig,
)
from update_with_ai.lib.agent_loop_impl import AgentLoopImpl
from update_with_ai.lib.agent_loop import AgentLoopConfig, LogEvent
from update_with_ai.lib.bazel_agent_config_impl import BazelAgentConfigImpl
from update_with_ai.lib.sandbox import Sandbox
from update_with_ai.lib.sandbox_impl import SandboxImpl
from update_with_ai.lib.bazel_runner import BazRunner
from typing import Any, Dict, List, Optional
import os
import sys


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

    if event == "final_answer":
        cumulative = data.get("cumulative_usage", {})
        return (
            f"[agent {node}] final answer; cumulative: "
            f"prompt {cumulative.get('prompt_tokens', 0)} | "
            f"completion {cumulative.get('completion_tokens', 0)} | "
            f"total {cumulative.get('total_tokens', 0)} "
            f"({cumulative.get('request_count', 0)} requests)"
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
        content_id = data.get("content_id", "unknown")
        stubbed = data.get("stubbed_message", {})
        replacement = data.get("replacement_message", {})
        stub_preview = str(stubbed.get("content", "")).replace("\n", "\\n")[:80]
        repl_preview = str(replacement.get("content", "")).replace("\n", "\\n")[:80]
        return (
            f"[{node}] message_stubbed: content_id='{content_id}' "
            f"stubbed={stub_preview!r} replacement={repl_preview!r}"
        )

    if event == "tool_called":
        parts = []
        for tc in data.get("tool_calls", []):
            name = tc.get("function", {}).get("name", "unknown")
            args = tc.get("function", {}).get("arguments", "{}")
            parts.append(f"{name}({str(args)[:100]})")
        return f"[{node}] tool_called: {'; '.join(parts)}"

    if event == "tool_result":
        parts = []
        for r in data.get("results", []):
            cid = getattr(r, "content_id", None)
            stub = getattr(r, "stub_previous", False)
            content = str(getattr(r, "content", "")).replace("\n", "\\n")[:80]
            parts.append(f"content_id={cid!r} stub_previous={stub} content={content!r}")
        return f"[{node}] tool_result ({len(parts)}): {'; '.join(parts)}"

    if event == "api_response":
        usage = data.get("usage", {})
        return (
            f"[{node}] api_response: prompt {usage.get('prompt_tokens', 0)} | "
            f"completion {usage.get('completion_tokens', 0)} | "
            f"total {usage.get('total_tokens', 0)}"
        )

    if event == "reminder_injected":
        return f"[{node}] reminder_injected: {data.get('message', '')}"

    if event == "final_answer":
        answer = str(data.get("answer", "")).replace("\n", "\\n")
        preview = answer if len(answer) <= 200 else answer[:200] + "..."
        usage = data.get("usage", {})
        cumulative = data.get("cumulative_usage", {})
        return (
            f"[{node}] final_answer: {preview} | "
            f"request: prompt {usage.get('prompt_tokens', 0)} completion {usage.get('completion_tokens', 0)} | "
            f"cumulative: prompt {cumulative.get('prompt_tokens', 0)} "
            f"completion {cumulative.get('completion_tokens', 0)} "
            f"total {cumulative.get('total_tokens', 0)} "
            f"({cumulative.get('request_count', 0)} requests) "
            f"context {data.get('final_context_size', 0)}"
        )

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


class BazRunnerImpl(BazRunner):
    """
    Assembler for running the cleanroom system.

    Collects the components (graph storage, agent loop, DAG clean logic)
    and runs a topological cleaning pass over a target node and its transitive dependencies.
    """

    def run_dag(
        self,
        root_node: NodeId,
        workspace_root: str,
        config_target: Optional[str] = None,
    ) -> CleaningResult:
        """
        Run a DAG cleaning pass starting from root_node.

        Args:
            root_node: Label of the root node to clean.
            workspace_root: Workspace/runfiles root for loading manifests.
            config_target: Agent/model configuration target (an `agent_config`
                Bazel target label, e.g. "//agent_configs:default"). If None,
                the selection falls back to AGENT_CONFIG_TARGET and then
                //agent_configs:default (see bazel_agent_config).

        Returns a CleaningResult:
            (True, CleanResult)  — all nodes in subgraph cleaned (a
                                   ChangeResult, FeedbackResult, or
                                   NoChangeResult)
            (False, FailureResult) — failure at some node
        """
        print(f"Loading graph from {root_node}...")

        # Step 1: Build the graph storage from manifest files (reads verify
        # fields from manifests); it serves as both the graph and the message
        # store.
        graph = BazelGraphStorageFileImpl(
            config=GraphConfig(workspace_root=workspace_root),
        )

        # Step 2: Configure the agent loop from an agent_config target.
        # The target is selected by priority: the config_target argument
        # (e.g. `--config //pkg:name` on the CLI), then AGENT_CONFIG_TARGET,
        # then the //agent_configs:default convention. The API key is never
        # part of the config target: it is resolved from the environment by
        # the BazelAgentConfig component (the config's pinned API-key
        # environment variable, or AGENT_API_KEY — an unexpected failure,
        # see bazel_agent_config).
        agent_loop = AgentLoopImpl(
            config=BazelAgentConfigImpl().build_agent_loop_config(config_target, workspace_root),
        )

        # Step 3: Agent logging — compact events on stdout, full transcript
        # to a file in the directory where bazel was invoked (override with
        # CLEANROOM_AGENT_LOG, e.g. an absolute path or a name relative to the
        # workspace root).
        log_dir = (
            os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            or os.environ.get("BUILD_WORKING_DIRECTORY")
            or os.getcwd()
        )
        log_override = os.environ.get("CLEANROOM_AGENT_LOG")
        if log_override:
            log_path = log_override if os.path.isabs(log_override) else os.path.join(log_dir, log_override)
        else:
            log_path = os.path.join(log_dir, "agent_loop.log")
        log_file = open(log_path, "w", encoding="utf-8")
        print(f"Agent log: {log_path}")

        def _agent_logger(event: LogEvent, data: Dict[str, Any]) -> None:
            line = _format_compact_log(event, data)
            if line is not None:
                print(line)
            log_file.write(_format_full_log(event, data) + "\n")

        # Step 4: Clean logic with sandbox factory
        clean_logic = AgentNodeCleanLogicImpl(
            config=CleanLogicConfig(
                graph=graph,
                agent_loop_config=AgentLoopConfig(
                    base_url=agent_loop._config.base_url,
                    api_key=agent_loop._config.api_key,
                    model=agent_loop._config.model,
                ),
                make_sandbox=lambda cfg: SandboxImpl(config=cfg),
                make_agent_loop=lambda cfg=None: agent_loop,
                logger=_agent_logger,
            )
        )

        # Step 5: Build the DAG and run
        dag = DagImpl(
            config=DagConfig(
                storage=graph,
                clean_logic=clean_logic,
            )
        )

        print(f"\nRunning DAG from {root_node}...")
        try:
            result = dag.clean_subgraph(root_node)
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
        processes the feedback.

        Args:
            node_id: Label of the node receiving the feedback
            workspace_root: Workspace/runfiles root for loading manifests
            messages: Feedback messages to deliver to the node

        Returns:
            (True, NoChangeResult()) on success,
            (False, FailureResult()) on failure (node does not exist in graph)
        """
        print(f"Loading graph from {node_id}...")
        graph = BazelGraphStorageFileImpl(config=GraphConfig(workspace_root=workspace_root))

        try:
            graph.resolve_package_directory(node_id)
        except ValueError:
            return (False, FailureResult())

        graph.add_messages(node_id, messages)
        for message in messages:
            print(f"Delivered feedback to {node_id}: {message}")
        return (True, NoChangeResult())


def main() -> int:
    """Entry point: parse target from CLI and run."""
    args = sys.argv[1:]
    if len(args) < 1:
        print(f"Usage: {sys.argv[0]} <target> [workspace_root]", file=sys.stderr)
        return 1

    root_node: NodeId = args[0]
    workspace_root: str = args[1] if len(args) > 1 else os.getcwd()

    try:
        runner = BazRunnerImpl()
        success, result = runner.run_dag(root_node, workspace_root)
        return 0 if success else 1
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
