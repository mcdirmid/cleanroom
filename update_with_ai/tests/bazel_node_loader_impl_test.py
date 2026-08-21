"""
tests/bazel_node_loader_impl_test.py

Unit tests for lib/bazel_node_loader_impl.py, asserting the implementation
LLS (specs/bazel_node_loader_impl-low.md) contract:

- Manifest paths derive deterministically from labels: //pkg:target ->
  pkg/target_manifest.json in runfiles (LLS invariant).
- load_node builds a BazNodeImpl with all manifest fields, returns None for
  unknown labels, caches by label, and never caches partial loads.
- load_graph returns the root plus transitive deps (declared and silent),
  omitting unknown labels.
- get_node_prompt returns the node's prompt or None.
- BazNodeImpl tool-provider operations dynamically load provider modules via
  importlib (//pkg:tool -> module pkg.tool), lazily cached per node in
  _tool_providers.
- execute_tool returns the first non-None outcome from declared providers;
  ToolFailure("Tool {name} not found") when no provider handles the call.
- run_prompt returns a loop-failure result when no agent loop is configured
  and otherwise delegates to agent_loop.run_agent with the node's tools.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

from unittest.mock import Mock, patch

from update_with_ai.lib.bazel_node_loader import BazNode
from update_with_ai.lib.bazel_node_loader_impl import (
    BazNodeImpl,
    BazelNodeLoaderImpl,
    _resolve_manifest_path,
)
from update_with_ai.lib.tool_provider import Continue, ToolCallOutcome, ToolFailure, ToolResult


def _noop_executor(name: str, arguments: Dict[str, Any]) -> ToolCallOutcome:
    """A ToolExecutor that always asks the agent loop to continue."""
    return Continue()


# Tool provider modules are written into the temp workspace and loaded via
# the real importlib path in _load_tool (label //testproviders:tool_a ->
# module testproviders.tool_a). The %r formatting keeps the definition the
# module returns byte-for-byte identical to the expected constant below.
PROVIDER_A_DEFINITION = {
    "name": "tool_a",
    "description": "Tool A",
    "parameters": {"type": "object", "properties": {}},
}
PROVIDER_B_DEFINITION = {
    "name": "tool_b",
    "description": "Tool B",
    "parameters": {"type": "object", "properties": {}},
}

PROVIDER_A_SOURCE = """\
from update_with_ai.lib.tool_provider import ToolResult


class ToolProviderA:
    def get_tool_definitions(self):
        return [%r]

    def execute_tool(self, name, arguments):
        if name == "tool_a":
            return ToolResult(content="result from a", supersedes=False)
        return None
""" % (PROVIDER_A_DEFINITION,)

PROVIDER_B_SOURCE = """\
from update_with_ai.lib.tool_provider import ToolResult


class ToolProviderB:
    def get_tool_definitions(self):
        return [%r]

    def execute_tool(self, name, arguments):
        if name == "tool_b":
            return ToolResult(content="result from b", supersedes=False)
        return None
""" % (PROVIDER_B_DEFINITION,)


class TestManifestPathResolution(unittest.TestCase):
    """LLS invariant: manifest paths derive deterministically from labels."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cleanroom_manifest_resolution_")
        self.runfiles = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_label_maps_to_pkg_target_manifest_json(self):
        """//pkg:target -> pkg/target_manifest.json (LLS invariant)."""
        manifest = self.runfiles / "pkg" / "target_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}")
        resolved = _resolve_manifest_path("//pkg:target", self.runfiles)
        self.assertEqual(resolved, manifest)

    def test_nonexistent_manifest_returns_none(self):
        """A label with no manifest file resolves to None (unknown label)."""
        self.assertIsNone(_resolve_manifest_path("//pkg:missing", self.runfiles))

    def test_falls_back_to_workspace_location(self):
        """Resolves through the runfiles/workspace prefix when present."""
        manifest = self.runfiles / "workspace" / "pkg" / "target_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}")
        resolved = _resolve_manifest_path("//pkg:target", self.runfiles)
        self.assertEqual(resolved, manifest)


