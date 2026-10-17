<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:14:22Z
CHANGE: Author workspace sync_impl concrete scenarios
CODE_HASH: b8ff635770a2
-->

# Concrete scenarios for `sync_impl` (implementation)

Scenarios 1 through 8 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 9
and 10 cover behaviours the interface does not expose to a caller, and each of them is a candidate
for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — The sync result of an operation that moved nothing

Given: role alpha is commissioned for scope_a, and the canonical main repository and the workspace
already hold identical alpha files.

1. The synchronizer pulls upstream changes for alpha in scope_a.
   Observed: a sync result reporting zero pulled files, zero harvested files, no stamped audits,
   and no flushed blames.
   Realized by: role configuration and directory scope lookups through `role_registry`, and
   the component's own file comparison, which filters out files whose content and metadata already
   agree.

### Scenario 2 — Pulling updated upstream contracts and sources

Given: role alpha is commissioned for scope_a; the canonical main repository holds
`beta/high/beta.md` with content `beta contract two` and the alpha source for widget with content
`widget two`, while the workspace holds `beta/high/beta.md` with content `beta contract one` and
the alpha source for widget with content `widget one`; nothing has been edited in the workspace
since it was commissioned.

1. The synchronizer pulls upstream changes for alpha in scope_a.
   Observed: the workspace `beta/high/beta.md` holds `beta contract two` with read-only
   permissions, the workspace alpha source for widget holds `widget two` with read-write
   permissions, and the sync result reports two pulled files.
   Realized by: role configuration lookups through `role_registry` for the directory scope
   and upstream contract dependencies, in-band source metadata extraction through `src_metadata`
   to establish that the local target carries no uncommitted change, and the component's own
   copying with permission enforcement.

### Scenario 3 — An upstream file that the workspace does not have at all

Given: role alpha is commissioned for scope_a; the canonical main repository holds the guide
`guides/alpha_guide.md`, which the workspace lacks, and a file `alpha/retired.md` that the
workspace holds but the main repository no longer holds.

1. The synchronizer pulls upstream changes for alpha in scope_a.
   Observed: `guides/alpha_guide.md` appears in the workspace with read-only permissions, and
   `alpha/retired.md` is deleted from the workspace.
   Realized by: role configuration lookups through `role_registry` for the declared guides
   and the directory scope, and the component's own deletion of workspace files that the canonical
   repository no longer holds.

### Scenario 4 — An upstream modification that conflicts with a local change

Given: role alpha is commissioned for scope_a; the alpha source for widget carries the local
modification `widget local`, its in-band code hash records that modification, and the canonical
main repository has since changed the same source to `widget upstream`.

1. The synchronizer pulls upstream changes for alpha in scope_a.
   Observed: the pull fails explicitly naming the alpha source for widget, and the workspace still
   holds `widget local` rather than either discarding it or merging the two contents.
   Realized by: in-band source metadata extraction through `src_metadata`, which establishes that
   the local target carries an uncommitted change, and the component's own fail-fast conflict
   detection.

2. The synchronizer pulls again after the local modification is submitted and the in-band code
   hash records the submitted content.
   Observed: the workspace now holds `widget upstream`, and the sync result reports one pulled
   file.
   Realized by: `src_metadata`, now finding no uncommitted local change, and the component's own
   copying of the differing upstream content.

### Scenario 5 — Refreshing the system files

Given: role alpha is commissioned for scope_a; the workspace holds local modifications to the
alpha source for widget and to the tool runner in `bin/`; the canonical main repository has
changed the tool runner, the project configuration, and the guide file
`guides/alpha_guide.md`.

1. The synchronizer refreshes the non-parts system files for alpha.
   Observed: the workspace tool runner, project configuration, and guide hold the canonical
   content, and the locally modified alpha source for widget is untouched.
   Realized by: the component's own system file refresh, which recopies project
   configurations and guides while skipping every in-scope source file, and delegation of runner
   deployment, role guide regeneration, and test stub synchronization to `provision`.

### Scenario 6 — Harvesting validated targets and an auditor audit

Given: role alpha is commissioned for scope_a with main repository root `/repo`; the workspace
alpha source for widget has been modified and its in-band code hash records the modification; the
canonical `/repo/alpha/widget.md` still holds the baseline content the workspace was
commissioned from.

