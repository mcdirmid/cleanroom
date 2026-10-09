<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-06T12:35:00Z
CHANGE: update to planning grounding format
CODE_HASH: 5aa09c578841
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# sandbox_impl implementation component

imports: sandbox_file_editor
implements: sandbox

## Intent

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. The sandbox_impl implementation component establishes a unified session coordination boundary that exposes session-wide file modification state from the edit manager.

By querying modification state from the edit manager, the implementation maintains consistent session state without duplicating storage logic.

## Factored Contracts

### Typing

- A sandbox implementation coordinates file modification tracking within the agent session tier.

### Contracts

- Querying file modifications delegates to the edit manager. [delegate_file_modifications]

### Woven Contracts

- Querying session modifications retrieves modification state from the edit manager. [delegate_file_modifications, sandbox: [expose_modifications_occurred], sandbox_file_editor: [writes_occurred_true_on_diff, writes_occurred_false_on_match]]

## Grounding

### Knowledge Provisions

- Exposes whether workspace file modifications occurred during the session. [modifications_status]

### Inherited Deferred Requirements

- Determination of workspace file modification state.
  - Grounded: [sandbox_file_editor: [writes_occurred_status]]
