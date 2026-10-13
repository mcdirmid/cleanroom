<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:15:07Z
CHANGE: Add subagent harness impl scenarios
CODE_HASH: 70da102ca57e
-->

# subagent_harness_impl scenarios

### Scenario 1 — Formatting instructional task prompts

Given: role lib is dispatched in scope_a with ready targets.

1. The harness formats a task prompt.
   Observed: the prompt details the active role, target files, guide instructions, verification checks, and submit or blame actions.
   Realized by: the component's prompt construction interpolation.

### Scenario 2 — Detecting submitted files from pending work diffs

Given: a subagent executes cleanly and submits targets via the role tool.

1. The harness awaits turn completion.
   Observed: submitted targets are identified by diffing pre-execution pending work with remaining pending items, returning clean status.
   Realized by: the component's pending work buffer diff inspection.

### Scenario 3 — Detecting defect blame from the blame buffer

Given: a subagent executes and attributes defect feedback to an upstream file.

1. The harness awaits turn completion.
   Observed: the blame buffer records are detected, returning blamed status and culprit target paths.
   Realized by: the component's blame buffer file reading and attribution extraction.

### Scenario 4 — Handling subagent process execution failure

Given: an external subagent process crashes or exits with a non-zero exit code.

1. The harness awaits turn completion.
   Observed: the turn returns failed status with captured process diagnostic output.
   Realized by: the component's process execution exit code checking and log trailing capture.

### Scenario 5 — Resolving platform command templates

Given: a consumer requests a harness adapter for a platform name.

1. The resolver resolves the platform name.
   Observed: the corresponding CLI command template is resolved for Antigravity, Goose, or DeepSeek Harness, or simulation mode is enabled.
   Realized by: the component's platform template dictionary mapping.

### Scenario 6 — Enforcing execution timeouts

Given: a subagent process exceeds the configured timeout duration.

1. The harness awaits turn completion.
   Observed: the runaway process is terminated and the turn returns failed status noting timeout expiration.
   Realized by: the component's subprocess timeout monitoring and process termination.

### Scenario 7 — Parsing token metrics from execution logs

Given: a subagent turn log contains token reporting strings.

1. The harness awaits turn completion.
   Observed: uncached, cached, and output tokens are parsed into a normalized token usage record.
   Realized by: the component's regular expression log parsing and pricing calculation.
