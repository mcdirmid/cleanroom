"""
Tests for lib/agent_node_clean_logic_impl.py (AgentNodeCleanLogicImpl).

Asserts the behavioral contract from specs/agent_node_clean_logic_impl-low.md,
biased to verifying that lib/agent_node_clean_logic_impl.py satisfies it.

BazelGraph, the Sandbox factory, and the AgentLoop factory are mocked. The
agent-loop mock captures the tool executor, so the single-call executor
dispatch (including blame-target dependency validation) can be exercised
directly against the sandbox.
"""

import os
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

from update_with_ai.lib.agent_loop import (
    AgentLoop,
    AgentLoopConfig,
    AgentResult,
    FinalAnswer,
    LoggerCallback,
    ToolDefinition,
    ToolExecutor,
)
from update_with_ai.lib.agent_node_clean_logic_impl import AgentNodeCleanLogicImpl, Config
from update_with_ai.lib.bazel_graph_storage import BazelGraphStorage, NodeDefinition
from update_with_ai.lib.dag_clean_logic import (
    ChangeResult,
    FailureResult,
    FeedbackResult,
    NoChangeResult,
)
from update_with_ai.lib.dag_storage import NodeId, NodeMessage, PendingMessages
from update_with_ai.lib.sandbox import Blame, Sandbox, SandboxConfig
from update_with_ai.lib.tool_provider import (
    TerminateAgentWithFailure,
    TerminateAgentWithSuccess,
    ToolCallOutcome,
    ToolFailure,
    ToolResult,
)


def _agent_loop_config() -> AgentLoopConfig:
    """Default AgentLoopConfig used by the tests."""
    return AgentLoopConfig(
        base_url="http://test",
        api_key="test-key",
        model="test-model",
    )


def _make_node_def(
    prompt: str = "test prompt",
    readable_paths: Optional[List[str]] = None,
    writable_paths: Optional[List[str]] = None,
    file_mappings: Optional[Dict[str, str]] = None,
    blame_targets: Optional[List[str]] = None,
) -> NodeDefinition:
    """Build a NodeDefinition with the given sandbox configuration."""
    return NodeDefinition(
        prompt=prompt,
        sandbox_config=SandboxConfig(
            file_mappings=file_mappings or {},
            readable_paths=readable_paths or [],
            writable_paths=writable_paths or [],
            blame_targets=blame_targets or [],
            read_size_limit=100,
            search_result_limit=10,
        ),
    )


class MockBazelGraphStorage(BazelGraphStorage):
    """Mock BazelGraphStorage backed by in-memory definitions and dependencies.

    Implements the full bazel_graph_storage protocol (dag_storage operations
    plus definition/package-directory resolution). The clean logic consumes
    node definitions (resolve_node_definition) and dependencies
    (get_node_dependencies, for blame-target validation).
    """

    def __init__(
        self,
        definitions: Optional[Dict[NodeId, NodeDefinition]] = None,
        dependencies: Optional[Dict[NodeId, List[NodeId]]] = None,
    ) -> None:
        self._definitions = definitions or {}
        self._dependencies = dependencies or {}
        self._messages: Dict[NodeId, List[NodeMessage]] = {}

    def resolve_node_definition(self, node_id: NodeId) -> NodeDefinition:
        if node_id not in self._definitions:
            raise ValueError(f"Unknown node: {node_id}")
        return self._definitions[node_id]

    def resolve_package_directory(self, node_id: NodeId) -> str:
        return f"pkg/{node_id}"

    def get_node_dependencies(self, node_id: NodeId) -> List[NodeId]:
        return list(self._dependencies.get(node_id, []))

    def get_pending_messages(self, node_id: NodeId) -> PendingMessages:
        return list(self._messages.get(node_id, []))

    def add_messages(self, node_id: NodeId, messages: List[NodeMessage]) -> None:
        self._messages.setdefault(node_id, []).extend(messages)

    def delete_node_data(self, node_id: NodeId) -> None:
        self._messages.pop(node_id, None)

    def get_known_reverse_dependencies(self, node_id: NodeId) -> List[NodeId]:
        return []