1. The synchronizer harvests alpha's changes for scope_a.
   Observed: `/repo/alpha/widget.md` holds the modified content, the sync result reports one
   harvested file, and no stamped audits.
   Realized by: the component's own inspection phase, which scans writable targets and computes
   current code hashes through `src_metadata`; its validation phase, which compares the main
   repository baseline against the workspace baseline; and its commit phase, which copies the
   validated file.

2. The auditor role epsilon, whose feedback role dependency is alpha, verifies the same widget
   target and harvests.
   Observed: `/repo/alpha/widget.md` carries epsilon's audit stamp, its code body is unchanged,
   and the sync result reports one stamped audit naming the alpha-role widget target.
   Realized by: role configuration lookups through `role_registry` for epsilon's feedback
   role dependencies and audit tag, and audit stamping through `src_metadata`, which writes the
   attribute without changing the code body.

### Scenario 7 — Harvesting a target the main repository changed concurrently

Given: role alpha is commissioned for scope_a; the workspace alpha source for widget was modified
from baseline `widget one` to `widget local`; the canonical `/repo/alpha/widget.md` has since
changed from `widget one` to `widget upstream`.

1. The synchronizer harvests alpha's changes for scope_a.
   Observed: the harvest fails explicitly naming the alpha source for widget, `/repo/alpha/widget.md`
   still holds `widget upstream`, and the sync result reports no harvested file.
   Realized by: the component's own validation phase, comparing the main repository code hash
   against the workspace baseline through `src_metadata`, and its refusal to apply the conflicting
   write.

### Scenario 8 — Flushing buffered blame feedback

Given: role alpha is commissioned for scope_a and holds the local blame buffer recording two
critiques of `beta/high/beta.md`, namely `the refusal message names no target` and `the second
step restates the first`; `/repo/beta/high/beta.md` exists with a last cleaned timestamp of
`2026-01-02T03:04:05Z` and no unacted feedback.

1. The synchronizer flushes the blame buffer for alpha.
   Observed: `/repo/beta/high/beta.md` carries unacted feedback entries for both critiques with
   UTC timestamps, its last cleaned timestamp is deleted, the local blame buffer is gone, and the
   sync result reports two flushed blames.
   Realized by: the component's own read of the local blame buffer, feedback appending and
   timestamp clearing through `src_metadata`, and the component's own deletion of the buffer file
   once every entry applies.

2. The synchronizer flushes again with the buffer still gone.
   Observed: a sync result reporting no flushed blames, with `/repo/beta/high/beta.md` unchanged.
   Realized by: the component's own handling of an absent buffer file, which yields an empty flush
   rather than an error.

## Implementation-only

### Scenario 9 — Stub integrity across the workspace

Given: role alpha is commissioned for scope_a and declares the stub role dependency beta; the
workspace stub for beta is a read-only test stub built from `beta/high/beta.md`, while the main
repository's `beta/high/beta.md` has since changed.

1. The synchronizer pulls upstream changes for alpha in scope_a.
   Observed: the workspace stub for beta raises `NotImplementedError` and matches the changed
   companion specification, and no content from the main repository implementation
   `beta/lib/beta.py` appears in the workspace.
   Realized by: stub validation and regeneration from companion specifications delegated to
   `provision`, which never copies an implementation file matching a stub role dependency.

2. The main repository's `beta/high/beta.md` is removed, and the synchronizer pulls again.
   Observed: the orphaned workspace stub for beta is deleted.
   Realized by: stub synchronization delegated to `provision`, purging stubs whose companion specification no longer exists.

### Scenario 10 — Regenerating the guide without disturbing targets

Given: role alpha is commissioned for scope_a at `/ws/alpha_scope_a`, the workspace alpha source
for widget carries the local modification `widget local`, and the canonical guide content has
changed.

1. The synchronizer refreshes the non-parts system files for alpha.
   Observed: the regenerated guide again states the workspace boundary, the prohibition on version
   control operations, the blame and feedback resolution instructions (including target change
   header inspection before auditor blame delivery), and the fail-stop protocol, and `alpha/widget.md` still holds
   `widget local`.
   Realized by: role guide regeneration delegated to `provision`, which rewrites only the guide file and
   leaves every in-scope source file alone.
