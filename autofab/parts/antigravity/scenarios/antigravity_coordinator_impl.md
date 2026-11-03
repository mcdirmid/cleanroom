# antigravity_coordinator_impl scenarios

### Scenario 1 — Generating zero-execution coordinator skill

Given: an autofab project repository configured for multi-agent execution.

1. The generator renders the coordinator skill.
   Observed: a skill document with frontmatter and instructions for DAG evaluation, subagent dispatch, and messaging back workers upon unresolved rounds is generated.
   Realized by: the component's markdown template formatting zero-execution instructions and YAML metadata.

### Scenario 2 — Enforcing workspace pinning requirement

Given: subagent dispatch instructions are being rendered.

1. The generator validates the skill content.
   Observed: the skill explicitly prohibits inheriting the parent workspace and requires setting Workspace to the role workspace directory.
   Realized by: the component's invariant assertion checking for forbidden inheritance strings.

### Scenario 3 — Formatting subagent dispatch directives

Given: a role dispatch directive for role_a in workspace_dir_a.

1. The generator formats the dispatch directive into an Antigravity tool specification.
   Observed: an Antigravity subagent dispatch payload is returned with TypeName, Role, Prompt (incorporating sole custodian file ownership certainty, targeted chunk reading directives, strict workspace confinement prohibiting unbounded filesystem scans, and coordinator reminders when present), and Workspace path.
   Realized by: the component's dispatch mapping constructing parameter dictionaries for `invoke_subagent`.

### Scenario 4 — Parsing wake notification messages

Given: a completion message emitted by a role subagent.

1. The generator parses the message text.
   Observed: action status, submitted targets, blamed targets, and failure diagnostics are extracted into a structured wake notification.
   Realized by: the component's message deserialization parsing JSON payloads or structured text blocks.

### Scenario 5 — Configuring pre-tool checkpoint hooks

Given: authoring role workspace `workspace_dir_a` with writable targets is being configured for Antigravity execution.

1. The coordinator configures workspace hooks.
   Observed: `.agents/hooks.json` exists in `workspace_dir_a` containing a `PreToolUse` lifecycle hook configuration for `edit_file|write_file` executing `./bin/checkpoint pre-edit`.
   Realized by: the component's hook configuration serializer writing `.agents/hooks.json`.

### Scenario 6 — Configuring auditor role workspace hooks

Given: auditor role workspace `workspace_dir_b` with zero writable targets is being configured for Antigravity execution.

1. The coordinator configures workspace hooks.
   Observed: boundary rules explicitly instruct zero file-editing permissions, and `.agents/hooks.json` configures `PreToolUse` hooks denying `edit_file` and `write_file` invocations (or omits checkpoint hooks).
   Realized by: the component's hook configuration serializer checking role writable file patterns.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-30T08:30:00Z
CHANGE: Deny edit tools and omit checkpoint hooks in .agents/hooks.json for auditor roles
-->
