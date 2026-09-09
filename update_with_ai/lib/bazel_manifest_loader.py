from typing import Optional, Protocol, Sequence
from . import bazel_graph_storage
from . import dag_storage

class Manifest(str):
    pass

class BazelManifestLoader(Protocol):
    def get_manifest(self, node: dag_storage.Node) -> Optional[Manifest]:
        ...

    def load_manifest(
        self, content: Manifest, storage: bazel_graph_storage.BazelGraphStorage
    ) -> Sequence[bazel_graph_storage.NodeDefinition]:
        ...