class MockSandbox(Sandbox):
    """Mock Sandbox: records each tool call and returns canned outcomes."""

    def __init__(
        self,
        tool_defs: Optional[List[ToolDefinition]] = None,
        write_occurred: bool = False,
        blame_outcome: Optional[ToolCallOutcome] = None,
    ) -> None:
        self._tool_defs = tool_defs if tool_defs is not None else []
        self._write_occurred = write_occurred
        self._blame_outcome = blame_outcome or TerminateAgentWithSuccess(
            FeedbackResult(messages=[("b", "fix it")])
        )
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def _record(self, name: str, arguments: Dict[str, Any]) -> None:
        self.calls.append((name, arguments))

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return self._tool_defs

    def get_write_occurred(self) -> bool:
        return self._write_occurred

    def read_file(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> ToolCallOutcome:
        self._record(
            "read_file",
            {"file_path": file_path, "offset": offset, "limit": limit},
        )
        return ToolResult(
            content="file contents", content_id=file_path, stub_previous=False
        )

    def write_file(self, file_path: str, content: str) -> ToolCallOutcome:
        self._record("write_file", {"file_path": file_path, "content": content})
        self._write_occurred = True
        return ToolResult(content="", content_id=file_path, stub_previous=True)

    def search_files(self, path: str, pattern: str) -> ToolCallOutcome:
        self._record("search_files", {"path": path, "pattern": pattern})
        return ToolResult(content="[]", content_id=path, stub_previous=False)

    def read_chunks(
        self,
        file_path: str,
        chunk_indices: Optional[List[int]] = None,
        include_adjacent: bool = False,
    ) -> ToolCallOutcome:
        self._record(
            "read_chunks",
            {
                "file_path": file_path,
                "chunk_indices": chunk_indices,
                "include_adjacent": include_adjacent,
            },
        )
        return ToolResult(content="chunks", content_id=file_path, stub_previous=False)

    def replace_chunks(
        self,
        file_path: str,
        replacements: List[Dict],
        encoding: Optional[str] = None,
    ) -> ToolCallOutcome:
        self._record(
            "replace_chunks",
            {
                "file_path": file_path,
                "replacements": replacements,
                "encoding": encoding,
            },
        )
        self._write_occurred = True
        return ToolResult(content="", content_id=file_path, stub_previous=True)

    def verify(self) -> ToolCallOutcome:
        self._record("verify", {})
        return ToolResult(content="verified", content_id="verify", stub_previous=True)

    def succeed(self) -> ToolCallOutcome:
        self._record("succeed", {})
        return TerminateAgentWithSuccess(NoChangeResult())

    def fail(self) -> ToolCallOutcome:
        self._record("fail", {})
        return TerminateAgentWithFailure[str]("Task failed")

    def blame(self, blames: List[Blame]) -> ToolCallOutcome:
        self._record("blame", {"blames": blames})
        return self._blame_outcome


class MockAgentLoop(AgentLoop):
    """Mock AgentLoop: records the run and returns a canned AgentResult."""

    def __init__(self, result: Optional[AgentResult] = None) -> None:
        self._result = result
        self.run_count = 0
        self.last_run: Optional[Dict[str, Any]] = None

    def run_agent(
        self,
        prompt: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        logger: Optional[LoggerCallback] = None,
    ) -> AgentResult:
        self.run_count += 1
        self.last_run = {
            "prompt": prompt,
            "tools": tools,
            "tool_executor": tool_executor,
            "logger": logger,
        }
        if self._result is None:
            return FinalAnswer(answer="")
        return self._result


class TestCleanOutcomeMapping(unittest.TestCase):
    """clean() maps each AgentResult variant to the LLS CleanResult."""

    def _impl(
        self,
        sandbox: MockSandbox,
        agent_loop: MockAgentLoop,
        node_def: Optional[NodeDefinition] = None,
    ) -> AgentNodeCleanLogicImpl:
        node_def = node_def or _make_node_def()
        graph = MockBazelGraphStorage(definitions={"a": node_def}, dependencies={"a": []})
        return AgentNodeCleanLogicImpl(
            Config(
                graph=graph,
                agent_loop_config=_agent_loop_config(),
                make_sandbox=lambda sc: sandbox,
                make_agent_loop=lambda cfg: agent_loop,
            )
        )

    def test_final_answer_with_write_occurs_change_result(self):
        """FinalAnswer with write_occurred -> ChangeResult([str(answer)])."""
        sandbox = MockSandbox(write_occurred=True)
        agent_loop = MockAgentLoop(result=FinalAnswer(answer="output"))
        result = self._impl(sandbox, agent_loop).clean("a", ["msg"])
        self.assertIsInstance(result, ChangeResult)
        assert isinstance(result, ChangeResult)
        self.assertEqual(result.type, "change")
        self.assertEqual(result.messages, ["output"])

    def test_final_answer_answer_converted_to_string(self):
        """ChangeResult messages hold str(result.answer) per the LLS."""
        answer: Any = 42  # not a str: exercises the explicit str() conversion
        sandbox = MockSandbox(write_occurred=True)
        agent_loop = MockAgentLoop(result=FinalAnswer(answer=answer))
        result = self._impl(sandbox, agent_loop).clean("a", [])
        self.assertIsInstance(result, ChangeResult)
        assert isinstance(result, ChangeResult)
        self.assertEqual(result.messages, ["42"])

    def test_final_answer_without_write_is_no_change(self):
        """FinalAnswer without write_occurred -> NoChangeResult()."""
        sandbox = MockSandbox(write_occurred=False)
        agent_loop = MockAgentLoop(result=FinalAnswer(answer="output"))
        result = self._impl(sandbox, agent_loop).clean("a", ["msg"])
        self.assertIsInstance(result, NoChangeResult)
        self.assertEqual(result.type, "no_change")

    def test_terminate_success_feedback_result_adopted(self):
        """(TerminateAgentWithSuccess(FeedbackResult), history) is adopted as-is,
        regardless of the sandbox write flag."""
        feedback = FeedbackResult(messages=[("b", "fix it")])
        sandbox = MockSandbox(write_occurred=True)
        agent_loop = MockAgentLoop(
            result=(TerminateAgentWithSuccess(feedback), [{"role": "assistant", "content": "x"}])
        )
        result = self._impl(sandbox, agent_loop).clean("a", [])
        self.assertIs(result, feedback)
        self.assertEqual(result.type, "feedback")

    def test_terminate_success_change_result_adopted(self):
        """(TerminateAgentWithSuccess(ChangeResult), history) is adopted as-is."""
        change = ChangeResult(messages=["changed"])
        sandbox = MockSandbox(write_occurred=True)
        agent_loop = MockAgentLoop(
            result=(TerminateAgentWithSuccess(change), [])
        )
        result = self._impl(sandbox, agent_loop).clean("a", [])
        self.assertIs(result, change)
        self.assertEqual(result.type, "change")

    def test_terminate_success_no_change_result_adopted(self):
        """(TerminateAgentWithSuccess(NoChangeResult), history) is adopted as-is."""
        no_change = NoChangeResult()
        sandbox = MockSandbox(write_occurred=False)
        agent_loop = MockAgentLoop(
            result=(TerminateAgentWithSuccess(no_change), [])
        )
        result = self._impl(sandbox, agent_loop).clean("a", [])
        self.assertIs(result, no_change)
        self.assertEqual(result.type, "no_change")

    def test_terminate_failure_is_failure(self):
        """(TerminateAgentWithFailure, history) -> FailureResult()."""
        sandbox = MockSandbox(write_occurred=True)
        agent_loop = MockAgentLoop(
            result=(TerminateAgentWithFailure[str]("Task failed"), [])
        )
        result = self._impl(sandbox, agent_loop).clean("a", [])
        self.assertIsInstance(result, FailureResult)
        self.assertEqual(result.type, "failure")

    def test_loop_failure_is_failure(self):
        """(error, history) loop failure -> FailureResult()."""
        sandbox = MockSandbox(write_occurred=True)
        agent_loop = MockAgentLoop(result=("api error", []))
        result = self._impl(sandbox, agent_loop).clean("a", [])
        self.assertIsInstance(result, FailureResult)
        self.assertEqual(result.type, "failure")


class TestIsDirty(unittest.TestCase):
    """is_dirty(): pending messages or missing writable files signal dirtiness."""

    def _impl(
        self, node_def: NodeDefinition
    ) -> AgentNodeCleanLogicImpl:
        graph = MockBazelGraphStorage(definitions={"a": node_def}, dependencies={"a": []})
        return AgentNodeCleanLogicImpl(
            Config(
                graph=graph,
                agent_loop_config=_agent_loop_config(),
                make_sandbox=lambda sc: MockSandbox(),
                make_agent_loop=lambda cfg: MockAgentLoop(),
            )
        )

    def test_dirty_when_pending_messages_present(self):
        """Pending messages make the node dirty even when files exist."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.txt")
            with open(out_path, "w") as f:
                f.write("x")
            node_def = _make_node_def(
                writable_paths=["out.txt"],
                file_mappings={"out.txt": out_path},
            )
            impl = self._impl(node_def)
            self.assertTrue(impl.is_dirty("a", ["message"]))
            self.assertFalse(impl.is_dirty("a", []))

    def test_dirty_when_writable_file_missing_on_disk(self):
        """A writable output file missing on disk (resolved via file_mappings)
        makes the node dirty even with no pending messages."""
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = os.path.join(tmp, "missing.txt")
            node_def = _make_node_def(
                writable_paths=["out.txt"],
                file_mappings={"out.txt": missing_path},
            )
            impl = self._impl(node_def)
            self.assertTrue(impl.is_dirty("a", []))
            # Once the file exists on disk, the node is clean without messages.
            with open(missing_path, "w") as f:
                f.write("x")
            self.assertFalse(impl.is_dirty("a", []))


class TestToolExecutor(unittest.TestCase):
    """The ToolExecutor passed to run_agent dispatches by name to the sandbox,
    with blame-target dependency validation first."""

    def _capture_executor(self, node_def: NodeDefinition, sandbox: MockSandbox):
        agent_loop = MockAgentLoop(result=FinalAnswer(answer="done"))
        graph = MockBazelGraphStorage(
            definitions={"a": node_def}, dependencies={"a": ["b"]}
        )
        impl = AgentNodeCleanLogicImpl(
            Config(
                graph=graph,
                agent_loop_config=_agent_loop_config(),
                make_sandbox=lambda sc: sandbox,
                make_agent_loop=lambda cfg: agent_loop,
            )
        )
        impl.clean("a", [])
        assert agent_loop.last_run is not None
        return agent_loop.last_run["tool_executor"]

    def test_blame_invalid_target_is_tool_failure_not_reaching_sandbox(self):
        """A blame target that is not a dependency returns ToolFailure[str]
        without invoking the sandbox's blame tool."""
        node_def = _make_node_def(blame_targets=["b"])
        sandbox = MockSandbox()
        executor = self._capture_executor(node_def, sandbox)
        outcome = executor("blame", {"blames": [("x", "not a dependency")]})
        self.assertIsInstance(outcome, ToolFailure)
        assert isinstance(outcome, ToolFailure)
        # LLS: an invalid blame target returns a tool failure before the
        # sandbox is reached; the message wording is unspecified.
        self.assertEqual(sandbox.calls, [])

    def test_blame_valid_target_passes_through_to_sandbox(self):
        """A blame target that is a dependency reaches the sandbox, and the
        sandbox's outcome is returned unchanged."""
        node_def = _make_node_def(blame_targets=["b"])
        blame_outcome: ToolCallOutcome = TerminateAgentWithSuccess(
            FeedbackResult(messages=[("b", "fix it")])
        )
        sandbox = MockSandbox(blame_outcome=blame_outcome)
        executor = self._capture_executor(node_def, sandbox)
        blames: List[Blame] = [("b", "fix it")]
        outcome = executor("blame", {"blames": blames})
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)
        self.assertIs(outcome, blame_outcome)
        self.assertEqual(sandbox.calls, [("blame", {"blames": blames})])

    def test_dispatches_single_calls_by_name_to_sandbox(self):
        """Non-blame calls dispatch to the sandbox method of the same name."""
        node_def = _make_node_def()
        sandbox = MockSandbox()
        executor = self._capture_executor(node_def, sandbox)
        outcome = executor(
            "read_file", {"file_path": "foo.txt", "offset": 0, "limit": 10}
        )
        self.assertIsInstance(outcome, ToolResult)
        self.assertEqual(
            sandbox.calls,
            [
                (
                    "read_file",
                    {"file_path": "foo.txt", "offset": 0, "limit": 10},
                )
            ],
        )

    def test_unknown_tool_is_tool_failure(self):
        """An unknown tool name is a ToolFailure[str] (per tool_provider)."""
        node_def = _make_node_def()
        sandbox = MockSandbox()
        executor = self._capture_executor(node_def, sandbox)
        outcome = executor("no_such_tool", {})
        self.assertIsInstance(outcome, ToolFailure)
        assert isinstance(outcome, ToolFailure)
        self.assertIn("no_such_tool", outcome.value)
        self.assertEqual(sandbox.calls, [])


