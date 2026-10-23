from support.lib.lifecycle import Singleton, SystemTier
from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from update_with_ai.parts.agent.lib import file_alias
from update_with_ai.parts.agent.lib import node_storage
from update_with_ai.parts.dag.lib import dag_storage

TargetLabel = NewType("TargetLabel", str)
VerificationCommand = NewType("VerificationCommand", str)


# Contract: build artifact carrying node references and file paths for a workspace target
@dataclass(frozen=True)
class TargetManifest:
    label: TargetLabel
    task_prompt: Optional[node_storage.TaskPrompt] = None
    source_file: Optional[file_alias.RelativePath] = None
    silent_source_files: Sequence[file_alias.RelativePath] = ()
    template: Optional[file_alias.FileContent] = None
    dependencies: Sequence[TargetLabel] = ()
    silent_dependencies: Sequence[TargetLabel] = ()
    star_dependencies: Sequence[TargetLabel] = ()
    feedback_dependencies: Sequence[TargetLabel] = ()
    guide_target: Optional[TargetLabel] = None
    verification_check: Optional[VerificationCommand] = None
    allows_step_mode: Optional[bool] = True
    verification_success_message: Optional[str] = None


class UvManifestLoader(Singleton[SystemTier], Protocol):
    # Contract: retrieve target manifest for a node
    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[TargetManifest]: ...

    # Contract: resolve manifests into target nodes, definitions, and prompts
    def load_manifest(self, node: dag_storage.DagNode) -> None: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:09:58Z
# CHANGE: Use the real cross-part file alias module for the declared interface field types instead of a private fallback container
# --- END CLEANROOM METADATA ---
