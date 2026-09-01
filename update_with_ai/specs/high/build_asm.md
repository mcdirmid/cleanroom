# build_asm

imports: build_runner, build_graph_storage, agent_node_cleaner, dag_cleaner, runner_logger, manifest_node_loader
types from build_runner: build runner
types from build_graph_storage: build graph storage
types from agent_node_cleaner: agent node cleaner
types from dag_cleaner: dag cleaner
types from runner_logger: runner logger
types from manifest_node_loader: manifest loader
implements: build runner

## Behavior

- A *build runner* is assembled from concrete implementations of *build graph storage*, *manifest loader*, *agent node cleaner*, *dag cleaner*, and *runner logger*.
- The assembled *build runner* coordinates topological cleaning passes by delegating target loading to *manifest loader*, graph storage to *build graph storage*, node cleaning to *agent node cleaner* wired to the *build graph storage*, topological ordering to *dag cleaner*, and routing execution transcripts to *runner logger* in the workspace directory.
