<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:15:06Z
CHANGE: Add subagent harness scenarios
CODE_HASH: 99f29775b07d
-->

# subagent_harness scenarios

## Scenario 1 — Formatting instructional task prompts

Given: role lib is dispatched in scope_a with ready targets.

1. The harness formats a task prompt.
   Observed: the prompt details the active role, target files, guide instructions, verification checks, and submit or blame actions.

## Scenario 2 — Detecting submitted files from pending work diffs

Given: a subagent executes cleanly and submits targets via the role tool.

1. The harness awaits turn completion.
   Observed: submitted targets are identified by diffing pre-execution pending work with remaining pending items, returning clean status.

## Scenario 3 — Detecting defect blame from the blame buffer

Given: a subagent executes and attributes defect feedback to an upstream file.

1. The harness awaits turn completion.
   Observed: the blame buffer records are detected, returning blamed status and culprit target paths.

## Scenario 4 — Handling subagent process execution failure

Given: an external subagent process crashes or exits with a non-zero exit code.

1. The harness awaits turn completion.
   Observed: the turn returns failed status with captured process diagnostic output.

## Scenario 5 — Resolving platform command templates

Given: a consumer requests a harness adapter for a platform name.

1. The resolver resolves the platform name.
   Observed: the corresponding CLI command template is resolved for Antigravity, Goose, or DeepSeek Harness, or simulation mode is enabled.

## Scenario 6 — Enforcing execution timeouts

Given: a subagent process exceeds the configured timeout duration.

1. The harness awaits turn completion.
   Observed: the runaway process is terminated and the turn returns failed status noting timeout expiration.

## Scenario 7 — Parsing token metrics from execution logs

Given: a subagent turn log contains token reporting strings.

1. The harness awaits turn completion.
   Observed: uncached, cached, and output tokens are parsed into a normalized token usage record.
