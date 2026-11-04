# Cleanroom Benchmark Suites

This directory contains standalone benchmark targets used for measuring model efficiency, token consumption, context caching economics, and multi-agent synthesis under the Cleanroom methodology.

Each sub-package in `benchmarks/parts/` defines an isolated benchmark evaluation target. The benchmark suite name is identical to the part's directory name.

---

## Available Benchmark Suites

| Suite Name | Part Directory | Target Address | Archetype | Description |
| :--- | :--- | :--- | :--- | :--- |
| `dag_engine` | `benchmarks/parts/dag_engine` | `//benchmarks/parts/dag_engine#dag_engine_impl` | Graph Traversal / Wave Execution Engine | Concurrent DAG execution engine with wave scheduling, cycle detection, and failure policies. |
| `dag_engine_lite` | `benchmarks/parts/dag_engine_lite` | `//benchmarks/parts/dag_engine_lite#dag_engine_lite_impl` | Graph Traversal / Synchronous Scheduler | Purely synchronous, lightweight DAG execution and topological wave scheduler without concurrency. |
| `semver_solver` | `benchmarks/parts/semver_solver` | `//benchmarks/parts/semver_solver#semver_solver_impl` | Constraint Satisfaction / Dependency Solver | Strict SemVer 2.0.0 parser, precedence comparator, range matching engine, and backtracking dependency resolution solver. |
| `semver_solver_multi` | `benchmarks/parts/semver_solver_multi` | `//benchmarks/parts/semver_solver_multi#dependency_solver_impl` | Constraint Satisfaction / Multi-Component Dependency Solver | Decomposed SemVer 2.0.0 suite with three interface components (`semver_core`, `semver_range`, `dependency_solver`) and three implementation components (`semver_core_impl`, `semver_range_impl`, `dependency_solver_impl`). |
| `lru_cache` | `benchmarks/parts/lru_cache` | `//benchmarks/parts/lru_cache#lru_cache_impl` | Bounded Memory Cache / State Machine | Lightweight Least-Recently-Used cache with recency promotion, dynamic capacity resizing, overflow eviction, and operational telemetry (~50 LOC). |
| `ring_buffer` | `benchmarks/parts/ring_buffer` | `//benchmarks/parts/ring_buffer#ring_buffer_impl` | Circular FIFO Queue / Ring Buffer | Ultra-minimal smoke test benchmark: bounded circular FIFO buffer with overwrite eviction on capacity saturation (~30 LOC). |
| `task_queue` | `benchmarks/parts/task_queue` | `//benchmarks/parts/task_queue#task_queue_impl` | Producer-Consumer / Interdependent Queue & Worker | Minimal dual-component benchmark: bounded task queue and execution worker with mutual dispatch and completion callback contracts (~35 LOC each). |

---

## CLI Usage

Run a benchmark flight against a specific suite:

```bash
# Run dag_engine with Gemini Flash
uv run autofab benchmark --suite=dag_engine --models=gemini-flash --harness=antigravity

# Run dag_engine_lite with Gemini Flash
uv run autofab benchmark --suite=dag_engine_lite --models=gemini-flash --harness=antigravity

# Run semver_solver with Gemini Flash
uv run autofab benchmark --suite=semver_solver --models=gemini-flash --harness=antigravity

# Run all benchmark suites
uv run autofab benchmark --suite=all --models=gemini-flash --harness=antigravity
```

### Options

- `--suite`: Target benchmark suite (`dag_engine`, `dag_engine_lite`, `semver_solver`, `semver_solver_multi`, `lru_cache`, `ring_buffer`, `task_queue`, or `all`).
- `--models`: Comma-separated list of model identifiers or profiles (e.g. `gemini-flash`, `deepseek-flash`, `qwen-moe-q6`).
- `--harness`: Execution harness (`antigravity`, `loop`, `dsh`, or `simulation`).
- `--dry-run`: Validate parameters and configuration without executing model API calls.
- `--output`: Path to write the generated markdown flight report.
