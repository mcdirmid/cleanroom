<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:14:21Z
CHANGE: Author workspace workspace_sync concrete scenarios
CODE_HASH: 41e4afe93a12
-->

# Concrete scenarios for `workspace_sync` (interface)

## Scenario 1 — The sync result of an operation that moved nothing

Given: role alpha is commissioned for scope_a, and the canonical main repository and the workspace
already hold identical alpha files.

1. The synchronizer pulls upstream changes for alpha in scope_a.
   Observed: a sync result reporting zero pulled files, zero harvested files, no stamped audits,
   and no flushed blames.

## Scenario 2 — Pulling updated upstream contracts and sources

Given: role alpha is commissioned for scope_a; the canonical main repository holds
`beta/high/beta.md` with content `beta contract two` and the alpha source for widget with content
`widget two`, while the workspace holds `beta/high/beta.md` with content `beta contract one` and
the alpha source for widget with content `widget one`; nothing has been edited in the workspace
since it was commissioned.

1. The synchronizer pulls upstream changes for alpha in scope_a.
   Observed: the workspace `beta/high/beta.md` holds `beta contract two` with read-only
   permissions, the workspace alpha source for widget holds `widget two` with read-write
   permissions, and the sync result reports two pulled files.

## Scenario 3 — An upstream file that the workspace does not have at all

Given: role alpha is commissioned for scope_a; the canonical main repository holds the guide
`guides/alpha_guide.md`, which the workspace lacks, and a file `alpha/retired.md` that the
workspace holds but the main repository no longer holds.

1. The synchronizer pulls upstream changes for alpha in scope_a.
   Observed: `guides/alpha_guide.md` appears in the workspace with read-only permissions, and
   `alpha/retired.md` is deleted from the workspace.

## Scenario 4 — An upstream modification that conflicts with a local change

Given: role alpha is commissioned for scope_a; the alpha source for widget carries the local
modification `widget local`, its in-band code hash records that modification, and the canonical
main repository has since changed the same source to `widget upstream`.

1. The synchronizer pulls upstream changes for alpha in scope_a.
   Observed: the pull fails explicitly naming the alpha source for widget, and the workspace still
   holds `widget local` rather than either discarding it or merging the two contents.

2. The synchronizer pulls again after the local modification is submitted and the in-band code
   hash records the submitted content.
   Observed: the workspace now holds `widget upstream`, and the sync result reports one pulled
   file.

## Scenario 5 — Refreshing the system files

Given: role alpha is commissioned for scope_a; the workspace holds local modifications to the
alpha source for widget and to the tool runner in `bin/`; the canonical main repository has
changed the tool runner, the project configuration, and the guide file
`guides/alpha_guide.md`.

1. The synchronizer refreshes the non-parts system files for alpha.
   Observed: the workspace tool runner, project configuration, and guide hold the canonical
   content, and the locally modified alpha source for widget is untouched.

## Scenario 6 — Harvesting validated targets and an auditor audit

Given: role alpha is commissioned for scope_a with main repository root `/repo`; the workspace
alpha source for widget has been modified and its in-band code hash records the modification; the
canonical `/repo/alpha/widget.md` still holds the baseline content the workspace was
commissioned from.

1. The synchronizer harvests alpha's changes for scope_a.
   Observed: `/repo/alpha/widget.md` holds the modified content, the sync result reports one
   harvested file, and no stamped audits.

2. The auditor role epsilon, whose feedback role dependency is alpha, verifies the same widget
   target and harvests.
   Observed: `/repo/alpha/widget.md` carries epsilon's audit stamp, its code body is unchanged,
   and the sync result reports one stamped audit naming the alpha-role widget target.

## Scenario 7 — Harvesting a target the main repository changed concurrently

Given: role alpha is commissioned for scope_a; the workspace alpha source for widget was modified
from baseline `widget one` to `widget local`; the canonical `/repo/alpha/widget.md` has since
changed from `widget one` to `widget upstream`.

1. The synchronizer harvests alpha's changes for scope_a.
   Observed: the harvest fails explicitly naming the alpha source for widget, `/repo/alpha/widget.md`
   still holds `widget upstream`, and the sync result reports no harvested file.

## Scenario 8 — Flushing buffered blame feedback

Given: role alpha is commissioned for scope_a and holds the local blame buffer recording two
critiques of `beta/high/beta.md`, namely `the refusal message names no target` and `the second
step restates the first`; `/repo/beta/high/beta.md` exists with a last cleaned timestamp of
`2026-01-02T03:04:05Z` and no unacted feedback.

1. The synchronizer flushes the blame buffer for alpha.
   Observed: `/repo/beta/high/beta.md` carries unacted feedback entries for both critiques with
   UTC timestamps, its last cleaned timestamp is deleted, the local blame buffer is gone, and the
   sync result reports two flushed blames.

2. The synchronizer flushes again with the buffer still gone.
   Observed: a sync result reporting no flushed blames, with `/repo/beta/high/beta.md` unchanged.
