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
   Realized by: the component's transcript parser reading JSONL lines (falling back to regex scraping from raw lines) and calculating costs via model rate cards.

### Scenario 3 — Constructing role turn result

Given: an executed turn where the agent submitted target_a and blamed culprit_b.

1. The harness adapter awaits role completion.
   Observed: a role turn result reports completed status with submitted targets, blamed targets, and token telemetry.
   Realized by: the component's turn result collation inspecting the workspace submission records (and stdout completion tags) and blame buffers.

### Scenario 4 — Interrupting runaway turns

Given: an active turn that exceeds its execution timeout limit.

1. The harness adapter invokes interrupt.
   Observed: execution is terminated immediately and the turn reports failure.
   Realized by: the component's process termination sending kill signals to active subagent processes.

### Scenario 5 — Polling active turns non-blockingly

Given: an active role turn currently executing in a role workspace.

1. The harness adapter polls the active turn.
   Observed: returns None while the process continues running, and returns a completed turn result once finished.
   Realized by: the component's process polling checking subprocess return status without blocking.

### Scenario 6 — Registering Antigravity harness adapter factory

Given: an agent session with an active harness registry.

1. The harness manager initializes.
   Observed: the Antigravity harness adapter factory is installed in the harness registry under platform name antigravity.
   Realized by: the component's harness manager querying the harness registry singleton and installing its adapter factory during initialization.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T19:15:00Z
CHANGE: author antigravity_harness_impl scenarios
-->
