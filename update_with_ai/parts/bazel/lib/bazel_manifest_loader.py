# Requirements specified in bazel_manifest_loader.pyi
from typing import Optional, Protocol, Sequence
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage


class TargetManifest(str):
    pass


Manifest = TargetManifest


class BazelManifestLoader(Protocol):
    def get_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[TargetManifest]: ...

    def load_manifest(
        self, content: TargetManifest, storage: agent_storage.AgentStorage
    ) -> Sequence[agent_storage.NodeDefinition]: ...
