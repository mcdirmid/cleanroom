# antigravity_run_logger interface component

## Assumptions and Requirements

### Requirements

1. An antigravity log event record represents a captured execution action, exposing an event name, a source, and a summary.
2. The antigravity run logger records an event name, a source, and a summary for an execution action.
3. The antigravity run logger associates a conversation identifier with a role slug.
4. The antigravity run logger converts a role label into a safe identifier string.

## Grounding Facts

### Knowledge Needed

- Execution action event details (name, source, summary).
- Conversation identifier and role slug.
- Role label formatting rules.

### Actions Needed

- Record log event.
- Link conversation identifier to role slug.
- Sanitize role label into slug string.
