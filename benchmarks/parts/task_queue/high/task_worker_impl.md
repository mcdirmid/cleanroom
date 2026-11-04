# task_worker_impl implementation component

imports: task_queue
implements: task_worker

## Purpose

The task_worker_impl implementation component realizes a concrete task execution worker that processes payloads, tracks telemetry, and reports completion back to the task queue.

Decoupled task execution requires workers that transform payloads, manage busy state transitions, and report completion back to the queue service. Without consistent completion callbacks, task queues lose track of workload status. The task_worker_impl implementation component provides deterministic payload transformation, execution telemetry, and completion reporting across task lifecycles.

**Out of scope:** The task_worker_impl implementation component does not manage FIFO queue ordering, capacity limits, or persistent job storage; these are handled by other components.

**Delegated:** Task queueing, dispatch ordering, and result storage are delegated to task_queue.

## Types and Behavior

A system's *concrete task worker* realizes the task worker protocol within the system lifecycle tier, maintaining an internal processed counter, a last processed task identifier, a busy flag, and a set of failing task identifiers. The worker exposes its total *processed count* indicating successfully completed tasks, the *last task identifier* processed, and whether it *is busy* actively executing a task.

Executing sets busy state, computes the uppercase string outcome prefixed with the processed marker, calls the task queue singleton to complete the task with the computed outcome, updates the last task identifier, increments the processed counter by one, clears busy state, and returns the outcome string; if task queue completion raises queue unavailable exception or if the task identifier is marked for failure, executing clears busy state and raises worker execution exception. Fetching and executing delegates to the task queue singleton to dispatch the next pending task and executes it, raising worker error if queue dispatch encounters an empty queue, and raising worker execution exception if queue dispatch or completion encounters a queue unavailable exception. Resetting clears the processed counter to zero, clears the last task identifier, and resets busy state. The worker supports *setting task failures*, updating the set of failing task identifiers for operational verification.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:10:00Z
LAST_CHANGED: 2026-11-03T23:10:00Z
CHANGE: Realize worker execution with processed counter, last task id telemetry, and busy state
SPEC_QA_AUDIT: 2026-11-03T23:10:00Z
-->
