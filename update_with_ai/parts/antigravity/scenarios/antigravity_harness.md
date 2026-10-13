<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_harness scenarios
CODE_HASH: 6ee8178fddac
-->

# antigravity_harness scenarios

## Scenario 1 — Executing role turn in role workspace

Given: a role dispatch directive for role_a in workspace_dir_a.

1. The harness adapter dispatches the role directive.
   Observed: execution begins in workspace_dir_a, runs subagent commands, and returns a task handle.

## Scenario 2 — Extracting token telemetry from transcript log

Given: an execution transcript log containing Gemini model interaction events.

1. The harness adapter parses the transcript log.
   Observed: uncached prompt tokens, cached prompt tokens, completion tokens, and financial expenditure in USD are computed.

## Scenario 3 — Constructing role turn result

Given: an executed turn where the agent submitted target_a and blamed culprit_b.

1. The harness adapter awaits role completion.
   Observed: a role turn result reports completed status with submitted targets, blamed targets, and token telemetry.

## Scenario 4 — Interrupting runaway turns

Given: an active turn that exceeds its execution timeout limit.

1. The harness adapter invokes interrupt.
   Observed: execution is terminated immediately and the turn reports failure.
