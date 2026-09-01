<!-- Dependencies (md files to read alongside this one):
  - virtual_file_name.md
  - node_id_utils.md
  - dag_storage.md
  - sandbox.md
  - build_graph_storage.md
  - build_agent_config.md
-->

# Interface LLS: manifest_node_loader

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence
from build_graph_storage import BuildGraphStorage, NodeDefinition

ManifestContent: TypeAlias = str

class ManifestLoader(Protocol):
    def load_manifest(self, content: ManifestContent, storage: BuildGraphStorage) -> Sequence[NodeDefinition]: ...
```

- `ManifestContent` → corresponds to *manifest*: build-time metadata written by the build system describing a target's source files, silent source files, dependencies, silent dependencies, guides, templates, verification checks, and execution settings.
- `ManifestLoader` → corresponds to *manifest loader*: a service that resolves workspace target manifests into graph structures and *sandbox configurations*.

## Term definitions

- **manifest** → the `ManifestContent` alias
- **node definition** → the `NodeDefinition` alias from build_graph_storage
- **manifest loader** → term definition: a service that resolves workspace target manifests into graph structures and *sandbox configurations*

## Component-Provided Operations

### `load_manifest`

```python
def load_manifest(self, content: ManifestContent, storage: BuildGraphStorage) -> Sequence[NodeDefinition]: ...
```

**Purpose:** (ManifestLoader) Parses a manifest and populates node definitions, dependencies, task prompts, config targets, and sandbox permissions into build graph storage.

**Preconditions:**
- `content` is valid manifest syntax.

**Postconditions:**
- Normalizes target labels to canonical `NodeId` using node identifier utilities.
- Resolves declared source files and templates into read-write files and startup templates in sandbox configurations.
- Resolves declared silent source files into read-write files in sandbox configurations while excluding them from dependent read-only files.
- Resolves declared direct dependencies into declared read-only files, and star dependencies into transitive read-only file closures in sandbox configurations.
- Resolves declared silent dependencies as non-propagating dependencies in build graph storage while excluding their source files from read-only files.
- Resolves declared guide targets into task guides and verification checks into sandbox configurations.
- Resolves declared feedback dependencies into blame targets mapped to their owning dependency nodes in sandbox configurations.
- Generates sandbox configurations with minimally disambiguated virtual file names.
- Synthesizes node definitions for declared dependencies lacking explicit manifests.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *manifest loader* loads *manifests* to resolve target *nodes*, *dependencies*, *node definitions*, *task prompts*, *config targets*, and *sandbox configurations* using a *node identifier utility*, populating a *build graph storage*."

## Invariants

- Canonical node IDs generated from manifests are deterministic and collision-free.
- Transitive closures for star dependencies include all reachable source files of dependencies.
- Disambiguated virtual file names use the shortest unique path suffix across all accessible workspace files.
