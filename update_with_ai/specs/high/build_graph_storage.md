# build_graph_storage

imports: dag_storage, sandbox, virtual_file_name, build_agent_config
types from dag_storage: dag storage, node, dependency, propagating dependency, reverse dependency, message, pending message
types from sandbox: sandbox configuration
types from virtual_file_name: virtual file name
types from build_agent_config: config target

## Purpose

Stores workspace target graph relationships and per-node sandbox configurations populated from target manifests.

Task execution across structured projects requires maintaining target dependency relationships and sandbox execution contexts. Build graph storage preserves propagating and non-propagating graph relationships, task prompts, and isolated sandbox configurations populated from workspace target manifests.

## Types

- A *build graph storage* is a *dag storage* backed by workspace build target manifests
- A *node definition* is metadata describing target *sandbox configurations*, *task prompts*, *config targets*, guides, verification checks, and dependency blame mappings for a *node*
- A *task prompt* is an instruction describing the work required to clean a *node*

## Behavior

- A *build graph storage* maintains *nodes*, *dependencies*, *reverse dependencies*, and *pending messages* from workspace targets.
- A *build graph storage* provides *task prompts*, *node definitions*, and *sandbox configurations* for declared *nodes*.
- Declared dependencies marked propagating mark dependent *nodes* dirty when changed.
