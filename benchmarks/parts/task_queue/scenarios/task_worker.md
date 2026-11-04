# Concrete scenarios for task_worker interface

## Scenario 1 — Execute task and return outcome

Given: A newly initialized task worker.

1. Execute task `task_1` with payload `ping`.
Observed: Returned outcome is `PROCESSED:PING`.

2. Execute task `task_2` with payload `pong`.
Observed: Returned outcome is `PROCESSED:PONG`.

## Scenario 2 — Fetch and execute pending task from queue

Given: A task worker and a collaborator task queue containing pending task `job_42` with payload `compute`.

1. Fetch and execute next task from the queue.
Observed: Returned task identifier is `job_42`.

## Scenario 3 — Worker error on empty fetch

Given: A task worker and an empty task queue with 0 pending tasks.

1. Fetch and execute next task.
Observed: A worker error is raised.

## Scenario 4 — Worker execution exception on queue unavailable

Given: A task worker and a collaborator task queue seeded or configured as unavailable.

1. Fetch and execute next task.
Observed: A worker execution exception is raised.

## Scenario 5 — Seeding task failure raises worker execution exception

Given: A task worker state machine or fake seeded to fail on `fail_task`.

1. Execute task `fail_task` with payload `error_payload`.
Observed: A worker execution exception is raised.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:10:00Z
LAST_CHANGED: 2026-11-03T23:10:00Z
CHANGE: Streamline worker interface scenarios by moving telemetry and reset to implementation
-->
