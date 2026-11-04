# task_worker interface component

## Intent

Decoupled service architectures separate task queuing from worker execution logic. The task_worker interface component defines abstract protocols and error representations for workload execution, operational exception propagation, and completion reporting.

By establishing strict execution contracts, deterministic payload transformations, operational exception handling, and callback-based lifecycle tracking, the component guarantees consistent execution semantics while keeping queue scheduling, storage mechanics, and telemetry tracking outside its boundary.

## Factored Contracts

### Typing

- A worker error specializes specification error as a base exception.
- A worker execution exception specializes specification exception with a message argument.
- A task worker executes tasks and coordinates with the task queue.

### Contracts

- Executing a task transforms the payload into a completed outcome string. [transform_payload_to_outcome]
- Executing a task reports completion to the task queue. [notify_queue_on_task_completion]
- If collaborator completion raises queue unavailable exception, executing raises worker execution exception. [handle_queue_unavailable_on_execute]
- Executing a task returns the computed outcome string. [return_computed_outcome_on_execution]
- Fetching and executing requests the next pending task from the task queue and executes it. [fetch_task_from_queue_and_execute]
- If collaborator dispatch raises queue empty error, fetching and executing raises worker error. [raise_worker_error_on_empty_fetch]
- If collaborator dispatch or completion raises queue unavailable exception, fetching and executing raises worker execution exception. [handle_queue_unavailable_on_fetch]
- Fetching and executing returns the dispatched task identifier. [return_dispatched_id_on_fetch]
- Seeding task failures configures state machines and fakes to raise worker execution exception on designated tasks. [seed_task_failure_in_fakes]

### Woven Contracts

- Payload transformation, queue notification, and outcome computation coordinate to deliver deterministic task execution. [transform_payload_to_outcome, notify_queue_on_task_completion, return_computed_outcome_on_execution]
- Queue dispatch fetching and task execution coordinate to enable pull-based worker processing. [fetch_task_from_queue_and_execute, return_dispatched_id_on_fetch, raise_worker_error_on_empty_fetch]
- Collaborator queue unavailability triggers worker execution exception across execution paths. [handle_queue_unavailable_on_execute, handle_queue_unavailable_on_fetch]

## Grounding

### Knowledge Provisions

- Task worker execution service and dispatch coordination. [task_worker_core_service]

### Knowledge Requirements

- Deterministic payload transformation logic.
  - Deferred: Realized by string transformation in task_worker_impl.
- Collaborator task queue completion callback and dispatch protocol.
  - Deferred: Realized by queue singleton coordination in task_worker_impl.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:10:00Z
LAST_CHANGED: 2026-11-03T23:10:00Z
CHANGE: Streamline worker interface contracts by moving telemetry and busy state to implementation
SPEC_QA_AUDIT: 2026-11-03T23:10:00Z
-->
