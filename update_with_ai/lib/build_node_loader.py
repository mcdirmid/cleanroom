"""
Interface LLS: build_node_loader

Runtime loader for update_with_ai manifests.

Defines the BuildNode data-class Protocol (static node metadata bundled with
the ToolProvider interface) and the BuildNodeLoader interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

from .tool_provider import ToolProvider


@dataclass
class BuildNode(ToolProvider):
    """
    A data class Protocol that bundles static node metadata with the
    ToolProvider interface. Internal state fields (e.g., _dependency_nodes,
    _agent_loop) are implementation-specific and defined in the
    implementation spec (BuildNodeImpl).
    """
    label: str
    prompt: str
    tools: List[str]          # Tool target labels
    deps: List[str]           # Dependency node labels (incl. feedback deps)
    silent_deps: List[str]    # Silent deps (cleaned before run; output not readable; changes do not propagate)
    src: str = ""             # Declared source file (the artifact the agent writes)
    template: Optional[str] = None  # Declared source file's template (repo-relative path; initializes src at run start when missing)
    guide: Optional[str] = None  # The declared guide node label (declared separately from deps; its file is the run's guide)
    silent_srcs: List[str] = field(default_factory=list)  # Files the agent can write that deps cannot read
    feedback_deps: List[str] = field(default_factory=list)  # Deps that can receive feedback; included in deps


class BuildNodeLoader(Protocol):
    """Interface for loading build nodes from manifests."""

    def load_node(self, label: str) -> Optional[BuildNode]:
        """Load a single node from its manifest; None if not found."""
        ...

    def load_graph(self, root_label: str) -> Dict[str, BuildNode]:
        """Load all nodes in the subgraph rooted at root_label."""
        ...

    def get_node_prompt(self, node_label: str) -> Optional[str]:
        """Get the prompt for a node; None if not found."""
        ...
