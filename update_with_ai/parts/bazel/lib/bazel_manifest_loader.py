from typing import Optional, Protocol, Sequence
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage


class Manifest(str):
    pass


class BazelManifestLoader(Protocol):
    def get_manifest(self, node: dag_storage.Node) -> Optional[Manifest]: ...

    def load_manifest(
        self, content: Manifest, storage: agent_storage.AgentStorage
    ) -> Sequence[agent_storage.NodeDefinition]: ...
