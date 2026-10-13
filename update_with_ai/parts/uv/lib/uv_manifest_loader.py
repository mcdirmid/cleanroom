# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-11T05:09:58Z
# CHANGE: Use the real cross-part file alias module for the declared interface field types instead of a private fallback container
# CODE_HASH: 17f30c9d6a4a
# --- END CLEANROOM METADATA ---

from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage

TargetLabel = NewType("TargetLabel", str)
VerificationCommand = NewType("VerificationCommand", str)


@dataclass(frozen=True)
class TargetManifest:
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


class UvManifestLoader(Protocol):
    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[TargetManifest]: ...

    def load_manifest(self, node: dag_storage.DagNode) -> None: ...
