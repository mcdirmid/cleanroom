<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_harness_impl scenarios
CODE_HASH: d0e66e7a6fd9
-->

# antigravity_harness_impl scenarios

### Scenario 1 — Executing role turn in role workspace

Given: a role dispatch directive for role_a in workspace_dir_a.

1. The harness adapter dispatches the role directive.
   Observed: execution begins in workspace_dir_a, runs subagent commands, and returns a task handle.
   Realized by: the component's process dispatch launching the subagent command in the role workspace directory.

### Scenario 2 — Extracting token telemetry from transcript log

Given: an execution transcript log containing Gemini model interaction events.

1. The harness adapter parses the transcript log.
   Observed: uncached prompt tokens, cached prompt tokens, completion tokens, and financial expenditure in USD are computed.
   Realized by: the component's transcript parser reading JSONL lines and calculating costs via model rate cards.

### Scenario 3 — Constructing role turn result

Given: an executed turn where the agent submitted target_a and blamed culprit_b.

1. The harness adapter awaits role completion.
   Observed: a role turn result reports completed status with submitted targets, blamed targets, and token telemetry.
   Realized by: the component's turn result collation inspecting the workspace submission records and blame buffers.

### Scenario 4 — Interrupting runaway turns

Given: an active turn that exceeds its execution timeout limit.

1. The harness adapter invokes interrupt.
   Observed: execution is terminated immediately and the turn reports failure.
   Realized by: the component's process termination sending kill signals to active subagent processes.
