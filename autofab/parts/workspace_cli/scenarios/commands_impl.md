# Concrete scenarios for `commands_impl` (implementation)

## Scenario 1 — Work evaluation with pending dirtiness gating

Given: an active role workspace with dirty pending target `parts/agent/lib/foo.py`.

1. The handler executes `run_get_work`.
   Observed: execution is refused with exit code 1 because `parts/agent/lib/foo.py` is still dirty.

1. The dirty target is submitted or blamed.
   Observed: pending work is cleared, subsequent `run_get_work` discovers next ready targets, bounds them by batch size, writes pending work, and returns exit code 0.

## Scenario 2 — File verification with starter template regeneration

Given: a role workspace where a target file is missing and the role defines source patterns and upstream dependencies.

1. The handler executes `run_check_files`.
   Observed: the handler materializes the starter template for the missing target, executes static verification, and returns the verification status.

## Scenario 3 — Submission with verification gating

Given: an active role workspace with modified target `parts/agent/lib/bar.py`.

1. The handler executes `run_submit` with summary `fix bug` when verification succeeds.
   Observed: target is stamped and written to canonical main, event log is appended, pending target is removed, and exit code is 0.

1. The handler executes `run_submit` when static verification fails without bypass.
   Observed: submission is refused, target remains modified and dirty, and exit code is 1.

1. The handler executes `run_submit` on a modified target without having run `run_check_files` since modification.
   Observed: submission is refused, target remains modified and dirty, and exit code is 1.

1. The handler executes `run_submit` with `no_verify` in an active role workspace.
   Observed: submission is refused with an error prohibiting `--no-verify` in role workspaces, and exit code is 1.

## Scenario 4 — Blame attribution with single-paragraph constraint and staging

Given: a culprit upstream target and a multi-line critique containing newline characters.

1. The handler executes `run_blame` with the multi-line critique.
   Observed: critique is sanitized by collapsing line breaks into a single continuous paragraph, blame is staged into `.autofab_staged_blame.json`, a directive prompting the caller to stage additional blame or commit via `bin/submit` is emitted, and exit code is 0.

1. The handler executes `run_blame` with a valid single-paragraph critique.
   Observed: blame is staged into `.autofab_staged_blame.json`, a directive prompting the caller to stage additional blame or commit via `bin/submit` is emitted, and exit code is 0.

1. The handler executes `run_blame` or `run_fail` while workspace target files are modified without having run `run_check_files` since modification.
   Observed: execution is refused, reporting that `check_files` must be run on the modified files, and exit code is 1.

1. An auditor workspace with pending target `parts/dag_engine_lite/lib/dag_engine_lite_impl.py` executes `run_blame` against `parts/dag_engine_lite/pretense/dag_engine_lite_impl_pretense.py` with a valid critique, followed by `run_submit` on the audited target.
   Observed: blame is staged on `run_blame`, then `run_submit` commits the staged blame, marks the culprit dirty, appends event logs, records the blame into `.autofab_blame_buffer.json`, clears the audited target from pending work, and returns exit code 0.

1. A coverage auditor workspace where all open deficit spans in `.coverage_spans.json` are classified as `LIB-PRAGMA-REQUIRED` executes `run_blame` against a test module.
   Observed: blame is refused with an error reporting misattribution and zero test-owned spans in the deficit, directing blaming the library module instead, and exit code is 1.

1. A coverage auditor workspace executes `run_blame` with the same culprit and identical uncovered span set as the previous blame recorded in the buffer.
   Observed: blame is refused with an error prohibiting repeating identical blame against an unyielding span set, and exit code is 1.

1. The handler executes `run_blame` with an active `structured_blame` experiment.
   Observed: critique is parsed and validated as a structured blame tuple against low-level specifications, taxonomy, facet noun phrases, and symbol embargo rules, staging compliant blame or refusing malformed blame with exit code 1.

1. An auditor role workspace whose role definition declares the culprit's role under `star_feedback_role_deps` (such as `pretense_qa` blaming `pretense`) executes `run_blame` against a culprit target belonging to that role.
   Observed: the handler resolves permissions from the union of `feedback_role_deps` and `star_feedback_role_deps`, permits the blame attribution, stages the blame, and returns exit code 0.

## Scenario 7 — Rejecting feedback on unmodified targets

Given: an active role workspace with an assigned target carrying active feedback.

1. The handler executes `run_reject` while the target file has been modified.
   Observed: execution is refused with an error instructing that modified files must be submitted with `submit`, and exit code is 1.

1. The handler executes `run_reject` on an unmodified target file carrying active feedback.
   Observed: the active `# FEEDBACK:` header is scrubbed from the file, the contest rationale is recorded into `.autofab_blame_buffer.json` and the event log, the target is cleared from pending work, a round conclusion directive is emitted, and exit code is 0.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T11:00:00Z
LAST_CHANGED: 2026-11-07T10:20:00Z
CHANGE: Realize reject command scenarios and stage-and-commit blame submission scenarios
-->
