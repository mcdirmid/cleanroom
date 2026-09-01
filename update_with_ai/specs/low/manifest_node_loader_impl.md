<!-- Dependencies (md files to read alongside this one):
  - virtual_file_name.md
  - node_id_utils.md
  - dag_storage.md
  - sandbox.md
  - build_graph_storage.md
  - build_agent_config.md
  - manifest_node_loader.md
  - json_manifest_ext.md
-->

# Implementation LLS: manifest_node_loader_impl

## Data Types
```python
from virtual_file_name import VirtualFileMapperFactory
from node_id_utils import NodeIdUtils
from manifest_node_loader import ManifestLoader
from json_manifest_ext import JsonManifest

class ManifestLoaderImpl(ManifestLoader):
    def __init__(self, node_id_utils: NodeIdUtils, virtual_file_mapper_factory: VirtualFileMapperFactory) -> None: ...
```

## Behavioral Description

- Parses manifest content into `JsonManifest` records using `parse_json_manifest` from `json_manifest_ext`.
- Normalizes manifest node references (`label`, `deps`, `silent_deps`, `star_deps`, `feedback_deps`, `guide`, `config`) into canonical `NodeId` values using `node_id_utils.canonicalize_node_id`.
- Resolves manifest file paths (`src`, `template`, `silent_srcs`) by extracting the target's package directory via `node_id_utils.extract_node_directory` and joining relative filesystem paths.
- For a target node: maps resolved `src`, `template`, and `silent_srcs` into writable workspace files and startup template entries in `SandboxConfig`.
- For dependencies (`deps`, `star_deps`): loads each dependency's manifest (via `locate_manifest_file` and `load_json_manifest` or from storage), extracts its declared `src`, resolves it against that dependency's package directory, and registers it as a read-only file in `SandboxConfig`. For star dependencies, recursively traverses and includes the transitive source file closure.
- For silent dependencies (`silent_deps`): registers them as non-propagating dependencies in `BuildGraphStorage`, excluding their source files from read-only files.
- For guide targets (`guide`): retrieves the referenced guide node's declared `src` resolved against its package directory and constructs the `TaskGuide`, excluding step-mode guide source files from read-only files.
- For feedback dependencies (`feedback_deps`): maps each dependency's resolved declared `src` to a blame target associated with that dependency's canonical `NodeId` in `SandboxConfig`.
- Derives `VirtualFileMapping` for all accessible workspace files using `virtual_file_mapper_factory.create_mapper`.
- Synthesizes empty `NodeDefinition` records for referenced dependency targets lacking manifests.
- Registers node definitions, dependencies, and sandbox configurations into `storage`.

## Invariants

- Canonical labels are produced exclusively through `node_id_utils`.
- Silent dependencies are stored as non-propagating dependencies without read-only source exposure.
- Star dependencies expand to complete transitive source closures as read-only files.
- Path minimization derives the shortest unique suffix for colliding virtual file names.