class TestRunStructure(unittest.TestCase):
    """Per-run structure: fresh sandbox per clean, one agent run per clean,
    prompt composition, tool definitions, and the optional logger."""

    def test_sandbox_constructed_fresh_per_clean_from_node_config(self):
        """Each clean builds a fresh sandbox from the node's sandbox_config
        (per-run state, including the write flag, is reset)."""
        node_def = _make_node_def()
        graph = MockBazelGraphStorage(definitions={"a": node_def}, dependencies={"a": []})
        constructed: List[Tuple[SandboxConfig, MockSandbox]] = []

        def make_sandbox(sc: SandboxConfig) -> MockSandbox:
            sandbox = MockSandbox()
            constructed.append((sc, sandbox))
            return sandbox

        impl = AgentNodeCleanLogicImpl(
            Config(
                graph=graph,
                agent_loop_config=_agent_loop_config(),
                make_sandbox=make_sandbox,
                make_agent_loop=lambda cfg: MockAgentLoop(result=FinalAnswer(answer="ok")),
            )
        )
        impl.clean("a", [])
        impl.clean("a", ["m"])
        self.assertEqual(len(constructed), 2)
        # Fresh instance per clean (per-run state reset).
        self.assertIsNot(constructed[0][1], constructed[1][1])
        # Constructed from the node's resolved sandbox configuration.
        self.assertIs(constructed[0][0], node_def.sandbox_config)
        self.assertIs(constructed[1][0], node_def.sandbox_config)

    def test_exactly_one_agent_run_per_clean(self):
        """Each cleaning runs exactly one agent run."""
        node_def = _make_node_def()
        graph = MockBazelGraphStorage(definitions={"a": node_def}, dependencies={"a": []})
        loops: List[MockAgentLoop] = []

        def make_agent_loop(cfg: AgentLoopConfig) -> MockAgentLoop:
            loop = MockAgentLoop(result=FinalAnswer(answer="ok"))
            loops.append(loop)
            return loop

        impl = AgentNodeCleanLogicImpl(
            Config(
                graph=graph,
                agent_loop_config=_agent_loop_config(),
                make_sandbox=lambda sc: MockSandbox(),
                make_agent_loop=make_agent_loop,
            )
        )
        impl.clean("a", [])
        impl.clean("a", ["m"])
        self.assertEqual(len(loops), 2)
        self.assertEqual(loops[0].run_count, 1)
        self.assertEqual(loops[1].run_count, 1)

    def test_prompt_names_files_and_feedback_context(self):
        """The prompt is the node prompt augmented with readable/writable file
        lines and the pending messages as feedback from dependents."""
        node_def = _make_node_def(
            prompt="Work on the files",
            readable_paths=["foo.txt", "bar.txt"],
            writable_paths=["bar.txt"],
        )
        graph = MockBazelGraphStorage(definitions={"a": node_def}, dependencies={"a": []})
        agent_loop = MockAgentLoop(result=FinalAnswer(answer="ok"))
        impl = AgentNodeCleanLogicImpl(
            Config(
                graph=graph,
                agent_loop_config=_agent_loop_config(),
                make_sandbox=lambda sc: MockSandbox(),
                make_agent_loop=lambda cfg: agent_loop,
            )
        )
        impl.clean("a", ["fix this", "and this"])
        assert agent_loop.last_run is not None
        prompt = agent_loop.last_run["prompt"]
        self.assertTrue(prompt.startswith("Work on the files"))
        self.assertIn("Files you can read: bar.txt, foo.txt", prompt)
        self.assertIn("Files you can write: bar.txt", prompt)
        self.assertIn("Feedback from dependents:", prompt)
        self.assertIn("- fix this", prompt)
        self.assertIn("- and this", prompt)

    def test_passes_sandbox_tool_definitions_and_executor(self):
        """run_agent receives the sandbox's ToolDefinitions and a callable
        ToolExecutor."""
        tool_defs: List[ToolDefinition] = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "read a file",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        node_def = _make_node_def()
        graph = MockBazelGraphStorage(definitions={"a": node_def}, dependencies={"a": []})
        sandbox = MockSandbox(tool_defs=tool_defs)
        agent_loop = MockAgentLoop(result=FinalAnswer(answer="ok"))
        impl = AgentNodeCleanLogicImpl(
            Config(
                graph=graph,
                agent_loop_config=_agent_loop_config(),
                make_sandbox=lambda sc: sandbox,
                make_agent_loop=lambda cfg: agent_loop,
            )
        )
        impl.clean("a", [])
        assert agent_loop.last_run is not None
        self.assertIs(agent_loop.last_run["tools"], tool_defs)
        self.assertTrue(callable(agent_loop.last_run["tool_executor"]))

    def test_config_logger_forwarded_and_attributed_to_node(self):
        """An optional logger is forwarded to run_agent, wrapped so events are
        attributed to the cleaned node."""
        logged: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: str, data: Dict[str, Any]) -> None:
            logged.append((event, data))

        node_def = _make_node_def()
        graph = MockBazelGraphStorage(definitions={"a": node_def}, dependencies={"a": []})
        sandbox = MockSandbox()
        agent_loop = MockAgentLoop(result=FinalAnswer(answer="ok"))
        impl = AgentNodeCleanLogicImpl(
            Config(
                graph=graph,
                agent_loop_config=_agent_loop_config(),
                make_sandbox=lambda sc: sandbox,
                make_agent_loop=lambda cfg: agent_loop,
                logger=logger,
            )
        )
        impl.clean("a", [])
        assert agent_loop.last_run is not None
        wrapped = agent_loop.last_run["logger"]
        self.assertIsNotNone(wrapped)
        wrapped("api_response", {"usage": {"total_tokens": 10}})
        self.assertEqual(
            logged,
            [("api_response", {"usage": {"total_tokens": 10}, "node_id": "a"})],
        )

    def test_config_without_logger_passes_none(self):
        """Config(logger=None) is accepted; run_agent receives logger=None."""
        node_def = _make_node_def()
        graph = MockBazelGraphStorage(definitions={"a": node_def}, dependencies={"a": []})
        agent_loop = MockAgentLoop(result=FinalAnswer(answer="ok"))
        impl = AgentNodeCleanLogicImpl(
            Config(
                graph=graph,
                agent_loop_config=_agent_loop_config(),
                make_sandbox=lambda sc: MockSandbox(),
                make_agent_loop=lambda cfg: agent_loop,
            )
        )
        impl.clean("a", [])
        assert agent_loop.last_run is not None
        self.assertIsNone(agent_loop.last_run["logger"])


if __name__ == "__main__":
    unittest.main()
