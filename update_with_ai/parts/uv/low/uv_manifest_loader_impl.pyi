# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: c6caf889adb1
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Cleanroom manifest loader implementation low-level specification."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
from update_with_ai.parts.dag.lib import dag_storage
from . import uv_manifest_loader
import agent_storage
import dag_storage
import file_paths
import uv_target


@singleton_type("system")
class UvManifestLoader(
    uv_manifest_loader.UvManifestLoader, InTier[SystemTier]
):
    """Realizes role manifest loading, node resolution, and graph construction.

    GROUNDING:
    - Realizes uv_manifest_loader interface contracts by discovering role definitions and package structures across workspace directories, decoding schemas via uv_manifest_ext, and populating agent_storage and dag_storage.
    """

    @operation
    @override
    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[uv_manifest_loader.TargetManifest]:
        """Retrieves and parses target manifests from workspace directories.

        Args:
            node: The node whose manifest is retrieved.

        Returns:
            The parsed target manifest when found, or None.

        POSTCONDITIONS:
        - MUST retrieve target manifests from workspace directories for graph nodes.
        - MUST anchor relative package directories to the workspace root.
        - MUST search package directories upwards for scope configuration files to discover methodology bindings.
        - MUST load role definitions using uv manifest ext.
        - MUST evaluate role source patterns parameterized with unit metadata.
        - MUST evaluate task prompt templates parameterized with unit metadata.
        - MUST evaluate verification check templates parameterized with unit metadata.
        - MUST cross-product unit dependencies with role dependencies to produce target dependencies.
        - MUST incorporate fixed role node dependencies as declared direct dependencies across unit and role dimensions.
        - MUST resolve bare cross-package unit dependency references to their containing packages within parts workspaces.
        - MUST forward constituent unit dependencies and role dependencies for inactive pass-through nodes.
        - MUST synthesize promptless pass-through node definitions when a unit component type is not active for a role.

        GROUNDING:
        - Discovers unit specifications and role definitions across workspace directories using file_paths, decodes them via uv_manifest_ext, evaluates path patterns and prompt templates, and synthesizes TargetManifest records.
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
