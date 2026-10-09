<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-06T12:35:00Z
CHANGE: update to planning grounding format
CODE_HASH: 88eda6434a81
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# sandbox interface component

## Intent

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. If these capabilities are exposed as disconnected services, orchestrators must duplicate initialization logic, manage race conditions during startup template creation, and manually track workspace mutations. The sandbox interface component establishes a unified session coordination boundary that ensures template materialization precedes agent execution and exposes session-wide file modification state.

By coordinating starter template instantiation for missing read-write files and exposing whether workspace file modifications occurred, the sandbox provides orchestrators with clear environment guarantees.

## Factored Contracts

### Typing

- A sandbox coordinates file modification tracking within the agent session tier.

### Contracts

- An agent session's sandbox coordinates file modification tracking. [sandbox_coordinates_modification_tracking]
- The sandbox exposes whether workspace file modifications occurred during the session. [expose_modifications_occurred]

### Woven Contracts

- Workspace modification queries indicate whether files were changed during the active session. [sandbox_coordinates_modification_tracking, expose_modifications_occurred]

## Grounding

### Knowledge Provisions

- Exposes whether workspace file modifications occurred during the session. [modifications_status]

### Knowledge Requirements

- Determination of workspace file modification state.
  - Deferred: Delegated to session edit manager in implementation.
