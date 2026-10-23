# dag_engine_lite

The `dag_engine_lite` component realizes a lightweight, purely synchronous Directed Acyclic Graph (DAG) execution and wave scheduling engine without concurrency.

## Capabilities

- **Graph Construction & Invariant Validation**: Add nodes and directed edges, detect cycles, find roots/leaves, and compute deterministic topological sorts.
- **Sequential Wave Scheduling**: Partition DAG nodes into deterministic execution waves respecting dependencies, priorities, and dynamic failure policies (`FAIL_FAST`, `CONTINUE_ON_ERROR`, `SKIP_DOWNSTREAM`).
- **Synchronous Execution & Telemetry**: Execute task actions sequentially in topological wave order, handling retries and compiling critical path metrics into execution reports.
