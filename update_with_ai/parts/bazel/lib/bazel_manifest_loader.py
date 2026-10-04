# Requirements specified in bazel_manifest_loader.pyi
from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage

TargetLabel = NewType("TargetLabel", str)
VerificationCommand = NewType("VerificationCommand", str)


class _Types:
    RelativePath = NewType("RelativePath", str)
    FileTemplate = NewType("FileTemplate", str)


agent_file_alias = _Types
sandbox_file_editor = _Types


@dataclass(frozen=True)
class TargetManifest:
    label: TargetLabel
    task_prompt: Optional[agent_storage.TaskPrompt] = None
    source_file: Optional[agent_file_alias.RelativePath] = None
    silent_source_files: Sequence[agent_file_alias.RelativePath] = ()
    template: Optional[sandbox_file_editor.FileTemplate] = None
    dependencies: Sequence[TargetLabel] = ()
    silent_dependencies: Sequence[TargetLabel] = ()
    star_dependencies: Sequence[TargetLabel] = ()
    feedback_dependencies: Sequence[TargetLabel] = ()
    guide_target: Optional[TargetLabel] = None
    verification_check: Optional[VerificationCommand] = None


class BazelManifestLoader(Protocol):
    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[TargetManifest]: ...

    def load_manifest(self, node: dag_storage.DagNode) -> None: ...
