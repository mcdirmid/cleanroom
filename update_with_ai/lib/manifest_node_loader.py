from typing import Protocol, TypeAlias, Sequence
from .build_graph_storage import BuildGraphStorage, NodeDefinition

ManifestContent: TypeAlias = str


class ManifestLoader(Protocol):
    def load_manifest(
        self, content: ManifestContent, storage: BuildGraphStorage
    ) -> Sequence[NodeDefinition]:
        ...

