# build_graph_storage_impl

imports: dag_storage, sandbox, virtual_file_name, build_graph_storage, build_message_store
types from dag_storage: dag storage, node, dependency, propagating dependency, reverse dependency, message, pending message
types from sandbox: sandbox configuration
types from virtual_file_name: virtual file name
types from build_graph_storage: build graph storage, node definition, task prompt
types from build_message_store: build message store
implements: build graph storage

## Behavior

- A *build graph storage* stores *node definitions* and graph relationships populated from target manifests.
- A *build graph storage* delegates durable persistence of *pending messages* and *reverse dependencies* to a *build message store*.
- A *build graph storage* maintains in-memory *node definitions*, *task prompts*, and *sandbox configurations* mapped to *nodes*.
- Virtual file mappings assign distinct *virtual file names* for all declared readable and writable files of a *node*.
- Propagating dependencies exclude silent dependencies declared on a *node*.
