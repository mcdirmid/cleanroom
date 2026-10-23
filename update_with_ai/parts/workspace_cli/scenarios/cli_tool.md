# Concrete scenarios for `cli_tool` (interface)

## Scenario 1 — Running the work subcommand

Given: role alpha is active in scope_a, the alpha-role target for the unit widget is missing, and
the pending work buffer is empty.

1. The caller runs the work subcommand for scope_a as role alpha.
   Observed: a console report listing the alpha-role target for widget as ready with the reason
   that the target is missing, naming its companion specification contracts to read and its next
   steps, and an integer exit code of zero.
2. The caller runs the work subcommand again without changing anything.
   Observed: the report is refused, naming the pending alpha-role target for widget and directing
   the caller to complete or blame it, and the exit code is non-zero.

## Scenario 2 — Running the submit subcommand

Given: role alpha is active in scope_a, the alpha-role target for widget has been modified and
carries an in-band code hash recording that modification, and the caller supplies no change
summary.

1. The caller runs the submit subcommand for the alpha-role target for widget without a summary.
   Observed: the submission is refused, naming the missing summary, the target keeps its
   modification, and the exit code is non-zero.
2. The caller runs the submit subcommand for the target with the summary `clean widget`.
   Observed: the target's in-band metadata records the summary `clean widget`, a submission record
   is appended to the cleanroom log, the pending work buffer no longer lists the target, and the
   exit code is zero.

## Scenario 3 — Running the blame subcommand

Given: role alpha is active in scope_a and the companion specification `beta/high/beta.md`
declares a refusal that names no target.

1. The caller runs the blame subcommand against `beta/high/beta.md` with the single-paragraph
   critique `the refusal names no target`.
   Observed: the critique is recorded as an unacted feedback entry on `beta/high/beta.md` in the
   canonical main repository, a blame record is appended to the cleanroom log, the pending work
   buffer no longer lists the alpha-role target for widget, and the exit code is zero.
2. The caller runs the blame subcommand against `beta/high/beta.md` with a critique of two
   paragraphs.
   Observed: the attribution is refused, naming the single-paragraph constraint, no feedback entry
   is recorded, and the exit code is non-zero.

## Scenario 4 — Running the fail subcommand

Given: role alpha is active in scope_a and the alpha-role target for widget raises a diagnostic
when its declared verification runs.

1. The caller runs the fail subcommand for the alpha-role target for widget with the diagnostic
   `verification aborted without a report`.
   Observed: the diagnostic is recorded as failure feedback on the target, the pending work buffer
   no longer lists the target, and the exit code is zero.

## Scenario 5 — Running the check files subcommand

Given: role alpha is active in scope_a, the alpha-role target for widget exists and is clean, and
the alpha-role target for gadget is missing.

1. The caller runs the check files subcommand for the alpha-role target for widget.
   Observed: the verification reports a clean outcome and the exit code is zero.
2. The caller runs the check files subcommand for the missing alpha-role target for gadget.
   Observed: the target is regenerated from its starter template before verification runs, and the
   exit code reflects that verification's status.

## Scenario 6 — Running the coverage subcommand

Given: role alpha is active in scope_a, the alpha-role implementation file for widget has one
statement executed by its companion test, and the declared coverage threshold is 50 percent.

1. The caller runs the coverage subcommand for the alpha-role target for widget.
   Observed: a diagnostic span report covering the implementation and test pair, with the
   statement coverage reported against the 50 percent threshold, and the exit code reflects
   whether the threshold was met.

## Scenario 7 — Commissioning and refreshing workspaces

Given: no workspace is commissioned for role beta in scope_b, and the system files of the
workspace of role alpha in scope_a differ from their canonical content.

1. The caller runs the commission subcommand for role beta in scope_b.
   Observed: the beta workspace for scope_b is created and registered, and the exit code is zero.
2. The caller runs the refresh system subcommand across the active workspaces.
   Observed: the system files, bin utilities, and companion guides of the alpha workspace hold the
   canonical content, and the exit code is zero.

## Scenario 8 — An unknown subcommand

Given: role alpha is active in scope_a.

1. The caller runs the subcommand `polish` for the alpha-role target for widget.
   Observed: the request is refused, naming `polish` as unknown, no file is changed, and the exit
   code is non-zero.

## Scenario 9 — Running the work subcommand with batch size bounding

Given: role alpha is active in scope_a with two ready targets, and the pending work buffer is empty.

1. The caller runs the work subcommand for scope_a with batch size one.
   Observed: a console report presenting the first ready target, advising that one additional ready unit remains in the queue and should be acquired after submitting the active batch, only the first target recorded in pending work, and an exit code of one indicating work is ready.

## Scenario 10 — Commissioning all roles for a directory scope

Given: scope_a declares multiple roles in its methodology configuration, and no role workspaces have been commissioned.

1. The caller runs the commission subcommand with the all flag for scope_a (`commission --all scope_a`).
   Observed: role workspaces for all declared roles within scope_a are created and registered, mapping the positional scope parameter as directory scope rather than a role name, and the exit code is zero.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:15:14Z
CHANGE: Update Scenario 10 for dynamic directory scope
-->
