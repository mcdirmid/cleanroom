"""
Interface LLS: bazel_graph_storage
Fulfills the dag_storage contract with data from the Bazel workspace, and
additionally resolves node definitions and package directories.
"""

from __future__ import annotations
from typing import Protocol
from dataclasses import dataclass
from .dag_storage import NodeId, DagStorage
from .sandbox import SandboxConfig


GraphSource = str


@dataclass
class GraphConfig:
    """Client-supplied configuration: either a graph source or a workspace root."""
    graph_source: GraphSource | None = None
    workspace_root: str | None = None


PackageDirectory = str


@dataclass
class NodeDefinition:
    """The agent prompt and sandbox configuration declared by a node's target."""
    prompt: str
    sandbox_config: SandboxConfig


class BazelGraphStorage(DagStorage, Protocol):
    """Interface for the LLS BazelGraphStorage: fulfills DagStorage and
    additionally resolves node definitions and package directories."""

    def resolve_node_definition(self, node_id: NodeId) -> NodeDefinition:
        """
        Return the agent prompt and sandbox configuration declared by a node's target.

        Preconditions:
        - node_id is a valid Bazel target label
        - The node ID resolves to a target with a complete definition

        Postconditions:
        - Returns a NodeDefinition containing the node's agent prompt
          and sandbox configuration as declared by the target

        Failure Handling:
        - No failure conditions; all valid node IDs resolve to complete definitions.

        HLS Justification: "Query a node's definition (the agent prompt and sandbox configuration)."
        """
        ...

    def resolve_package_directory(self, node_id: NodeId) -> PackageDirectory:
        """
        Return the directory containing the node's BUILD file.

        Preconditions:
        - node_id is a valid Bazel target label

        Postconditions:
        - Returns the package directory as the directory containing the node's BUILD file
        - Also the directory where the node's messages are stored

        Failure Handling:
        - No failure conditions; all valid node IDs have a package directory.

        HLS Justification: "Query a node's package directory."
        """
        ...
