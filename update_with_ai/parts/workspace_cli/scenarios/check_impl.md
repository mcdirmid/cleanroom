# Concrete scenarios for `check_impl` (implementation)

## Scenario 1 — Work discovery with pending dirty target blocking

Given: an active role workspace with a pending dirty target recorded in the buffer.

1. The caller runs `run_get_work`.
   Observed: returns exit code 1 and outputs error requiring completion of the pending target.

## Scenario 2 — File verification with starter template regeneration

Given: a regenerable role whose target file is missing from disk.

1. The caller runs `run_check_files`.
   Observed: regenerates target from starter template, executes verification commands, and records verification records and target file hashes in the workspace.

## Scenario 3 — Verification environment isolation

Given: an active role workspace with local test stubs shadowing canonical modules.

1. The caller runs `run_check_files`.
   Observed: executes verification tools with PYTHONPATH bounded strictly to the active role workspace and its package directories, isolating verification from the canonical repository root.

## Scenario 4 — Zero ready targets round conclusion directive formatting

Given: an active role workspace where all assigned targets are resolved, clean, or blocked waiting on prerequisites and zero ready targets exist.

1. The caller runs `run_get_work`.
   Observed: outputs the round conclusion directive instructing the worker that all work assigned to their role is resolved and the round must be concluded immediately without executing further tools.

## Scenario 5 — Model failure limit propagation in test verification

Given: an active role workspace with a model configuration declaring max_failures or local tier defaults.

1. The caller runs `run_check_files` for a target whose role verification command executes test rules.
   Observed: resolves effective max_failures from model configuration (defaulting to 5 for local engines and 100 for non-local models) and configures the test execution environment with `--maxfail`.

## Scenario 6 — Verification command execution timeout

Given: an active role workspace with a verification command that hangs or exceeds the execution timeout.

1. The caller runs `run_check_files`.
   Observed: bounds command execution with an execution timeout, terminates the hanging sub-process, reports verification failure due to timeout expiration with explicit diagnostic messaging that the timeout indicates a code defect (such as an infinite loop or deadlock) rather than an infrastructure failure, and returns a non-zero exit status without blocking indefinitely.

## Scenario 7 — Workspace-relative companion guide path resolution in get_work

Given: an active role workspace with an assigned role declaring a repository-relative guide path (`update_python_with_ai/guides/pretense.md`) and a copied guide in the role workspace (`guides/pretense.md`).

1. The caller runs `run_get_work`.
   Observed: formats the actionable next steps displaying the workspace-relative companion guide path (`guides/pretense.md`) rather than the uncopied repository-relative path.

## Scenario 8 — Gemini Argon active model verification in get_work

Given: an active role workspace configured with model `gemini-argon` on the `antigravity` harness where the active subagent conversation is running on a non-Argon model (e.g. `gemini-3.8-flash`).

1. The caller runs `run_get_work`.
   Observed: aborts with exit code 1 and outputs an error telling the user to manually switch their model to "Gemini Argon" before requesting the run again.

## Scenario 9 — Auditor specification grounding reminders upon verification failure

Given: an active auditor role workspace (such as QA or Coverage) where verification checks fail.

1. The caller runs `run_check_files`.
   Observed: upon verification failure, outputs prominent auditor reminders directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-21T21:50:00Z
LAST_CHANGED: 2026-10-29T00:30:00Z
CHANGE: Format auditor specification grounding reminders permitting line numbers in blamed file while forbidding exposing details of other files
-->
