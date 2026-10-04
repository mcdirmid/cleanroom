"""Bazel manifest loader implementation low-level specification."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import bazel_manifest_loader
import dag_storage


@singleton_type("system")
class BazelManifestLoader(
    bazel_manifest_loader.BazelManifestLoader, InTier[SystemTier]
):
    """Realizes JSON manifest loading, node resolution, and graph construction."""

    @operation
    @override
    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[bazel_manifest_loader.TargetManifest]:
        """Retrieves and parses target manifests from workspace directories or runfiles trees.

        Args:
            node: The node whose manifest is retrieved.

        Returns:
            The parsed target manifest when found, or None.

        POSTCONDITIONS:
        - MUST retrieve target manifests from workspace directories for graph nodes.
        - MUST retrieve target manifests from runfiles trees for graph nodes.
        - MUST anchor relative package directories to the workspace root.
        - MUST anchor canonical package paths to candidate runfiles roots.
        - MUST load unit manifests using bazel manifest ext.
        - MUST load role manifests using bazel manifest ext.
        - MUST load monolithic target manifests using bazel manifest ext.
        - MUST evaluate role source patterns parameterized with unit metadata.
        - MUST evaluate task prompt templates parameterized with unit metadata.
        - MUST evaluate verification check templates parameterized with unit metadata.
        - MUST cross-product unit dependencies with role dependencies to produce target dependencies.
        - MUST incorporate fixed role node dependencies as declared direct dependencies across unit and role dimensions.
        - MUST synthesize promptless pass-through node definitions when a unit component type is not active for a role.
        """
        ...

    @operation
    @override
    def load_manifest(self, node: dag_storage.DagNode) -> None:
        """Resolves target manifests into graph structures and node definitions.

        Args:
            node: The target node to load and resolve.

        POSTCONDITIONS:
        - MUST populate agent storage with node definitions carrying task prompts.
        - MUST record declared primary source file paths in agent storage without duplicating package path segments.
        - MUST register declared direct dependencies in agent storage.
        - MUST register declared silent dependencies as non-propagating dependencies in agent storage.
        - MUST synthesize fallback node definitions for referenced targets lacking manifests.
        """
        ...