class _TempRunfilesTestCase(unittest.TestCase):
    """Fixture: a temp runfiles workspace with _get_runfiles_path mocked."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cleanroom_loader_test_")
        self.runfiles = Path(self.tmp)
        self.loader = BazelNodeLoaderImpl()
        self._runfiles_patcher = patch(
            "update_with_ai.lib.bazel_node_loader_impl._get_runfiles_path",
            return_value=self.runfiles,
        )
        self._runfiles_patcher.start()
        self.addCleanup(self._runfiles_patcher.stop)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write_manifest(
        self,
        pkg: str,
        name: str,
        label: str,
        *,
        prompt: str = "test prompt",
        tools: Optional[List[str]] = None,
        deps: Optional[List[str]] = None,
        silent_deps: Optional[List[str]] = None,
        feedback_deps: Optional[List[str]] = None,
        srcs: Optional[List[str]] = None,
        silent_srcs: Optional[List[str]] = None,
    ) -> Path:
        """Write <runfiles>/<pkg>/<name>_manifest.json for label //pkg:name."""
        pkg_dir = self.runfiles / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "label": label,
            "prompt": prompt,
            "tools": tools if tools is not None else [],
            "deps": deps if deps is not None else [],
            "silent_deps": silent_deps if silent_deps is not None else [],
            "feedback_deps": feedback_deps if feedback_deps is not None else [],
            "srcs": srcs if srcs is not None else [],
            "silent_srcs": silent_srcs if silent_srcs is not None else [],
        }
        path = pkg_dir / (name + "_manifest.json")
        with open(path, "w") as f:
            json.dump(manifest, f)
        return path

    def load_impl(self, label: str) -> BazNodeImpl:
        """load_node(label) asserted to return a BazNodeImpl (contract)."""
        node = self.loader.load_node(label)
        self.assertIsInstance(node, BazNodeImpl)
        assert isinstance(node, BazNodeImpl)
        return node


class TestLoadNode(_TempRunfilesTestCase):
    """load_node: manifests -> BazNodeImpl, caching by label."""

    def test_load_node_returns_node_with_all_manifest_fields(self):
        """load_node builds a BazNodeImpl carrying every manifest field."""
        self.write_manifest(
            "pkg",
            "target",
            "//pkg:target",
            prompt="Target prompt",
            tools=["//pkg:tool_a"],
            deps=["//pkg:dep"],
            silent_deps=["//pkg:silent_dep"],
            feedback_deps=["//pkg:fdep"],
            srcs=["foo.txt"],
            silent_srcs=["private.log"],
        )
        node = self.load_impl("//pkg:target")
        self.assertIsInstance(node, BazNode)
        self.assertEqual(node.label, "//pkg:target")
        self.assertEqual(node.prompt, "Target prompt")
        self.assertEqual(node.tools, ["//pkg:tool_a"])
        self.assertEqual(node.deps, ["//pkg:dep", "//pkg:fdep"])
        self.assertEqual(node.silent_deps, ["//pkg:silent_dep"])
        self.assertEqual(node.feedback_deps, ["//pkg:fdep"])
        self.assertEqual(node.srcs, ["foo.txt"])
        self.assertEqual(node.silent_srcs, ["private.log"])

    def test_load_node_includes_feedback_deps_in_deps(self):
        """Feedback deps are automatically included in deps: a manifest with
        deps [] and feedback_deps ["//pkg:fdep"] loads a node whose deps
        include "//pkg:fdep" (deduplicated)."""
        self.write_manifest("pkg", "fdep", "//pkg:fdep", prompt="FD")
        self.write_manifest(
            "pkg",
            "root",
            "//pkg:root",
            prompt="Root",
            feedback_deps=["//pkg:fdep"],
        )
        root = self.load_impl("//pkg:root")
        self.assertEqual(root.feedback_deps, ["//pkg:fdep"])
        self.assertEqual(root.deps, ["//pkg:fdep"])
        self.assertEqual(
            [n.label for n in root._dependency_nodes], ["//pkg:fdep"]
        )

    def test_load_node_unknown_label_returns_none(self):
        """Unknown labels produce None (invalid labels never cached)."""
        self.assertIsNone(self.loader.load_node("//pkg:does_not_exist"))

    def test_load_node_caches_by_label(self):
        """Repeated loads return the same cached instance (identity)."""
        self.write_manifest("pkg", "target", "//pkg:target", prompt="P")
        first = self.load_impl("//pkg:target")
        second = self.load_impl("//pkg:target")
        self.assertIs(first, second)

    def test_partial_load_does_not_populate_cache(self):
        """A node is cached only after successful deserialization (LLS)."""
        broken = self.runfiles / "pkg" / "broken_manifest.json"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_text("{not valid json")
        with self.assertRaises(json.JSONDecodeError):
            self.loader.load_node("//pkg:broken")
        # The failed load must not have cached anything: once the manifest is
        # repaired the next load reads it fresh and succeeds.
        self.write_manifest("pkg", "broken", "//pkg:broken", prompt="Fixed")
        node = self.load_impl("//pkg:broken")
        self.assertEqual(node.prompt, "Fixed")

    def test_load_node_populates_dependency_nodes_including_silent_deps(self):
        """_dependency_nodes holds resolved deps AND silent deps."""
        self.write_manifest("pkg", "dep", "//pkg:dep", prompt="Dep")
        self.write_manifest("pkg", "silent_dep", "//pkg:silent_dep", prompt="Silent")
        self.write_manifest(
            "pkg",
            "root",
            "//pkg:root",
            prompt="Root",
            deps=["//pkg:dep"],
            silent_deps=["//pkg:silent_dep"],
        )
        root = self.load_impl("//pkg:root")
        self.assertEqual(
            [n.label for n in root._dependency_nodes],
            ["//pkg:dep", "//pkg:silent_dep"],
        )

    def test_load_node_skips_unknown_deps_in_dependency_nodes(self):
        """Unknown dependency labels are omitted from _dependency_nodes."""
        self.write_manifest("pkg", "dep", "//pkg:dep", prompt="Dep")
        self.write_manifest(
            "pkg",
            "root",
            "//pkg:root",
            prompt="Root",
            deps=["//pkg:dep", "//pkg:missing"],
        )
        root = self.load_impl("//pkg:root")
        self.assertEqual([n.label for n in root._dependency_nodes], ["//pkg:dep"])


