# Concrete scenarios for `check_impl` (implementation)

## Scenario 1 — Work discovery with pending dirty target relisting

Given: an active role workspace with a pending dirty target recorded in the buffer.

1. The caller runs `run_get_work`.
   Observed: returns exit code 1 and relists the assigned pending target under ready for execution, formatting the companion guide, contracts to read, dirty reasons including unacted feedback, and actionable next steps as if it were the initial get_work call.

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

## Scenario 9 — Auditor triage summary upon verification failure

Given: an active auditor role workspace (such as QA or Coverage) where verification checks fail on a target file.

1. The caller runs `run_check_files`.
   Observed: upon verification failure, sanitizes subprocess output by stripping redundant embedded arbiter reminders, and outputs a structured triage summary extracting the author's latest # CHANGE: commit header, primary failure exception or assertion, candidate culprit file, and a single prominent auditor reminder directing the agent to formulate blame feedback explaining why the author's change did not resolve the defect strictly in terms of how the blamed file is not compliant with the common source of truth specification (instructing the coverage auditor to examine the library implementation for unreachable code when an uncovered line persists), and to call bin/get_work to verify remaining units and conclude after delivering blame without authoring debug scripts.

## Scenario 10 — Milestone git checkpoint commit on successful check_files

Given: an active authoring role workspace declaring writable target patterns with working tree modifications where `run_check_files` verification passes with zero errors.

1. The caller runs `run_check_files` for the target.
   Observed: static checks and test rules pass with exit code 0, and an in-workspace git commit is recorded with message `Checkpoint: verified <target>` preserving the verified working state.

## Scenario 11 — Auditor check_files omits milestone checkpoint commit

Given: an active auditor role workspace declaring zero writable target patterns where `run_check_files` verification passes.

1. The caller runs `run_check_files` for the target.
   Observed: static checks and test rules pass with exit code 0, and no git milestone commit is created, preserving clean workspace state without git side effects.

## Scenario 12 — Unauthorized read-only file modification detected and reverted

Given: an active role workspace where `__init__.py` or another file outside the role's writeable patterns was modified or created.

1. The caller runs `run_check_files`.
   Observed: detects the unauthorized modification, prints verification failure diagnostic, reverts the modified file from repository canonical state, and returns exit code 1.

## Scenario 13 — Verification rejected when role workspace has zero pending work

Given: an active role workspace with no pending targets recorded in the buffer and zero ready items in the work queue.

1. The caller runs `run_check_files` for a target.
   Observed: returns exit code 1 with error diagnostic directing the worker to call get_work first or conclude the round.

## Scenario 14 — Verification rejected when target is not in assigned pending work

Given: an active role workspace with pending targets recorded in the buffer.

1. The caller runs `run_check_files` for an unassigned target.
   Observed: returns exit code 1 with error diagnostic reporting that the target is not in assigned pending work.

## Scenario 15 — Pull inbound changes and refresh system files before running check_files

Given: an active role workspace with assigned pending work where canonical main workspace has updated files.

1. The caller runs `run_check_files`.
   Observed: pulls updated files and refreshes system files from canonical repository before executing verification rules.

## Scenario 16 — Auditor aggressive check_files and auto-submit in get_work

Given: an active auditor role workspace (such as QA or Coverage) with ready dirty targets discovering work via `get_work`.

1. The caller runs `run_get_work`.
   Observed: aggressively executes verification checks on each dirty target; targets passing verification are automatically submitted with audit attestation and omitted from presented work; targets failing verification are retained in the work queue without outputting failure diagnostics or triage summaries during work acquisition (leaving failure diagnostics to be surfaced when the worker executes `check_files` directly); and when all targets pass, clears pending work, sets the no-pending-work marker, and outputs the round conclusion directive directing the worker to conclude immediately with zero tool calls.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T11:00:00Z
LAST_CHANGED: 2026-11-03T23:45:00Z
CHANGE: Instruct coverage auditor when uncovered lines persist to examine library implementation for unreachable code
-->
