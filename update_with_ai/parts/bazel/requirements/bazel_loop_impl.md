# bazel_loop_impl implementation component

imports: bazel_manifest_loader, loop, loop_cleaner, loop_node_cleaner, dag_storage, runner_logger
implements: loop

## Assumptions and Requirements

### Requirements

1. Target labels are resolved against workspace directories or runfiles trees to populate graph storage.
2. Cleaning halts immediately and produces a failing build result if node cleaning fails, if any reachable node in the target subgraph remains dirty after cleaning, or if an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.
3. Telemetry capturing execution events, pass duration, and build outcome is streamed to standard output and transcript files.

## Grounding Facts

### Knowledge Needed

- Target labels.
- Workspace root and runfiles tree paths.
- Graph storage and subgraph state from `dag_storage`.
- Build outcome and execution events.

### Actions Needed

- Resolve target labels and load manifest into graph storage via `bazel_manifest_loader`.
- Execute cleaning pass via `loop_cleaner`.
- Evaluate subgraph cleanliness and construct build result.
- Stream telemetry events to `runner_logger`.
