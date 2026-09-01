# build_runner_impl

imports: dag_storage, dag_cleaner, dag_node_cleaner, runner_logger, manifest_node_loader, build_runner
types from dag_storage: dag storage, node, message, pending message
types from dag_cleaner: dag cleaner
types from dag_node_cleaner: node cleaner, change message, feedback message
types from runner_logger: runner logger, log event
types from manifest_node_loader: manifest loader
types from build_runner: build runner, cleaning pass, build result
implements: build runner

## Behavior

- A *build runner* resolves target labels and loads workspace target graphs into *dag storage* using a *manifest loader*.
- Marking a *node* dirty in a *build runner* injects a *change message* with text set to check.
- Injecting feedback or broadcasting changes transmits caller-provided message content.
- A *build runner* halts cleaning and reports failure if a *node* cleaning fails or a cycle is encountered.
- When an agent session concludes, the *build runner* logs cumulative token usage and pass duration.
