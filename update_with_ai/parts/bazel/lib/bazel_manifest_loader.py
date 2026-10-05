# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T05:58:29Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 92635c49cb52
# --- END CLEANROOM METADATA ---

# Requirements specified in bazel_manifest_loader.pyi
from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage

TargetLabel = NewType("TargetLabel", str)
VerificationCommand = NewType("VerificationCommand", str)


class _Types:
    RelativePath = NewType("RelativePath", str)
    FileContent = NewType("FileContent", str)


agent_file_alias = _Types


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


class BazelManifestLoader(Protocol):
    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[TargetManifest]: ...

    def load_manifest(self, node: dag_storage.DagNode) -> None: ...
