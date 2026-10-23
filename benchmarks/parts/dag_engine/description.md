# dag_engine

The `dag_engine` component realizes a generalized Directed Acyclic Graph (DAG) execution and wave scheduling engine.

## Capabilities

- **Graph Construction & Invariant Validation**: Add nodes and directed edges, detect cycles, find roots/leaves, and compute deterministic topological sorts.
- **Wave Scheduling**: Partition DAG nodes into concurrent execution waves respecting dependencies, priorities, and dynamic failure policies (`FAIL_FAST`, `CONTINUE_ON_ERROR`, `SKIP_DOWNSTREAM`).
- **Concurrent Execution & Telemetry**: Execute independent node actions concurrently under configurable concurrency limits, handling timeouts, retries, cancellation, and critical path metrics.