class TestLoadGraph(_TempRunfilesTestCase):
    """load_graph: root + transitive deps incl. silent deps; unknown omitted."""

    def test_load_graph_returns_root_and_transitive_deps(self):
        """Graph contains root and all transitive deps, including silent."""
        self.write_manifest("pkg", "leaf", "//pkg:leaf", prompt="Leaf")
        self.write_manifest("pkg", "dep", "//pkg:dep", prompt="Dep", deps=["//pkg:leaf"])
        self.write_manifest("pkg", "silent_dep", "//pkg:silent_dep", prompt="Silent")
        self.write_manifest(
            "pkg",
            "root",
            "//pkg:root",
            prompt="Root",
            deps=["//pkg:dep"],
            silent_deps=["//pkg:silent_dep"],
        )
        graph = self.loader.load_graph("//pkg:root")
        self.assertEqual(
            set(graph),
            {"//pkg:root", "//pkg:dep", "//pkg:silent_dep", "//pkg:leaf"},
        )
        self.assertEqual(graph["//pkg:root"].prompt, "Root")
        self.assertEqual(graph["//pkg:leaf"].prompt, "Leaf")

    def test_load_graph_omits_unknown_labels(self):
        """Unknown labels are omitted from the loaded graph (LLS)."""
        self.write_manifest("pkg", "dep", "//pkg:dep", prompt="Dep")
        self.write_manifest(
            "pkg",
            "root",
            "//pkg:root",
            prompt="Root",
            deps=["//pkg:dep", "//pkg:missing"],
        )
        graph = self.loader.load_graph("//pkg:root")
        self.assertEqual(set(graph), {"//pkg:root", "//pkg:dep"})
        self.assertNotIn("//pkg:missing", graph)


class TestGetNodePrompt(_TempRunfilesTestCase):
    """get_node_prompt: prompt for a known node, None otherwise."""

    def test_returns_prompt_for_existing_node(self):
        self.write_manifest("pkg", "target", "//pkg:target", prompt="Target prompt")
        self.assertEqual(self.loader.get_node_prompt("//pkg:target"), "Target prompt")

    def test_returns_none_for_unknown_node(self):
        self.assertIsNone(self.loader.get_node_prompt("//pkg:does_not_exist"))


