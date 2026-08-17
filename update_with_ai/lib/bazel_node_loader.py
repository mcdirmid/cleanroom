"""
Interface LLS: bazel_node_loader

Runtime loader for update_with_ai manifests.

Defines the BazNode data-class Protocol (static node metadata bundled with
the ToolProvider interface) and the BazelNodeLoader interface. The runtime
loader implementation (manifest resolution, caching) lives in
bazel_node_loader_impl.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from .tool_provider import ToolProvider


@dataclass
class BazNode(ToolProvider):
    """
    A data class Protocol that bundles static node metadata with the
    ToolProvider interface. Internal state fields (e.g., _dependency_nodes,
    _agent_loop) are implementation-specific and defined in the
    implementation spec (BazNodeImpl).
    """
    label: str
    prompt: str
    tools: List[str]          # Tool target labels
    deps: List[str]           # Dependency node labels
    silent_deps: List[str]    # Silent deps (output readable, cleaned after)
    srcs: List[str]           # Files the agent can write that deps can read
    silent_srcs: List[str]    # Files the agent can write that deps cannot read


class BazelNodeLoader(Protocol):
    """Interface for loading Bazel nodes from manifests."""

    def load_node(self, label: str) -> Optional[BazNode]:
        """Load a single node from its manifest; None if not found."""
        ...

    def load_graph(self, root_label: str) -> Dict[str, BazNode]:
        """Load all nodes in the subgraph rooted at root_label."""
        ...

    def get_node_prompt(self, node_label: str) -> Optional[str]:
        """Get the prompt for a node; None if not found."""
        ...
