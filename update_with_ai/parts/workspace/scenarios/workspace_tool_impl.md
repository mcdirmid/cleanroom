<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:14:23Z
CHANGE: Author workspace workspace_tool_impl concrete scenarios
CODE_HASH: 5fd6730ecdbf
-->

# Concrete scenarios for `workspace_tool_impl` (implementation)

Scenarios 1 through 8 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 9
through 11 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Running the work subcommand

Given: role alpha is active in scope_a, the alpha-role target for the unit widget is missing, and
the pending work buffer is empty.

1. The caller runs the work subcommand for scope_a as role alpha.
   Observed: a console report listing the alpha-role target for widget as ready with the reason
   that the target is missing, naming its companion specification contracts to read and its next
   steps, and an integer exit code of zero.
   Realized by: session tier scoping through `agent_session`, inbound change pulling through
   `workspace_sync`, queue evaluation and pending target tracking through `workspace_work`, and the
   component's own console report formatting.
2. The caller runs the work subcommand again without changing anything.
   Observed: the report is refused, naming the pending alpha-role target for widget and directing
   the caller to complete or blame it, and the exit code is non-zero.
   Realized by: `workspace_work`, which refuses a new discovery request while uncompleted dirty
   work remains pending, and the component's own propagation of that refusal as a non-zero exit
   code.

### Scenario 2 — Running the submit subcommand

Given: role alpha is active in scope_a, the alpha-role target for widget has been modified and
carries an in-band code hash recording that modification, and the caller supplies no change
summary.

1. The caller runs the submit subcommand for the alpha-role target for widget without a summary.
   Observed: the submission is refused, naming the missing summary, the target keeps its
   modification, and the exit code is non-zero.
   Realized by: target submission gating and code hash validation through `control_submit`, and
   the component's own argument validation of the producer change summary.
2. The caller runs the submit subcommand for the target with the summary `clean widget`.
   Observed: the target's in-band metadata records the summary `clean widget`, a submission record
   is appended to the cleanroom log, the pending work buffer no longer lists the target, and the
   exit code is zero.
   Realized by: `control_submit` for validation and metadata stamping, `workspace_sync` for the
   reflection of the stamped files into the role workspace, the component's own log append, and
   `workspace_work` for clearing the target from pending work.

### Scenario 3 — Running the blame subcommand

Given: role alpha is active in scope_a and the companion specification `beta/high/beta.md`
declares a refusal that names no target.

1. The caller runs the blame subcommand against `beta/high/beta.md` with the single-paragraph
   critique `the refusal names no target`.
   Observed: the critique is recorded as an unacted feedback entry on `beta/high/beta.md` in the
   canonical main repository, a blame record is appended to the cleanroom log, the pending work
   buffer no longer lists the alpha-role target for widget, and the exit code is zero.
   Realized by: defect blame attribution through `control_attribution`, `workspace_sync` for the
   in-band append to the culprit file, the component's own log append, and `workspace_work` for
   clearing the pending target.
2. The caller runs the blame subcommand against `beta/high/beta.md` with a critique of two
   paragraphs.
   Observed: the attribution is refused, naming the single-paragraph constraint, no feedback entry
   is recorded, and the exit code is non-zero.
   Realized by: the component's own argument validation of the critique paragraph count, which
   precedes attribution.

### Scenario 4 — Running the fail subcommand

Given: role alpha is active in scope_a and the alpha-role target for widget raises a diagnostic
when its declared verification runs.

1. The caller runs the fail subcommand for the alpha-role target for widget with the diagnostic
   `verification aborted without a report`.
   Observed: the diagnostic is recorded as failure feedback on the target, the pending work buffer
   no longer lists the target, and the exit code is zero.
   Realized by: failure tagging and diagnostic recording through `control_attribution`, and
   `workspace_work` for clearing the pending target.

### Scenario 5 — Running the check files subcommand

Given: role alpha is active in scope_a, the alpha-role target for widget exists and is clean, and
the alpha-role target for gadget is missing.

