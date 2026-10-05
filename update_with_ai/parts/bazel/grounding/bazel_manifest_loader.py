# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-05T06:13:46Z
# CHANGE: Align postconditions and class docstrings with low-level contract
# CODE_HASH: 0ba92064695f
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Bazel manifest loader grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from support.lib.grounding_support import InTier, SystemTier
from parts.agent.grounding import agent_file_alias, agent_storage
from parts.dag.grounding import dag_storage

TargetLabel = NewType("TargetLabel", str)
VerificationCommand = NewType("VerificationCommand", str)


@dataclass(frozen=True)
class TargetManifest:
    """Build artifact carrying node references and file paths for a workspace target.

    COVERED:
    - Encapsulates label, prompt, source files, template, and dependency relations.
    """

    label: TargetLabel
    task_prompt: Optional[agent_storage.TaskPrompt] = None
    source_file: Optional[agent_file_alias.RelativePath] = None
    silent_source_files: Sequence[agent_file_alias.RelativePath] = ()
    template: Optional[agent_file_alias.FileContent] = None
    dependencies: Sequence[TargetLabel] = ()
    silent_dependencies: Sequence[TargetLabel] = ()
    star_dependencies: Sequence[TargetLabel] = ()
    feedback_dependencies: Sequence[TargetLabel] = ()
    guide_target: Optional[TargetLabel] = None
    verification_check: Optional[VerificationCommand] = None
    allows_step_mode: Optional[bool] = True


class BazelManifestLoader(InTier[SystemTier], Protocol):
    """Discovers and translates build system target manifests into runtime graph structures and node definitions."""

    def retrieve_manifest(self, node: dag_storage.DagNode) -> Optional[TargetManifest]:
        """
        COVERED:
        - MUST retrieve the manifest for the node.
          - Consequent knowledge: return TargetManifest record.

        DEFERRED:
        - Filesystem manifest discovery deferred to bazel_manifest_loader_impl.py.
        """
        _manifest: Optional[TargetManifest] = TargetManifest(
            label=TargetLabel(str(node.unit_address))
        )
        raise NotImplementedError

    def load_manifest(self, node: dag_storage.DagNode) -> None:
        """
        DEFERRED:
        - MUST resolve manifests into target nodes, node definitions, task prompts, and dependency graph edges.
        - MUST populate agent storage with resolved structures.
        - MUST resolve declared direct dependencies into dependency graph edges in agent storage.
        - MUST resolve declared silent dependencies as non-propagating dependencies in agent storage.
        - MUST synthesize definitions for declared dependencies lacking explicit manifests.
        - MUST synthesize promptless pass-through node definitions when a unit component type is not active for a role.
          - Deferred to bazel_manifest_loader_impl.py.
        """
        raise NotImplementedError
