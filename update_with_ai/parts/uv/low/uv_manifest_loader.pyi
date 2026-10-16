# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T03:48:25Z
# CHANGE: Register synthesized pass-through definitions as non-propagating graph dependencies
# CODE_HASH: d383f1f2a4e5
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Cleanroom manifest loader low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage

TargetLabel = NewType("TargetLabel", str)
VerificationCommand = NewType("VerificationCommand", str)


@dataclass(frozen=True)
@data_type
class TargetManifest:
    """Build artifact carrying node references and file paths for a workspace target.

    Args:
        label: Target node label.
        task_prompt: Task prompt text.
        source_file: Declared source file path.
        silent_source_files: Declared silent source file paths.
        template: Declared template content or path.
        dependencies: Direct dependency target labels.
        silent_dependencies: Silent dependency target labels.
        star_dependencies: Star dependency target labels.
        feedback_dependencies: Feedback dependency target labels.
        guide_target: Declared guide target label.
        verification_check: Verification check command or specification.
        allows_step_mode: Whether the target allows step mode execution.
        verification_success_message: Optional message presented when verification succeeds.
    """
    label: TargetLabel
    task_prompt: Optional[agent_storage.TaskPrompt] = ...
    source_file: Optional[agent_file_alias.RelativePath] = ...
    silent_source_files: Sequence[agent_file_alias.RelativePath] = ...
    template: Optional[agent_file_alias.FileContent] = ...
    dependencies: Sequence[TargetLabel] = ...
    silent_dependencies: Sequence[TargetLabel] = ...
    star_dependencies: Sequence[TargetLabel] = ...
    feedback_dependencies: Sequence[TargetLabel] = ...
    guide_target: Optional[TargetLabel] = ...
    verification_check: Optional[VerificationCommand] = ...
    allows_step_mode: Optional[bool] = ...
    verification_success_message: Optional[str] = ...


@singleton_type("system")
class UvManifestLoader(InTier[SystemTier], Protocol):
    """Discovers and translates workspace role definitions into runtime graph structures and node definitions."""

    @operation
    def retrieve_manifest(self, node: dag_storage.DagNode) -> Optional[TargetManifest]:
        """Retrieves the target manifest for a node.

        Args:
            node: The node whose manifest is retrieved.

        Returns:
            The target manifest when found, or None.

        POSTCONDITIONS:
        - MUST retrieve the manifest for the node.
        """
        ...

    @operation
    def load_manifest(self, node: dag_storage.DagNode) -> None:
        """Resolves manifests into target nodes, definitions, and prompts.

        Args:
            node: The target node to load and resolve.

        POSTCONDITIONS:
        - MUST resolve manifests into target nodes, node definitions, task prompts, and dependency graph edges.
        - MUST populate agent storage with resolved structures.
        - MUST resolve declared direct dependencies into dependency graph edges in agent storage.
        - MUST resolve declared silent dependencies as non-propagating dependencies in agent storage.
        - MUST synthesize definitions for declared dependencies lacking explicit manifests.
        - MUST synthesize promptless pass-through node definitions when a unit component type is not active for a role.
        - WHEN synthesizing promptless pass-through node definitions because a unit component type is not active for a role, MUST register the synthesized definitions as graph dependencies that do not propagate changes.
        """
        ...