1. The caller runs the check files subcommand for the alpha-role target for widget.
   Observed: the verification reports a clean outcome and the exit code is zero.
   Realized by: the component's own resolution of the active role and target files and its
   execution of the corresponding static linting, type checking, and test rules, whose exit status
   it returns.
2. The caller runs the check files subcommand for the missing alpha-role target for gadget.
   Observed: the target is regenerated from its starter template before verification runs, and the
   exit code reflects that verification's status.
   Realized by: the component's own starter template regeneration for a role that declares source
   patterns and upstream dependencies, followed by the same verification path.

### Scenario 6 — Running the coverage subcommand

Given: role alpha is active in scope_a, the alpha-role implementation file for widget has one
statement executed by its companion test, and the declared coverage threshold is 50 percent.

1. The caller runs the coverage subcommand for the alpha-role target for widget.
   Observed: a diagnostic span report covering the implementation and test pair, with the
   statement coverage reported against the 50 percent threshold, and the exit code reflects
   whether the threshold was met.
   Realized by: statement coverage evaluation through `tool_coverage`, which uses the local
   workspace files when they are present, and the component's own span report formatting.

### Scenario 7 — Commissioning and refreshing workspaces

Given: no workspace is commissioned for role beta in scope_b, and the system files of the
workspace of role alpha in scope_a differ from their canonical content.

1. The caller runs the commission subcommand for role beta in scope_b.
   Observed: the beta workspace for scope_b is created and registered, and the exit code is zero.
   Realized by: workspace commissioning through `workspace_provision` and active workspace
   registration through `workspace_registry`.
2. The caller runs the refresh system subcommand across the active workspaces.
   Observed: the system files, bin utilities, and companion guides of the alpha workspace hold the
   canonical content, and the exit code is zero.
   Realized by: active workspace discovery through `workspace_registry` and system synchronization
   through `workspace_sync`.

### Scenario 8 — An unknown subcommand

Given: role alpha is active in scope_a.

1. The caller runs the subcommand `polish` for the alpha-role target for widget.
   Observed: the request is refused, naming `polish` as unknown, no file is changed, and the exit
   code is non-zero.
   Realized by: the component's own command-line argument parsing, which rejects a subcommand it
   does not implement before any domain coordinator is reached.

## Implementation-only

### Scenario 9 — The feedback subcommand buffers a critique

Given: role alpha is active in scope_a, no local blame buffer exists, and the companion
specification `beta/high/beta.md` declares a refusal that names no target.

1. The caller runs the feedback subcommand against `beta/high/beta.md` with the
   single-paragraph critique `the refusal names no target`.
   Observed: the critique is recorded in the local blame buffer for `beta/high/beta.md`, no
   feedback entry is written to the canonical main repository yet, and the exit code is zero.
   Realized by: the component's own blame buffer write, which defers the canonical append to the
   next flush through `workspace_sync`.

2. The caller then runs the refresh system subcommand.
   Observed: the critique appears as an unacted feedback entry on `beta/high/beta.md` in the
   canonical main repository and the local blame buffer is gone.
   Realized by: `workspace_sync`, whose flush reads the local blame buffer and appends the entries
   in-band.

### Scenario 10 — Work execution pulls before it evaluates

Given: role alpha is active in scope_a, the canonical main repository holds newer content for
`beta/high/beta.md` than the workspace does, and no in-scope target carries an uncommitted change.

1. The caller runs the work subcommand for scope_a as role alpha.
   Observed: the workspace `beta/high/beta.md` holds the newer canonical content by the time the
   report is printed, and the report reflects work evaluated against that content.
   Realized by: inbound change pulling through `workspace_sync`, which the work path runs before
   `workspace_work` evaluates the queue.

### Scenario 11 — Startup synchronization of the system files

Given: role alpha is active in scope_a and the workspace tool runner in `bin/` differs from the
canonical tool runner.

1. The caller runs the check files subcommand for the alpha-role target for widget.
   Observed: the workspace tool runner is refreshed to the canonical content before verification
   runs, the verification itself is unaffected, and the exit code reflects the verification.
   Realized by: the component's own startup synchronization, which routes system file refresh
   through `workspace_sync` before the target's verification rules execute.
