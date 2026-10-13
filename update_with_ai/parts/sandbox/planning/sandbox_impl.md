<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T21:57:18Z
LAST_CHANGED: 2026-10-11T03:10:59Z
CHANGE: State modification reporting as a delegated report rather than a query
CODE_HASH: c80b3357a565
SPEC_QA_AUDIT: 2026-10-12T21:57:18Z
-->

# sandbox_impl implementation component

## Intent

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. The sandbox_impl implementation component establishes a unified session coordination boundary that exposes session-wide file modification state from the edit manager.

By delegating modification state to the edit manager, the implementation maintains consistent session state without duplicating storage logic.

## Factored Contracts

### Typing

- The sandbox coordinates workspace state for the active session.

### Contracts

- The sandbox reports whether workspace file modifications occurred during the session by delegating to the edit manager. [delegate_file_modifications]

### Woven Contracts

- Reporting session modifications retrieves modification state from the edit manager. [delegate_file_modifications, sandbox: [expose_modifications_occurred], sandbox_file_editor: [writes_occurred_true_on_diff, writes_occurred_false_on_match]]

## Grounding

### Knowledge Provisions

- Exposes whether workspace file modifications occurred during the session. [modifications_status]

### Inherited Deferred Requirements

- Determination of workspace file modification state.
  - Grounded: [sandbox_file_editor: [writes_occurred_status]]
