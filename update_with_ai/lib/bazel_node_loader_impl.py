"""
Implementation LLS: bazel_node_loader_impl

This module provides the runtime representation of a Bazel node
(BazNodeImpl) and the manifest loader (BazelNodeLoaderImpl).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .bazel_node_loader import BazNode, BazelNodeLoader
from .tool_provider import ToolFailure, ToolCallOutcome, ToolExecutor
from .agent_loop import AgentResult


def _get_runfiles_path() -> Path:
    """
    Get the runfiles directory path.

    Returns:
        Path to runfiles directory
    """
    # Try Bazel runfiles library first
    try:
        from bazel_tools.tools.python.runfiles import runfiles  # type: ignore
        r = runfiles.Create()
        runfiles_dir = r.Rlocation("cleanroom")
        if runfiles_dir:
            return Path(runfiles_dir)
    except ImportError:
        pass

    # Fallback: use environment variable or current directory
    runfiles_path = os.environ.get("RUNFILES_DIR")
    if runfiles_path:
        return Path(runfiles_path)

    return Path.cwd()


def _resolve_manifest_path(label: str, runfiles: Path) -> Optional[Path]:
    """
    Resolve a node label to its manifest file path.

    Args:
        label: Bazel label like "//path:to:target"
        runfiles: Path to runfiles directory

    Returns:
        Path to manifest file, or None if not found at any known location.
    """
    label_str = str(label)
    if label_str.startswith("//"):
        rel_path = label_str[2:].replace(":", "/") + "_manifest.json"
    else:
        rel_path = label_str.replace(":", "/") + "_manifest.json"

    # Try standard location
    manifest_path = runfiles / rel_path
    if manifest_path.exists():
        return manifest_path

    # Try alternative location
    alt_path = runfiles / "workspace" / rel_path
    if alt_path.exists():
        return alt_path

    return None


@dataclass
class BazNodeImpl(BazNode):
    """
    Runtime representation of a update_with_ai.

    Extends the interface's BazNode data-class Protocol (which itself extends
    ToolProvider), adding implementation-internal state and implementing the
    tool-provider operations.
    """

    _tool_providers: Dict[str, Any] = field(default_factory=dict)  # label -> loaded provider (lazy cache)
    _dependency_nodes: List["BazNodeImpl"] = field(default_factory=list)  # Loaded at runtime
    _agent_loop: Any = None  # Set externally at runtime

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return tool definitions from configured tools."""
        definitions: List[Dict[str, Any]] = []
        for tool_label in self.tools:
            # Dynamically load tool provider
            tool: Any = self._load_tool(tool_label)
            if tool and hasattr(tool, 'get_tool_definitions'):
                definitions.extend(tool.get_tool_definitions())
        return definitions

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolCallOutcome:
        """Execute a tool call."""
        for tool_label in self.tools:
            tool: Any = self._load_tool(tool_label)
            if tool and hasattr(tool, 'execute_tool'):
                result = tool.execute_tool(name, arguments)
                if result is not None:
                    return result
        # Not found - return a tool failure (T_tool resolved to str per the
        # implementation spec)
        return ToolFailure[str]("Tool {} not found".format(name))

    def run_prompt(self, prompt: str, tool_executor: ToolExecutor) -> AgentResult:
        """
        Run the agent loop with the configured prompt.

        Args:
            prompt: The user prompt
            tool_executor: Function to execute tool calls

        Returns:
            AgentResult
        """
        # Get agent loop from environment or create one
        agent_loop = getattr(self, '_agent_loop', None)
        if agent_loop is None:
            return ("Agent loop not configured", [])

        return agent_loop.run_agent(
            prompt=prompt,
            tools=self.get_tool_definitions(),
            tool_executor=tool_executor,
        )

    def _load_tool(self, tool_label: str) -> Optional[object]:
        """
        Dynamically load a tool provider from runfiles.

        Args:
            tool_label: Bazel label like "//path:tool_name"

        Returns:
            Tool provider instance or None
        """
        import importlib
        import sys

        # Per-node cache (implementation spec: a tool provider is loaded at
        # most once per node; _tool_providers holds the loaded instances
        # keyed by tool label).
        cached = self._tool_providers.get(tool_label)
        if cached is not None:
            return cached

        # Convert label to a dotted module name (importlib-based loading,
        # per the implementation spec: modules are resolved from sys.path).
        # e.g., //my_pkg:tool -> module my_pkg.tool
        label_str = str(tool_label)
        if label_str.startswith("//"):
            rel_path = label_str[2:].replace(":", "/")
        else:
            rel_path = label_str.replace(":", "/")

        # Try to import the module
        try:
            module_name = rel_path.replace("/", ".").replace(".py", "")
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                module = importlib.import_module(module_name)

            # Look for tool provider class or factory function
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if hasattr(attr, 'get_tool_definitions'):
                    provider = attr() if callable(attr) else attr
                    self._tool_providers[tool_label] = provider
                    return provider
        except Exception:
            pass

        return None

    def _load_dependencies(self, load_node_fn: Callable) -> List["BazNodeImpl"]:
        """Load dependency nodes from manifests.

        Args:
            load_node_fn: Function that loads a node by label.
        """
        self._dependency_nodes = []
        for dep_label in list(self.deps) + list(self.silent_deps):
            dep = load_node_fn(dep_label)
            if dep:
                self._dependency_nodes.append(dep)
        return self._dependency_nodes


