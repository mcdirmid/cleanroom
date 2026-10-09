# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-05T05:39:52Z
# CHANGE: Add silent source file path contract to load_manifest
# CODE_HASH: 2648c2d5a137
# --- END CLEANROOM METADATA ---

"""Bazel manifest loader implementation low-level specification."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import bazel_manifest_loader
import dag_storage
import agent_storage
import bazel_target
import file_paths


@singleton_type("system")
class BazelManifestLoader(
    bazel_manifest_loader.BazelManifestLoader, InTier[SystemTier]
):
    """Realizes JSON manifest loading, node resolution, and graph construction.

    GROUNDING:
    - Realizes bazel_manifest_loader interface contracts by discovering build manifests across filesystem search paths, decoding schemas via bazel_manifest_ext, and populating agent_storage and dag_storage.
    """

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

        GROUNDING:
        - Discovers unit and role manifests across workspace directories and runfiles trees using file_paths, decodes them via bazel_manifest_ext, evaluates path patterns and prompt templates, and synthesizes TargetManifest records.
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
        - MUST record silent source file paths in agent storage without duplicating package path segments.
        - MUST register declared direct dependencies in agent storage.
        - MUST register declared feedback dependencies in agent storage.
        - MUST register declared silent dependencies as non-propagating dependencies in agent storage.
        - MUST synthesize fallback node definitions for referenced targets lacking manifests.

        GROUNDING:
        - Discovers and parses TargetManifest records via retrieve_manifest, populating node definitions and prompt metadata into agent_storage and registering dependency relationships into dag_storage.
        """
        ...
