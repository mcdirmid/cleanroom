# Concrete scenarios for task_worker_impl implementation

## Reused from the interface

### Scenario 1 — Execute task and return outcome

Given: A newly initialized task worker.

1. Execute task `task_1` with payload `ping`.
Observed: Returned outcome is `PROCESSED:PING`.
Realized by: Uppercasing payload, notifying task queue singleton to record outcome, and incrementing processed count.

2. Execute task `task_2` with payload `pong`.
Observed: Returned outcome is `PROCESSED:PONG`.
Realized by: Uppercasing payload, notifying task queue singleton to record outcome, and updating last task identifier.

### Scenario 2 — Fetch and execute pending task from queue

Given: A task worker and a collaborator task queue containing pending task `job_42` with payload `compute`.

1. Fetch and execute next task from the queue.
Observed: Returned task identifier is `job_42`.
Realized by: Resolving task queue singleton, calling dispatch, and executing the returned task.

### Scenario 3 — Worker error on empty fetch

Given: A task worker and an empty task queue with 0 pending tasks.

1. Fetch and execute next task.
Observed: A worker error is raised.
Realized by: Catching queue empty error from task queue dispatch and raising worker error.

### Scenario 4 — Worker execution exception on queue unavailable

Given: A task worker and a collaborator task queue seeded or configured as unavailable.

1. Fetch and execute next task.
Observed: A worker execution exception is raised.
Realized by: Catching queue unavailable exception from task queue dispatch or completion, clearing busy state, and raising worker execution exception.

### Scenario 5 — Seeding task failure raises worker execution exception

Given: A task worker state machine or fake seeded to fail on `fail_task`.

1. Execute task `fail_task` with payload `error_payload`.
Observed: A worker execution exception is raised.
Realized by: Checking failing task set, clearing busy state, and raising worker execution exception through transition seeding.

## Implementation-only

### Scenario 6 — Telemetry tracking and reset

Given: A newly initialized concrete task worker with processed count 0, last task identifier None, and is_busy False.

1. Inspect initial worker telemetry.
Observed: Processed count is 0, last task identifier is None, and is_busy is False.
Realized by: Reading internal counter, last task identifier, and busy state.

2. Execute task `task_1` with payload `hello`.
Observed: Processed count becomes 1, last task identifier is `task_1`, and is_busy is False.
Realized by: Updating internal telemetry during task execution.

3. Reset the worker.
Observed: Processed count becomes 0, last task identifier becomes None, and is_busy is False.
Realized by: Re-initializing processed count to zero, last task identifier to None, and busy flag to False.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:10:00Z
LAST_CHANGED: 2026-11-03T23:10:00Z
CHANGE: Move telemetry and reset scenarios into implementation-only
-->