class BazelNodeLoaderImpl(BazelNodeLoader):
    """Loads nodes from manifests and caches them by label."""

    def __init__(self) -> None:
        self._node_cache: Dict[str, BazNodeImpl] = {}

    def load_node(self, label: str) -> Optional[BazNode]:
        """
        Load a single node from its manifest.

        Returns:
            BazNodeImpl instance or None if not found. Cached instances are
            returned without reading the manifest. Partial loads do not
            populate the cache.
        """
        if label in self._node_cache:
            return self._node_cache[label]

        runfiles = _get_runfiles_path()
        manifest_path = _resolve_manifest_path(label, runfiles)

        if manifest_path is None:
            return None

        # Load manifest
        with open(manifest_path) as f:
            data = json.load(f)

        # Feedback deps are automatically included in deps: the loaded node's
        # deps are the manifest's deps expanded with its feedback deps
        # (deduplicated). This holds even when the manifest was produced
        # without the macro's own expansion.
        raw_deps = list(data.get("deps", []))
        feedback_deps = list(data.get("feedback_deps", []))
        deps = list(raw_deps)
        for fd in feedback_deps:
            if fd not in deps:
                deps.append(fd)

        node = BazNodeImpl(
            label=data["label"],
            prompt=data["prompt"],
            tools=data.get("tools", []),
            deps=deps,
            silent_deps=data.get("silent_deps", []),
            feedback_deps=feedback_deps,
            srcs=data.get("srcs", []),
            silent_srcs=data.get("silent_srcs", []),
        )

        # Load dependencies (avoid circular import)
        node._load_dependencies(self.load_node)

        self._node_cache[label] = node
        return node

    def load_graph(self, root_label: str) -> Dict[str, BazNode]:
        """
        Load an entire graph starting from the root node.

        Args:
            root_label: Bazel label of root node

        Returns:
            Dict mapping labels to BazNode instances (root and transitive
            deps, including silent_deps). Unknown labels are omitted.
        """
        nodes: Dict[str, BazNode] = {}

        def _load_recursive(node_label: str) -> None:
            if node_label in nodes:
                return

            node = self.load_node(node_label)
            if node is None:
                return

            nodes[node_label] = node

            # Recursively load dependencies
            for dep_label in node.deps:
                _load_recursive(dep_label)

            # Also load silent_deps
            for dep_label in node.silent_deps:
                _load_recursive(dep_label)

        _load_recursive(root_label)
        return nodes

    def get_node_prompt(self, node_label: str) -> Optional[str]:
        """
        Get the prompt for a node without loading the full node.

        Args:
            node_label: Bazel label

        Returns:
            Prompt string or None
        """
        manifest = self.load_node(node_label)
        if manifest:
            return manifest.prompt
        return None
