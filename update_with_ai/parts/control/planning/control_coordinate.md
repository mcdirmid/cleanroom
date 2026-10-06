# control_coordinate interface component

imports: agent_session, dag_storage, control_verification, control_work_scheduler, control_submit, control_attribution, agent_node_config, agent_file_alias

## Intent

The control_coordinate interface component defines contracts for central session coordination, target state tracking, default target resolution, and unified control tool dispatching.

Autonomous tools require a consistent state coordinator so that nodes being worked on, checked, submitted, or blamed remain synchronized across successive tool calls. The session coordinator acts as the single source of truth for session target states, resolves default targets when tool arguments are omitted, and dispatches get_work, check_files, submit, blame, and fail requests to specialized control services.

## Factored Contracts

### Typing

- A target state represents an open, clean, failed, or attributed state.
- A control dispatch outcome reports success status, outcome message, and remaining open targets.
- A session coordinator operates within the agent session lifecycle tier.

### Contracts

- A session coordinator registers active targets and tracks their associated target states. [track_target_states]
- A session coordinator resolves the default target when omitted based on open target count or last touched file. [resolve_default_target_contract]
- A session coordinator dispatches work discovery using subgraph or directory parameters. [dispatch_get_work]
- A session coordinator dispatches verification evaluation for a specific target or all open targets. [dispatch_check_files]
- A session coordinator dispatches target submission through the submission coordinator. [dispatch_submit]
- A session coordinator dispatches defect attribution through the attribution coordinator. [dispatch_blame]
- A session coordinator dispatches failure recording through the attribution coordinator. [dispatch_fail]
- A session coordinator queries remaining open targets in the session. [query_open_targets]

### Woven Contracts

- When check files is invoked without a target argument, the coordinator queries all open targets and evaluates verification across each open target. [query_open_targets, dispatch_check_files]
- When submit succeeds for a target, the coordinator updates that target's state to clean and reports remaining open targets. [dispatch_submit, track_target_states, query_open_targets]
- When blame or fail occurs for a target, the coordinator updates target states and marks in-batch dependent nodes as failed. [dispatch_blame, dispatch_fail, track_target_states, query_open_targets]

## Grounding

### Knowledge Provisions

- Session target state tracking and active node registry. [session_target_registry]
- Default target resolution for ambiguous or omitted tool invocations. [default_target_resolution]
- Central dispatching facade for control operations across verification, work scheduling, submission, and attribution. [control_dispatch_facade]

### Knowledge Requirements

- Registration and tracking of active session targets across target states.
  - Deferred: Delegated to in-memory node state dictionary in implementation.
- Resolution of default targets based on open counts or file modification timestamps.
  - Deferred: Delegated to default target resolution algorithm in implementation.
- Work discovery dispatching to work scheduler.
  - Deferred: Delegated to WorkScheduler from control_work_scheduler in implementation.
- Verification evaluation dispatching across single or all open targets.
  - Deferred: Delegated to VerificationEvaluator from control_verification in implementation.
- Target submission dispatching through submission coordinator.
  - Deferred: Delegated to SubmissionCoordinator from control_submit in implementation.
- Defect attribution and failure dispatching through attribution coordinator.
  - Deferred: Delegated to AttributionCoordinator from control_attribution in implementation.
