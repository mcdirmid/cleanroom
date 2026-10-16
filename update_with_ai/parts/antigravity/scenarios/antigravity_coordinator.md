<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_coordinator scenarios
CODE_HASH: 9819ab45984b
-->

# antigravity_coordinator scenarios

## Scenario 1 — Generating zero-execution coordinator skill

Given: a cleanroom project repository configured for multi-agent execution.

1. The generator renders the coordinator skill.
   Observed: a skill document with frontmatter and instructions for DAG evaluation and subagent dispatch is generated.

## Scenario 2 — Enforcing workspace pinning requirement

Given: subagent dispatch instructions are being rendered.

1. The generator validates the skill content.
   Observed: the skill explicitly prohibits inheriting the parent workspace and requires setting Workspace to the role workspace directory.

## Scenario 3 — Formatting subagent dispatch directives

Given: a role dispatch directive for role_a in workspace_dir_a.

1. The generator formats the dispatch directive into an Antigravity tool specification.
   Observed: an Antigravity subagent dispatch payload is returned with TypeName, Role, Prompt, and Workspace path.

## Scenario 4 — Parsing wake notification messages

Given: a completion message emitted by a role subagent.

1. The generator parses the message text.
   Observed: action status, submitted targets, blamed targets, and failure diagnostics are extracted into a structured wake notification.
