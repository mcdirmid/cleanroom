<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:30:00Z
CHANGE: Define sandbox_submission planning specification
CODE_HASH: 9d9a558c2701
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# sandbox_submission interface component

## Intent

Autonomous agents operating across complex workspaces require explicit, governed control boundaries to conclude successful tasks, attribute upstream defects, and abort unrecoverable executions. Without centralized outcome coordination, agents risk silent failures, endless re-cleaning loops, or unverified task completions. The sandbox_submission interface component establishes a governed termination boundary that verifies session criteria, enforces change documentation when files are modified, and routes diagnostic feedback to responsible dependency nodes.

By providing dedicated tools for clean submission, failure attribution, and defect blame, outcome resolution couples session conclusion to empirical validation and structured provenance.

## Factored Contracts

### Typing

- A polymorphic resolve tool defines a file alias resolve target parameter identifying the active node being resolved.
- The submit tool is a resolve tool specifying a change summary parameter.
- The fail tool is a resolve tool specifying an explanation parameter.
- The blame tool is a resolve tool specifying a blame target parameter and an explanation parameter.

### Contracts

- A resolve tool produces a terminating response when all active nodes are resolved. [resolve_tool_terminates_when_all_resolved]
- A resolve tool produces a non-terminating response when other active nodes remain. [resolve_tool_lists_remaining_nodes]
- The submit tool concludes active nodes upon passing verification. [submit_concludes_nodes_on_pass]
- The submit tool resolves submitted target arguments supplied as canonical target strings or workspace-relative file paths against declared role targets. [submit_resolves_target_arguments]
- The submit tool marks the resolve target clean in the current get work turn. [submit_marks_target_clean]
- The submit tool enforces change documentation. [submit_enforces_change_documentation]
- The fail tool terminates the run in failure. [fail_terminates_run_in_failure]
- The blame tool attributes task failure to an upstream dependency node. [blame_attributes_upstream_failure]

### Woven Contracts

- Concluding tasks via the submit tool validates passing verification, documents modifications, and marks resolved targets clean in the graph. [submit_concludes_nodes_on_pass, submit_marks_target_clean, submit_enforces_change_documentation]
- Resolving active targets terminates the session when all active nodes are resolved, or produces a non-terminating response listing remaining targets when other nodes remain open. [resolve_tool_terminates_when_all_resolved, resolve_tool_lists_remaining_nodes]
- Attributing task failure via the blame tool records diagnostic explanations blaming upstream dependency nodes. [blame_attributes_upstream_failure]
- Terminating executions via the fail tool marks tasks as failed. [fail_terminates_run_in_failure]

## Grounding

### Knowledge Provisions

- Concludes active nodes clean in graph storage. [clean_submission]
- Records defect attribution to upstream dependencies. [defect_blame]
- Terminates tasks in failure. [failure_termination]

### Knowledge Requirements

- Tracking of open targets and dispatch of submission and failure outcomes.
  - Deferred: Requires session coordinator in implementation.
