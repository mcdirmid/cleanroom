# Concrete scenarios for `commands_impl` (implementation)

## Scenario 1 — Work evaluation with pending dirtiness gating

Given: an active role workspace with dirty pending target `parts/agent/lib/foo.py`.

1. The handler executes `run_get_work`.
   Observed: execution is refused with exit code 1 because `parts/agent/lib/foo.py` is still dirty.

2. The dirty target is submitted or blamed.
   Observed: pending work is cleared, subsequent `run_get_work` discovers next ready targets, bounds them by batch size, writes pending work, and returns exit code 0.

## Scenario 2 — File verification with starter template regeneration

Given: a role workspace where a target file is missing and the role defines source patterns and upstream dependencies.

1. The handler executes `run_check_files`.
   Observed: the handler materializes the starter template for the missing target, executes static verification, and returns the verification status.

## Scenario 3 — Submission with verification gating

Given: an active role workspace with modified target `parts/agent/lib/bar.py`.

1. The handler executes `run_submit` with summary `fix bug` when verification succeeds.
   Observed: target is stamped and written to canonical main, cleanroom log is appended, pending target is removed, and exit code is 0.

2. The handler executes `run_submit` when static verification fails without bypass.
   Observed: submission is refused, target remains modified and dirty, and exit code is 1.

3. The handler executes `run_submit` on a modified target without having run `run_check_files` since modification.
   Observed: submission is refused, target remains modified and dirty, and exit code is 1.

## Scenario 4 — Blame attribution with single-paragraph constraint

Given: a culprit upstream target and a multi-line critique containing newline characters.

1. The handler executes `run_blame` with the multi-line critique.
   Observed: blame is rejected due to newline violation, and exit code is 1.

2. The handler executes `run_blame` with a valid single-paragraph critique.
   Observed: critique feedback is appended to culprit, blamed culprit is recorded into `.cleanroom_blame_buffer.json`, cleanroom log is appended, pending work is cleared, and exit code is 0.

3. The handler executes `run_blame` or `run_fail` while workspace target files are modified without having run `run_check_files` since modification.
   Observed: execution is refused, reporting that `check_files` must be run on the modified files, and exit code is 1.

4. An auditor workspace with pending target `parts/dag_engine_lite/lib/dag_engine_lite_impl.py` executes `run_blame` against `parts/dag_engine_lite/pretense/dag_engine_lite_impl_pretense.py` with a valid critique.
   Observed: blame is accepted, pending work is cleared of the audited target, and exit code is 0.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-20T21:07:00Z
LAST_CHANGED: 2026-10-25T22:36:00Z
CHANGE: Add scenario for clearing pending target when auditor blames pretense culprit
-->
