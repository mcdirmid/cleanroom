# task_queue

The `task_queue` benchmark realizes a minimal decoupled task orchestration system with two inter-dependent implementation components for evaluating multi-component agent synthesis and cross-component collaboration.

## Architecture

The benchmark contains two interface components and two concrete implementation components:

1. **`task_queue`**: Defines the abstract `TaskQueue` protocol and queue exception hierarchy (`QueueError`, `QueueEmptyError`, `QueueFullError`).
2. **`task_queue_impl`**: Realizes the FIFO task queue using `collections.deque` with bounded capacity, dispatching tasks to the collaborator worker and tracking completed outcomes (~35 LOC).
3. **`task_worker`**: Defines the abstract `TaskWorker` protocol and worker exception hierarchy (`WorkerError`).
4. **`task_worker_impl`**: Realizes the task execution worker, transforming task payloads, maintaining execution counters, and reporting task completion callbacks back to the task queue (~30 LOC).

## Interdependence

The two implementation components are mutually reliant:
- When `TaskQueue.dispatch()` is invoked, it delegates task execution to `TaskWorker.execute(task_id, payload)`.
- When `TaskWorker.execute(...)` processes a workload, it invokes `TaskQueue.complete(task_id, outcome)` to report task results.
- `TaskWorker.fetch_and_execute()` coordinates pull-based task processing by invoking `TaskQueue.dispatch()`.
