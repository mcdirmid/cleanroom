<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T11:00:00Z
CHANGE: turn down support for goose, supporting only antigravity and dsh
CODE_HASH: 95753b524ca3
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

## Scenario 5 — Installing and resolving platform harness adapters

Given: an adapter factory is installed in the harness registry for a platform name.

1. The registry resolves the platform name.
   Observed: the corresponding harness adapter is constructed via the installed adapter factory, or simulation mode is enabled.

## Scenario 6 — Enforcing execution timeouts when explicitly configured

Given: a subagent process exceeds the configured timeout duration when an explicit timeout limit is specified.

1. The harness awaits turn completion.
   Observed: the runaway process is terminated and the turn returns failed status noting timeout expiration.

## Scenario 7 — Non-blocking polling without mandatory execution timeout

Given: an active subagent process executes with default configuration without a timeout limit.

1. The harness polls the active process.
   Observed: running processes return none without termination, and completed processes return final turn results.

## Scenario 8 — Parsing token metrics from execution logs

Given: a subagent turn log contains token reporting strings.

1. The harness awaits turn completion.
   Observed: uncached, cached, and output tokens are parsed into a normalized token usage record.
