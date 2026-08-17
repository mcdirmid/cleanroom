"""
Tests for the SandboxImpl implementation.

Rewritten to match the current implementation and the low-level spec
(specs/sandbox_impl-low.md, specs/sandbox-low.md, specs/tool_provider-low.md,
specs/dag_clean_logic-low.md).

The current API returns a single ToolCallOutcome per tool call: a ToolResult
or a Signal (ToolFailure, TerminateAgentWithSuccess, TerminateAgentWithFailure).
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, List, Optional, Tuple

from update_with_ai.lib.sandbox import SandboxConfig
from update_with_ai.lib.sandbox_impl import SandboxImpl, STUB_REPLACEMENT
from update_with_ai.lib.tool_provider import (
    ToolResult,
    ToolFailure,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
)
from update_with_ai.lib.dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult


class TestSandboxImpl(unittest.TestCase):
    """Main coverage: tools, policy enforcement, stubbing semantics, state."""

    def setUp(self) -> None:
        """Set up a temp workspace with text, python, multi-chunk and empty files."""
        self.temp_dir = tempfile.mkdtemp()

        # Plain text file (81 bytes).
        self.test_file_path = os.path.join(self.temp_dir, "test.txt")
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Line 1: Hello World\n")
            f.write("Line 2: This is a test\n")
            f.write("Line 3: Another line\n")
            f.write("Line 4: Final line\n")

        # Single-chunk python file.
        self.python_file_path = os.path.join(self.temp_dir, "test.py")
        with open(self.python_file_path, "w", encoding="utf-8") as f:
            f.write("class TestClass:\n")
            f.write("    def method_one(self):\n")
            f.write("        return 'one'\n")
            f.write("    def method_two(self):\n")
            f.write("        return 'two'\n")

        # Multi-chunk python file (top-level imports, class, function).
        self.multi_file_path = os.path.join(self.temp_dir, "multi.py")
        with open(self.multi_file_path, "w", encoding="utf-8") as f:
            f.write("import os\n")
            f.write("import sys\n\n")
            f.write("class A:\n")
            f.write("    def __init__(self):\n")
            f.write("        pass\n\n")
            f.write("def func():\n")
            f.write("    return 1\n")

        # Empty python file.
        self.empty_py_path = os.path.join(self.temp_dir, "empty.py")
        with open(self.empty_py_path, "w", encoding="utf-8") as f:
            pass

        self.file_mappings = {
            "test.txt": self.test_file_path,
            "test.py": self.python_file_path,
            "multi.py": self.multi_file_path,
            "empty.py": self.empty_py_path,
        }
        self.readable_paths = ["test.txt", "test.py", "multi.py", "empty.py"]
        self.writable_paths = ["test.txt", "test.py", "multi.py", "empty.py"]
        self.blame_targets = ["agent", "system"]

        self.config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        self.sandbox = SandboxImpl(self.config)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    # ------------------------------------------------------------------
    # Outcome narrowing helpers
    # ------------------------------------------------------------------

    def as_tool_result(self, outcome: Any) -> ToolResult:
        assert isinstance(outcome, ToolResult), f"Expected ToolResult, got {outcome!r}"
        return outcome

    def as_tool_failure(self, outcome: Any) -> ToolFailure:
        assert isinstance(outcome, ToolFailure), f"Expected ToolFailure, got {outcome!r}"
        return outcome

    def as_success(self, outcome: Any) -> TerminateAgentWithSuccess:
        assert isinstance(outcome, TerminateAgentWithSuccess), (
            f"Expected TerminateAgentWithSuccess, got {outcome!r}"
        )
        return outcome

    def as_terminate_failure(self, outcome: Any) -> TerminateAgentWithFailure[Any]:
        assert isinstance(outcome, TerminateAgentWithFailure), (
            f"Expected TerminateAgentWithFailure, got {outcome!r}"
        )
        return outcome

    # ------------------------------------------------------------------
    # get_tool_definitions
    # ------------------------------------------------------------------

    def test_get_tool_definitions_always_includes_core_tools(self) -> None:
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        for expected in ("read_file", "write_file", "search_files", "succeed", "fail"):
            self.assertIn(expected, names)

    def test_get_tool_definitions_follow_json_schema_shape(self) -> None:
        for definition in self.sandbox.get_tool_definitions():
            self.assertEqual(definition["type"], "function")
            self.assertIn("name", definition["function"])
            self.assertIn("description", definition["function"])
            self.assertIn("parameters", definition["function"])

    def test_get_tool_definitions_chunk_tools_when_python_accessible(self) -> None:
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        self.assertIn("read_chunks", names)
        self.assertIn("replace_chunks", names)

    def test_get_tool_definitions_no_chunk_tools_without_readable_python(self) -> None:
        # test.py is mapped but not readable -> no Python files are accessible.
        config = SandboxConfig(
            file_mappings={"test.py": self.python_file_path, "test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        names = [d["function"]["name"] for d in SandboxImpl(config).get_tool_definitions()]
        self.assertNotIn("read_chunks", names)
        self.assertNotIn("replace_chunks", names)

    def test_get_tool_definitions_no_chunk_tools_without_python_mappings(self) -> None:
        config = SandboxConfig(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        names = [d["function"]["name"] for d in SandboxImpl(config).get_tool_definitions()]
        self.assertNotIn("read_chunks", names)
        self.assertNotIn("replace_chunks", names)

    def test_get_tool_definitions_verify_conditional(self) -> None:
        # No callback -> verify not offered.
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        self.assertNotIn("verify", names)

        def callback() -> str:
            return "ok"

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=callback,
        )
        names = [d["function"]["name"] for d in SandboxImpl(config).get_tool_definitions()]
        self.assertIn("verify", names)

    def test_get_tool_definitions_blame_conditional(self) -> None:
        # Non-empty blame targets -> blame offered.
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        self.assertIn("blame", names)
        blame_def = next(d for d in self.sandbox.get_tool_definitions()
                         if d["function"]["name"] == "blame")
        properties = blame_def["function"]["parameters"]["properties"]
        self.assertIn("blames", properties)
        self.assertIn("target", properties["blames"]["items"]["properties"])
        self.assertIn("feedback", properties["blames"]["items"]["properties"])

        # Empty blame targets -> blame not offered.
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        names = [d["function"]["name"] for d in SandboxImpl(config).get_tool_definitions()]
        self.assertNotIn("blame", names)

    # ------------------------------------------------------------------
    # read_file
    # ------------------------------------------------------------------

    def test_read_file_success(self) -> None:
        result = self.as_tool_result(self.sandbox.read_file("test.txt"))
        self.assertEqual(result.content_id, "test.txt")
        self.assertFalse(result.stub_previous)
        self.assertEqual(result.type, "tool_result")
        self.assertIn("Line 1: Hello World", result.content)

    def test_read_file_default_limit_is_read_size_limit(self) -> None:
        result = self.as_tool_result(self.sandbox.read_file("test.txt"))
        # "Line 1: Hello World\n" is exactly 20 bytes -> the read_size_limit.
        self.assertEqual(result.content, "Line 1: Hello World\n")
        self.assertEqual(len(result.content), 20)

    def test_read_file_offset_and_limit(self) -> None:
        result = self.as_tool_result(self.sandbox.read_file("test.txt", offset=0, limit=10))
        self.assertEqual(result.content, "Line 1: He")
        result2 = self.as_tool_result(self.sandbox.read_file("test.txt", offset=10, limit=10))
        self.assertEqual(result2.content, "llo World\n")

    def test_read_file_explicit_limit_overrides_read_size_limit(self) -> None:
        result = self.as_tool_result(self.sandbox.read_file("test.txt", limit=40))
        self.assertEqual(len(result.content), 40)

    def test_read_file_policy_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_file("unknown.txt"))
        # LLS: policy violations signal a tool failure naming the virtual path.
        self.assertIn("unknown.txt", failure.value)

    def test_read_file_policy_not_readable(self) -> None:
        # Map a path that is not readable.
        config = SandboxConfig(
            file_mappings={"secret.txt": self.test_file_path, "test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).read_file("secret.txt"))
        self.assertIn("secret.txt", failure.value)

    def test_read_file_negative_offset(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_file("test.txt", offset=-1))

    def test_read_file_zero_limit(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_file("test.txt", limit=0))

    def test_read_file_region_overlap_stubs(self) -> None:
        first = self.as_tool_result(self.sandbox.read_file("test.txt", offset=0, limit=10))
        self.assertFalse(first.stub_previous)
        self.assertEqual(first.content, "Line 1: He")

        # Overlapping region -> stubbed with replacement text.
        second = self.as_tool_result(self.sandbox.read_file("test.txt", offset=5, limit=10))
        self.assertTrue(second.stub_previous)
        self.assertEqual(second.content, "Content removed because newer version is available")
        self.assertEqual(STUB_REPLACEMENT, "Content removed because newer version is available")

    def test_read_file_non_overlapping_regions_not_stubbed(self) -> None:
        self.as_tool_result(self.sandbox.read_file("test.txt", offset=0, limit=10))
        second = self.as_tool_result(self.sandbox.read_file("test.txt", offset=20, limit=10))
        self.assertFalse(second.stub_previous)
        self.assertNotIn("Content removed", second.content)

    def test_read_file_only_previous_non_stubbed_regions_count(self) -> None:
        # (0,10) recorded; (5,15) overlaps -> stubbed and NOT recorded;
        # (12,22) does not overlap the recorded (0,10) -> not stubbed.
        self.as_tool_result(self.sandbox.read_file("test.txt", offset=0, limit=10))
        self.as_tool_result(self.sandbox.read_file("test.txt", offset=5, limit=10))
        third = self.as_tool_result(self.sandbox.read_file("test.txt", offset=12, limit=10))
        self.assertFalse(third.stub_previous)

    def test_read_file_truncated_region_ends_at_returned_content(self) -> None:
        # 10-byte file: "0123456789"
        short_path = os.path.join(self.temp_dir, "short.txt")
        with open(short_path, "w", encoding="utf-8") as f:
            f.write("0123456789")
        config = SandboxConfig(
            file_mappings={"short.txt": short_path},
            readable_paths=["short.txt"],
            writable_paths=["short.txt"],
            blame_targets=[],
            read_size_limit=100,
            search_result_limit=5,
            verification_callback=None,
        )
        sandbox = SandboxImpl(config)

        # Read offset 5 limit 100: only 5 bytes returned -> region (5,10).
        first = self.as_tool_result(sandbox.read_file("short.txt", offset=5, limit=100))
        self.assertFalse(first.stub_previous)
        self.assertEqual(first.content, "56789")

        # Read at EOF returns nothing; region is (10,10), which shares no byte
        # with (5,10). If the region were recorded using the requested limit,
        # this would overlap and be stubbed.
        second = self.as_tool_result(sandbox.read_file("short.txt", offset=10, limit=5))
        self.assertFalse(second.stub_previous)
        self.assertEqual(second.content, "")

        # Read overlapping the truncated region -> stubbed.
        third = self.as_tool_result(sandbox.read_file("short.txt", offset=8, limit=10))
        self.assertTrue(third.stub_previous)

    # ------------------------------------------------------------------
    # write_file
    # ------------------------------------------------------------------

    def test_write_file_success(self) -> None:
        result = self.as_tool_result(self.sandbox.write_file("test.txt", "New content"))
        self.assertTrue(result.stub_previous)
        self.assertEqual(result.content_id, "test.txt")
        self.assertTrue(self.sandbox.get_write_occurred())
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "New content")

    def test_write_file_empty_content_rejected(self) -> None:
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            original = f.read()
        failure = self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        self.assertFalse(self.sandbox.get_write_occurred())
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), original)

    def test_write_file_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self.sandbox.write_file("unknown.txt", "content"))
        self.assertIn("unknown.txt", failure.value)

    def test_write_file_not_writable(self) -> None:
        config = SandboxConfig(
            file_mappings={"test.py": self.python_file_path, "test.txt": self.test_file_path},
            readable_paths=["test.txt", "test.py"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).write_file("test.py", "content"))
        self.assertIn("test.py", failure.value)

    def test_write_file_clears_read_region_state(self) -> None:
        self.as_tool_result(self.sandbox.read_file("test.txt", offset=0, limit=10))
        self.as_tool_result(self.sandbox.write_file("test.txt", "brand new"))
        # Stubbing state was cleared -> same region is not stubbed.
        after = self.as_tool_result(self.sandbox.read_file("test.txt", offset=0, limit=10))
        self.assertFalse(after.stub_previous)

    def test_write_file_clears_search_dedup_state(self) -> None:
        self.as_tool_result(self.sandbox.search_files("test.txt", "Hello"))
        self.as_tool_result(self.sandbox.write_file("test.txt", "no matches here"))
        after = self.as_tool_result(self.sandbox.search_files("test.txt", "Hello"))
        self.assertFalse(after.stub_previous)

    def test_write_file_clears_chunk_state(self) -> None:
        self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.as_tool_result(self.sandbox.write_file("test.py", "x = 1\n"))
        after = self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.assertFalse(after.stub_previous)

    def test_write_file_creates_missing_directories(self) -> None:
        nested = os.path.join(self.temp_dir, "nested", "sub", "file.txt")
        config = SandboxConfig(
            file_mappings={"nested.txt": nested},
            readable_paths=["nested.txt"],
            writable_paths=["nested.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        sandbox = SandboxImpl(config)
        result = self.as_tool_result(sandbox.write_file("nested.txt", "Nested content"))
        self.assertTrue(result.stub_previous)
        self.assertTrue(os.path.exists(nested))
        with open(nested, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Nested content")

    # ------------------------------------------------------------------
    # search_files
    # ------------------------------------------------------------------

    def test_search_files_success(self) -> None:
        result = self.as_tool_result(self.sandbox.search_files("test.txt", "Hello"))
        self.assertEqual(result.content_id, "test.txt")
        self.assertFalse(result.stub_previous)
        self.assertIn("Hello", result.content)
        self.assertIn("1:", result.content)

    def test_search_files_dedup_by_path_and_pattern(self) -> None:
        first = self.as_tool_result(self.sandbox.search_files("test.txt", "test"))
        self.assertFalse(first.stub_previous)
        second = self.as_tool_result(self.sandbox.search_files("test.txt", "test"))
        self.assertTrue(second.stub_previous)
        self.assertEqual(second.content, "Content removed because newer version is available")

    def test_search_files_different_pattern_not_stubbed(self) -> None:
        self.as_tool_result(self.sandbox.search_files("test.txt", "Hello"))
        second = self.as_tool_result(self.sandbox.search_files("test.txt", "World"))
        self.assertFalse(second.stub_previous)

    def test_search_files_different_path_not_stubbed(self) -> None:
        self.as_tool_result(self.sandbox.search_files("test.txt", "test"))
        second = self.as_tool_result(self.sandbox.search_files("test.py", "Test"))
        self.assertFalse(second.stub_previous)

    def test_search_files_invalid_pattern(self) -> None:
        failure = self.as_tool_failure(self.sandbox.search_files("test.txt", "[invalid"))

    def test_search_files_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self.sandbox.search_files("unknown.txt", "x"))
        self.assertIn("unknown.txt", failure.value)

    def test_search_files_not_readable(self) -> None:
        config = SandboxConfig(
            file_mappings={"secret.txt": self.test_file_path, "test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).search_files("secret.txt", "x"))
        self.assertIn("secret.txt", failure.value)

    def test_search_files_recursive_in_directory(self) -> None:
        src_dir = os.path.join(self.temp_dir, "src")
        os.makedirs(os.path.join(src_dir, "sub"))
        with open(os.path.join(src_dir, "a.py"), "w", encoding="utf-8") as f:
            f.write("needle here\n")
        with open(os.path.join(src_dir, "sub", "b.txt"), "w", encoding="utf-8") as f:
            f.write("another needle\n")
        config = SandboxConfig(
            file_mappings={"src": src_dir},
            readable_paths=["src"],
            writable_paths=[],
            blame_targets=[],
            read_size_limit=100,
            search_result_limit=5,
            verification_callback=None,
        )
        result = self.as_tool_result(SandboxImpl(config).search_files("src", "needle"))
        self.assertIn("a.py:1:", result.content)
        self.assertIn("sub/b.txt:1:", result.content)

    def test_search_files_result_limit(self) -> None:
        many_path = os.path.join(self.temp_dir, "many.txt")
        with open(many_path, "w", encoding="utf-8") as f:
            for i in range(20):
                f.write(f"Match {i}\n")
        config = SandboxConfig(
            file_mappings={"many.txt": many_path},
            readable_paths=["many.txt"],
            writable_paths=[],
            blame_targets=[],
            read_size_limit=100,
            search_result_limit=5,
            verification_callback=None,
        )
        result = self.as_tool_result(SandboxImpl(config).search_files("many.txt", "Match"))
        lines = [line for line in result.content.split("\n") if line.strip()]
        # LLS: results are limited to search_result_limit entries and contain
        # the search results; the exact result-line format is unspecified.
        self.assertEqual(len(lines), 5)
        for line in lines:
            self.assertIn("Match", line)

    # ------------------------------------------------------------------
    # read_chunks
    # ------------------------------------------------------------------

    def test_read_chunks_none_returns_all_chunks(self) -> None:
        result = self.as_tool_result(self.sandbox.read_chunks("test.py"))
        self.assertEqual(result.content_id, "test.py")
        self.assertFalse(result.stub_previous)
        self.assertIn("class TestClass", result.content)
        self.assertIn("def method_one", result.content)

    def test_read_chunks_specific_indices(self) -> None:
        result = self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.assertIn("class TestClass", result.content)

    def test_read_chunks_include_adjacent(self) -> None:
        # Request chunk 1 with adjacent context: returned = requested + adjacent.
        result = self.as_tool_result(
            self.sandbox.read_chunks("multi.py", chunk_indices=[1], include_adjacent=True)
        )
        # Chunks 0, 1 and 2 are all returned (the content is the LLS contract;
        # the "--- Chunk N ---" header format is unspecified).
        self.assertIn("import os", result.content)
        self.assertIn("class A:", result.content)

    def test_read_chunks_non_python_file_rejected(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_chunks("test.txt"))
        self.assertIn("test.txt", failure.value)

    def test_read_chunks_negative_index_rejected(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_chunks("test.py", chunk_indices=[-1]))

    def test_read_chunks_out_of_range_index_rejected(self) -> None:
        # Per the sandbox LLS, requested chunk indices must be valid
        # non-negative indices; an out-of-range index is a parameter error
        # (it is not silently dropped).
        failure = self.as_tool_failure(self.sandbox.read_chunks("test.py", chunk_indices=[999]))

    def test_read_chunks_not_accessible(self) -> None:
        config = SandboxConfig(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).read_chunks("test.txt"))

    def test_read_chunks_not_readable(self) -> None:
        # a.py readable (python accessible), b.py mapped but not readable.
        a_path = os.path.join(self.temp_dir, "a.py")
        b_path = os.path.join(self.temp_dir, "b.py")
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        with open(b_path, "w", encoding="utf-8") as f:
            f.write("y = 2\n")
        config = SandboxConfig(
            file_mappings={"a.py": a_path, "b.py": b_path},
            readable_paths=["a.py"],
            writable_paths=["a.py"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).read_chunks("b.py"))
        self.assertIn("b.py", failure.value)

    def test_read_chunks_overlapping_indices_stub(self) -> None:
        first = self.as_tool_result(self.sandbox.read_chunks("multi.py", chunk_indices=[0]))
        self.assertFalse(first.stub_previous)
        second = self.as_tool_result(
            self.sandbox.read_chunks("multi.py", chunk_indices=[0, 1])
        )
        self.assertTrue(second.stub_previous)
        self.assertEqual(second.content, "Content removed because newer version is available")

    def test_read_chunks_disjoint_indices_not_stubbed(self) -> None:
        first = self.as_tool_result(self.sandbox.read_chunks("multi.py", chunk_indices=[0]))
        self.assertFalse(first.stub_previous)
        second = self.as_tool_result(self.sandbox.read_chunks("multi.py", chunk_indices=[3]))
        self.assertFalse(second.stub_previous)

    def test_read_chunks_adjacent_context_counts_for_stubbing(self) -> None:
        # include_adjacent makes chunks 0,1,2 the returned set; a later read of
        # chunk 2 overlaps that set -> stubbed.
        self.as_tool_result(
            self.sandbox.read_chunks("multi.py", chunk_indices=[1], include_adjacent=True)
        )
        later = self.as_tool_result(self.sandbox.read_chunks("multi.py", chunk_indices=[2]))
        self.assertTrue(later.stub_previous)

        # Without adjacent context, chunk 1 alone does not pre-cover chunk 2.
        # Use a fresh sandbox so state from the adjacent read above does not
        # leak into this assertion.
        fresh = SandboxImpl(self.config)
        self.as_tool_result(fresh.read_chunks("multi.py", chunk_indices=[1]))
        later2 = self.as_tool_result(fresh.read_chunks("multi.py", chunk_indices=[2]))
        self.assertFalse(later2.stub_previous)

    def test_read_chunks_empty_file(self) -> None:
        result = self.as_tool_result(self.sandbox.read_chunks("empty.py"))
        self.assertEqual(result.content, "")
        self.assertFalse(result.stub_previous)

    # ------------------------------------------------------------------
    # replace_chunks
    # ------------------------------------------------------------------

    def test_replace_chunks_success(self) -> None:
        result = self.as_tool_result(
            self.sandbox.replace_chunks("test.py", [{"index": 0, "new_content": "class NewClass:"}])
        )
        self.assertTrue(result.stub_previous)
        self.assertEqual(result.content_id, "test.py")
        self.assertTrue(self.sandbox.get_write_occurred())
        with open(self.python_file_path, "r", encoding="utf-8") as f:
            self.assertIn("class NewClass:", f.read())

    def test_replace_chunks_atomic_all_or_nothing(self) -> None:
        with open(self.python_file_path, "r", encoding="utf-8") as f:
            original = f.read()
        replacements = [
            {"index": 0, "new_content": "class NewClass:"},
            {"index": 99, "new_content": "out of range"},
        ]
        failure = self.as_tool_failure(self.sandbox.replace_chunks("test.py", replacements))
        # Nothing was applied and no write occurred.
        with open(self.python_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), original)
        self.assertFalse(self.sandbox.get_write_occurred())

    def test_replace_chunks_empty_replacements_rejected(self) -> None:
        failure = self.as_tool_failure(self.sandbox.replace_chunks("test.py", []))

    def test_replace_chunks_missing_key_rejected(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": 0}])
        )

    def test_replace_chunks_non_integer_index_rejected(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": "0", "new_content": "x"}])
        )

    def test_replace_chunks_negative_index_rejected(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": -1, "new_content": "x"}])
        )

    def test_replace_chunks_non_python_file_rejected(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.replace_chunks("test.txt", [{"index": 0, "new_content": "x"}])
        )
        self.assertIn("test.txt", failure.value)

    def test_replace_chunks_not_writable(self) -> None:
        config = SandboxConfig(
            file_mappings={"a.py": self.python_file_path, "test.txt": self.test_file_path},
            readable_paths=["a.py", "test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(
            SandboxImpl(config).replace_chunks("a.py", [{"index": 0, "new_content": "x"}])
        )
        self.assertIn("a.py", failure.value)

    def test_replace_chunks_clears_stubbing_state(self) -> None:
        self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.as_tool_result(
            self.sandbox.replace_chunks("test.py", [{"index": 0, "new_content": "class NewClass:"}])
        )
        after = self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.assertFalse(after.stub_previous)

    # ------------------------------------------------------------------
    # verify
    # ------------------------------------------------------------------

    def test_verify_null_callback_returns_tool_failure(self) -> None:
        failure = self.as_tool_failure(self.sandbox.verify())

    def test_verify_success(self) -> None:
        def callback() -> str:
            return "Verification passed"

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=callback,
        )
        result = self.as_tool_result(SandboxImpl(config).verify())
        self.assertEqual(result.content, "Verification passed")
        self.assertEqual(result.content_id, "verify")
        self.assertTrue(result.stub_previous)

    def test_verify_callback_exception(self) -> None:
        def callback() -> str:
            raise ValueError("boom")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=callback,
        )
        failure = self.as_tool_failure(SandboxImpl(config).verify())
        # LLS (implementation spec): verification-callback exceptions signal a
        # tool failure; the exact wording is unspecified.

    # ------------------------------------------------------------------
    # succeed / fail
    # ------------------------------------------------------------------

    def test_succeed_no_change_when_no_write(self) -> None:
        success = self.as_success(self.sandbox.succeed())
        self.assertEqual(success.type, "terminate_success")
        self.assertIsInstance(success.value, NoChangeResult)
        assert isinstance(success.value, NoChangeResult)
        self.assertEqual(success.value.type, "no_change")

    def test_succeed_change_result_when_write_occurred(self) -> None:
        self.as_tool_result(self.sandbox.write_file("test.txt", "updated"))
        success = self.as_success(self.sandbox.succeed())
        self.assertIsInstance(success.value, ChangeResult)
        assert isinstance(success.value, ChangeResult)
        self.assertEqual(success.value.type, "change")
        self.assertEqual(success.value.messages, ["Task completed successfully"])

    def test_succeed_after_failed_write_is_no_change(self) -> None:
        self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        success = self.as_success(self.sandbox.succeed())
        self.assertIsInstance(success.value, NoChangeResult)

    def test_fail(self) -> None:
        failure = self.as_terminate_failure(self.sandbox.fail())
        self.assertEqual(failure.type, "terminate_failure")
        # LLS: the failure termination carries a str value describing the
        # failure; the exact wording is unspecified.
        self.assertIsInstance(failure.value, str)

    # ------------------------------------------------------------------
    # blame
    # ------------------------------------------------------------------

    def test_blame_no_targets_configured(self) -> None:
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).blame([("agent", "fix")]))

    def test_blame_empty_list(self) -> None:
        failure = self.as_tool_failure(self.sandbox.blame([]))

    def test_blame_invalid_target(self) -> None:
        failure = self.as_tool_failure(self.sandbox.blame([("bogus", "fix it")]))
        # LLS: the failure identifies the invalid pair (the target name).
        self.assertIn("bogus", failure.value)

    def test_blame_mixed_valid_and_invalid_targets(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.blame([("agent", "good"), ("bogus", "bad")])
        )
        self.assertIn("bogus", failure.value)

    def test_blame_valid_pairs(self) -> None:
        blames: List[Tuple[str, str]] = [
            ("agent", "Fix the agent output"),
            ("system", "Fix the system output"),
        ]
        success = self.as_success(self.sandbox.blame(blames))
        self.assertIsInstance(success.value, FeedbackResult)
        assert isinstance(success.value, FeedbackResult)
        self.assertEqual(success.value.type, "feedback")
        self.assertEqual(success.value.messages, blames)

    # ------------------------------------------------------------------
    # get_write_occurred
    # ------------------------------------------------------------------

    def test_get_write_occurred_initial_false(self) -> None:
        self.assertFalse(self.sandbox.get_write_occurred())

    def test_get_write_occurred_true_after_write(self) -> None:
        self.as_tool_result(self.sandbox.write_file("test.txt", "content"))
        self.assertTrue(self.sandbox.get_write_occurred())

    def test_get_write_occurred_true_after_replace_chunks(self) -> None:
        self.as_tool_result(
            self.sandbox.replace_chunks("test.py", [{"index": 0, "new_content": "class NewClass:"}])
        )
        self.assertTrue(self.sandbox.get_write_occurred())

    def test_get_write_occurred_monotonic(self) -> None:
        self.as_tool_result(self.sandbox.write_file("test.txt", "content"))
        # A later failed write does not clear the flag.
        self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        self.assertTrue(self.sandbox.get_write_occurred())

    def test_get_write_occurred_false_after_failed_write(self) -> None:
        self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        self.assertFalse(self.sandbox.get_write_occurred())

    # ------------------------------------------------------------------
    # State / invariants
    # ------------------------------------------------------------------

    def test_no_state_persists_between_runs(self) -> None:
        # A fresh instance has no stubbing state even with identical config.
        self.as_tool_result(self.sandbox.read_file("test.txt", offset=0, limit=10))
        fresh = SandboxImpl(self.config)
        result = self.as_tool_result(fresh.read_file("test.txt", offset=0, limit=10))
        self.assertFalse(result.stub_previous)
        self.assertFalse(fresh.get_write_occurred())

    def test_errors_leave_filesystem_unchanged(self) -> None:
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            test_txt = f.read()
        with open(self.python_file_path, "r", encoding="utf-8") as f:
            test_py = f.read()
        snapshots = {"test.txt": test_txt, "test.py": test_py}
        self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        self.as_tool_failure(self.sandbox.write_file("unknown.txt", "x"))
        self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": 99, "new_content": "x"}])
        )
        self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": 0}])
        )
        self.as_tool_failure(self.sandbox.read_file("test.txt", offset=-1))
        for name, expected in snapshots.items():
            path = self.file_mappings[name]
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), expected, f"{name} was modified by a failed call")


class TestSandboxImplErrors(unittest.TestCase):
    """Error-message quality and filesystem edge cases."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.real_foo = os.path.join(self.temp_dir, "foo.txt")
        self.real_bar = os.path.join(self.temp_dir, "bar.txt")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def _config(self, file_mappings, readable_paths, writable_paths,
                blame_targets: Optional[List[str]] = None,
                read_size_limit: int = 100,
                search_result_limit: int = 10,
                verification_callback=None) -> SandboxConfig:
        return SandboxConfig(
            file_mappings=file_mappings,
            readable_paths=readable_paths,
            writable_paths=writable_paths,
            blame_targets=blame_targets or [],
            read_size_limit=read_size_limit,
            search_result_limit=search_result_limit,
            verification_callback=verification_callback,
        )

    def as_tool_failure(self, outcome: Any) -> ToolFailure:
        assert isinstance(outcome, ToolFailure), f"Expected ToolFailure, got {outcome!r}"
        return outcome

    def test_read_nonexistent_file_virtualizes_real_path(self) -> None:
        missing = os.path.join(self.temp_dir, "missing", "foo.txt")
        sandbox = SandboxImpl(self._config(
            file_mappings={"foo.txt": missing},
            readable_paths=["foo.txt"],
            writable_paths=[],
        ))
        failure = self.as_tool_failure(sandbox.read_file("foo.txt"))
        # LLS: messages name the virtual path, never the resolved filesystem path.
        self.assertIn("foo.txt", failure.value)
        self.assertNotIn(missing, failure.value)

    def test_error_messages_virtualize_partial_real_paths(self) -> None:
        # A real path that prefixes another is replaced longest-first.
        real_a = os.path.join(self.temp_dir, "foo.txt")
        real_b = os.path.join(self.temp_dir, "foo.txt.bak")
        sandbox = SandboxImpl(self._config(
            file_mappings={"foo.txt": real_a, "foo.txt.bak": real_b},
            readable_paths=["foo.txt", "foo.txt.bak"],
            writable_paths=[],
        ))
        failure = self.as_tool_failure(sandbox.read_file("foo.txt"))
        # LLS: messages name the virtual path, never the resolved filesystem path.
        self.assertIn("foo.txt", failure.value)
        self.assertNotIn(self.temp_dir, failure.value)

    def test_read_denial_lists_readable_files(self) -> None:
        sandbox = SandboxImpl(self._config(
            file_mappings={"foo.txt": self.real_foo, "bar.txt": self.real_bar},
            readable_paths=["foo.txt"],
            writable_paths=["foo.txt"],
        ))
        failure = self.as_tool_failure(sandbox.read_file("bar.txt"))
        # LLS (implementation spec): denial messages name the virtual path and
        # list the readable paths.
        self.assertIn("bar.txt", failure.value)
        self.assertIn("foo.txt", failure.value)
        failure2 = self.as_tool_failure(sandbox.read_file("baz.txt"))
        self.assertIn("foo.txt", failure2.value)

    def test_write_denial_lists_writable_files(self) -> None:
        sandbox = SandboxImpl(self._config(
            file_mappings={"foo.txt": self.real_foo, "bar.txt": self.real_bar},
            readable_paths=["foo.txt", "bar.txt"],
            writable_paths=["foo.txt"],
        ))
        failure = self.as_tool_failure(sandbox.write_file("bar.txt", "content"))
        # LLS (implementation spec): denial messages name the virtual path and
        # list the writable paths.
        self.assertIn("bar.txt", failure.value)
        self.assertIn("foo.txt", failure.value)
        failure2 = self.as_tool_failure(sandbox.write_file("baz.txt", "content"))
        self.assertIn("foo.txt", failure2.value)

    def test_search_nonexistent_path(self) -> None:
        missing = os.path.join(self.temp_dir, "nonexistent")
        sandbox = SandboxImpl(self._config(
            file_mappings={"d": missing},
            readable_paths=["d"],
            writable_paths=[],
        ))
        failure = self.as_tool_failure(sandbox.search_files("d", "pattern"))
        # LLS: messages name the virtual path, never the resolved filesystem path.
        self.assertIn("d", failure.value)
        self.assertNotIn(self.temp_dir, failure.value)

    def test_read_empty_file(self) -> None:
        empty = os.path.join(self.temp_dir, "empty.txt")
        open(empty, "w", encoding="utf-8").close()
        sandbox = SandboxImpl(self._config(
            file_mappings={"empty.txt": empty},
            readable_paths=["empty.txt"],
            writable_paths=["empty.txt"],
        ))
        result = sandbox.read_file("empty.txt")
        assert isinstance(result, ToolResult)
        self.assertEqual(result.content, "")
        self.assertFalse(result.stub_previous)

    def test_read_path_that_is_a_directory(self) -> None:
        sandbox = SandboxImpl(self._config(
            file_mappings={"d": self.temp_dir},
            readable_paths=["d"],
            writable_paths=[],
        ))
        failure = self.as_tool_failure(sandbox.read_file("d"))
        # LLS: messages name the virtual path; the exact wording is unspecified.
        self.assertIn("d", failure.value)

    def test_write_special_characters_round_trip(self) -> None:
        content = "Special chars: \n\t\ufffd\U0001F600"
        sandbox = SandboxImpl(self._config(
            file_mappings={"foo.txt": self.real_foo},
            readable_paths=["foo.txt"],
            writable_paths=["foo.txt"],
        ))
        result = sandbox.write_file("foo.txt", content)
        assert isinstance(result, ToolResult)
        with open(self.real_foo, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)


if __name__ == "__main__":
    unittest.main()
