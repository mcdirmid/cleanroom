# antigravity_sandbox_gate interface component

imports: antigravity_run_logger

## Assumptions and Requirements

### Requirements

1. A gating decision record represents the outcome of evaluating a tool call, exposing a decision status, a reason, and an optional overwrite mapping.
2. The antigravity sandbox gate evaluates a raw JSON payload string and returns a gating decision.
3. The antigravity sandbox gate inspects a command line and determines whether execution is permitted.
4. The antigravity sandbox gate inspects a command line and determines whether coordinator execution is permitted.
5. The antigravity sandbox gate verifies whether a conversation identifier belongs to a coordinator subagent.
6. The antigravity sandbox gate verifies whether a conversation identifier belongs to a role worker subagent.
7. The antigravity sandbox gate associates a worker identifier with a session identifier.
8. The antigravity sandbox gate disassociates a worker identifier.
9. The antigravity sandbox gate returns all active worker session associations.

## Grounding Facts

### Knowledge Needed

- Tool call JSON payload.
- Command-line permission whitelists.
- Caller subagent identity.
- Worker session associations.

### Actions Needed

- Parse incoming tool payload.
- Evaluate command line against permission rules.
- Verify caller identity.
- Manage worker session associations.
