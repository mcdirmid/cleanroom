<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:05:57Z
CHANGE: Drop stale template materialization content and state sandbox modification tracking per the high-level contract
CODE_HASH: 22c2c91c291a
SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
-->

# sandbox interface component

## Intent

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. If these capabilities are exposed as disconnected services, orchestrators must duplicate initialization logic and manually track workspace mutations. The sandbox interface component establishes a unified session coordination boundary that exposes session-wide file modification state.

Tracking session modification state lets outcome controls require documentation of changed files before a session concludes, keeping session conclusions honest about workspace mutations.

## Factored Contracts

### Typing

- An agent session's sandbox coordinates state for the agent session.
- An agent session's sandbox exposes whether workspace file modifications occurred during the session.

### Contracts

- An agent session's sandbox coordinates session state. [sandbox_coordinates_modification_tracking]
- The sandbox exposes whether workspace file modifications occurred during the session. [expose_modifications_occurred]

### Woven Contracts

- Workspace modification queries indicate whether files were changed during the active session. [sandbox_coordinates_modification_tracking, expose_modifications_occurred]

## Grounding

### Knowledge Provisions

- Exposes whether workspace file modifications occurred during the session. [modifications_status]

### Knowledge Requirements

- Determination of workspace file modification state.
  - Deferred: Delegated to session edit manager in implementation.