class TestBazNodeImplToolProviders(unittest.TestCase):
    """BazNodeImpl tool-provider operations (importlib loading, lazy cache)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cleanroom_tool_provider_test_")
        providers_dir = Path(self.tmp) / "testproviders"
        providers_dir.mkdir()
        (providers_dir / "tool_a.py").write_text(PROVIDER_A_SOURCE)
        (providers_dir / "tool_b.py").write_text(PROVIDER_B_SOURCE)
        sys.path.insert(0, self.tmp)

    def tearDown(self):
        sys.path.remove(self.tmp)
        for name in list(sys.modules):
            if name == "testproviders" or name.startswith("testproviders."):
                del sys.modules[name]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_node(self, tools: List[str]) -> BazNodeImpl:
        return BazNodeImpl(
            label="//pkg:target",
            prompt="test prompt",
            tools=tools,
            deps=[],
            silent_deps=[],
            srcs=[],
            silent_srcs=[],
        )

    def test_get_tool_definitions_extends_declared_providers(self):
        """get_tool_definitions extends results across declared providers."""
        node = self.make_node(["//testproviders:tool_a", "//testproviders:tool_b"])
        definitions = node.get_tool_definitions()
        self.assertEqual(
            definitions,
            [PROVIDER_A_DEFINITION, PROVIDER_B_DEFINITION],
        )

    def test_get_tool_definitions_empty_without_tools(self):
        """A node declaring no tools yields no definitions (may be empty)."""
        node = self.make_node([])
        self.assertEqual(node.get_tool_definitions(), [])

    def test_execute_tool_returns_first_non_none_outcome(self):
        """execute_tool returns the first non-None outcome from providers."""
        node = self.make_node(["//testproviders:tool_a", "//testproviders:tool_b"])
        # tool_a does not handle "tool_b"; the first non-None outcome comes
        # from the second declared provider.
        outcome = node.execute_tool("tool_b", {"k": "v"})
        self.assertIsInstance(outcome, ToolResult)
        assert isinstance(outcome, ToolResult)
        self.assertEqual(outcome.type, "tool_result")
        self.assertEqual(outcome.content, "result from b")

    def test_execute_tool_returns_tool_failure_when_unhandled(self):
        """No declared provider handling the call -> ToolFailure(name)."""
        node = self.make_node(["//testproviders:tool_a", "//testproviders:tool_b"])
        outcome = node.execute_tool("ghost", {})
        self.assertIsInstance(outcome, ToolFailure)
        assert isinstance(outcome, ToolFailure)
        self.assertEqual(outcome.type, "tool_failure")
        self.assertEqual(outcome.value, "Tool ghost not found")

    def test_tool_providers_is_lazy_per_node_cache(self):
        """A provider is loaded at most once per node; same instance reused."""
        node = self.make_node(["//testproviders:tool_a"])
        provider = node._load_tool("//testproviders:tool_a")
        self.assertIsNotNone(provider)
        again = node._load_tool("//testproviders:tool_a")
        self.assertIs(provider, again)
        self.assertIn("//testproviders:tool_a", node._tool_providers)
        self.assertIs(node._tool_providers["//testproviders:tool_a"], provider)

    def test_load_tool_returns_none_for_unimportable_label(self):
        """An unresolvable tool label loads to None, not a cached failure."""
        node = self.make_node([])
        self.assertIsNone(node._load_tool("//nonexistent_pkg:ghost"))

    def test_run_prompt_delegates_to_agent_loop_with_nodes_tools(self):
        """run_prompt passes the node's tool definitions to run_agent."""
        node = self.make_node(["//testproviders:tool_a"])
        mock_loop = Mock()
        node._agent_loop = mock_loop
        result = node.run_prompt("hello", _noop_executor)
        self.assertIs(result, mock_loop.run_agent.return_value)
        mock_loop.run_agent.assert_called_once_with(
            prompt="hello",
            tools=[PROVIDER_A_DEFINITION],
            tool_executor=_noop_executor,
        )


class TestRunPrompt(unittest.TestCase):
    """run_prompt: loop-failure without an agent loop; delegation otherwise."""

    def make_node(self) -> BazNodeImpl:
        return BazNodeImpl(
            label="//pkg:target",
            prompt="test prompt",
            tools=[],
            deps=[],
            silent_deps=[],
            srcs=[],
            silent_srcs=[],
        )

    def test_run_prompt_without_agent_loop_returns_loop_failure(self):
        """Unconfigured agent loop -> ("Agent loop not configured", [])."""
        node = self.make_node()
        result = node.run_prompt("hello", _noop_executor)
        self.assertEqual(result, ("Agent loop not configured", []))

    def test_run_prompt_delegates_to_agent_loop(self):
        """With an agent loop configured, run_agent is called with the tools."""
        node = self.make_node()
        mock_loop = Mock()
        node._agent_loop = mock_loop
        result = node.run_prompt("hello", _noop_executor)
        self.assertIs(result, mock_loop.run_agent.return_value)
        mock_loop.run_agent.assert_called_once_with(
            prompt="hello",
            tools=[],
            tool_executor=_noop_executor,
        )


if __name__ == "__main__":
    unittest.main()
