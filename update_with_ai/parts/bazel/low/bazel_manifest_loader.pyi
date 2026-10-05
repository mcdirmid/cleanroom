# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-05T05:39:33Z
# CHANGE: Streamline manifest resolution by removing redundant dependency contract
# CODE_HASH: a98631a93804
# --- END CLEANROOM METADATA ---

"""Bazel manifest loader low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import agent_file_alias
import agent_storage
import dag_storage

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



@singleton_type("system")
class BazelManifestLoader(InTier[SystemTier], Protocol):
    """Discovers and translates build system target manifests into runtime graph structures and node definitions."""

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
        """
        ...
