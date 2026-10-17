<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:25:00Z
CHANGE: Define check planning specification
CODE_HASH: f8e77d9b3a48
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# check interface component

## Intent

Operating command-line subagents in isolated workspaces requires structured commands to discover assigned work, evaluate dirty targets, and run verification tools. The check interface component establishes operational contracts for running work discovery and file verification commands within role workspaces.

## Factored Contracts

### Typing

- A workspace checker operates within the agent session lifecycle tier.

### Contracts

- The workspace checker evaluates dirty work in the local role workspace, presenting bounded batches of ready targets and throttling unacted feedback reasons. [run_workspace_get_work]
- The workspace checker executes role-specific verification checks, linters, and type checking for specified or pending target files, configuring PYTHONPATH in the execution environment to include the package root and constituent support libraries, and regenerating missing targets from starter templates. [run_workspace_check_files]

### Woven Contracts

- When driving developer loop interactions in a role workspace, the checker evaluates and presents ready tasks, and executes verification checks across targets. [run_workspace_get_work, run_workspace_check_files]

## Grounding

### Knowledge Provisions

- Workspace work discovery and file checking command services. [workspace_check_service]

### Knowledge Requirements

- In-workspace work queue discovery and diagnostic formatting.
  - Deferred: Provided by workspace checker implementation.
- Target file verification, linting, and starter template regeneration.
  - Deferred: Provided by workspace checker implementation.
