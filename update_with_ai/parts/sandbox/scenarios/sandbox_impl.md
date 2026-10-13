<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-11T03:11:54Z
CHANGE: Author sandbox sandbox_impl concrete scenarios
CODE_HASH: 7a73be45ec52
-->

# Concrete scenarios for `sandbox_impl` (implementation)

Scenarios 1 through 4 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 5 through
8 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — A session that inspects a file without changing it

Given: an agent session for role alpha with no file modification yet, in which the agent reads the
workspace file `/ws/alpha_scope_a/widget.md` at 2026-01-02T03:04:05Z.

1. The agent asks whether workspace file modifications occurred during the session.
   Observed: no modifications occurred during the session.
   Realized by: file modification tracking delegated to `sandbox_file_editor`, whose edit manager
   reports that no workspace file writes occurred because no file content differs from its in-band
   code hash.

### Scenario 2 — A session that changes one file

Given: an agent session for role beta with no file modification yet, the workspace file
`/ws/beta_scope_b/gadget.md` holding the line `gadget_height = 30`, and the session permitted to
change that file.

1. The agent changes the content of `/ws/beta_scope_b/gadget.md` at 2026-01-02T03:05:00Z to the line
   `gadget_height = 42`.
   Observed: the sandbox records a file modification for the session.
   Realized by: file modification tracking delegated to `sandbox_file_editor`, whose edit manager
   detects the write by comparing the file content against its in-band code hash.

### Scenario 3 — A session that changes three files

Given: an agent session for role gamma with no file modification yet, and the workspace files
`/ws/gamma_scope_a/widget.md`, `/ws/gamma_scope_a/gadget.md`, and `/ws/gamma_scope_a/sprocket.md`
holding the lines `widget_height = 30`, `gadget_height = 30`, and `sprocket_height = 30`.

1. The agent changes the content of `/ws/gamma_scope_a/widget.md` at 2026-01-02T03:06:00Z to the line
   `widget_height = 42`, then changes the content of `/ws/gamma_scope_a/gadget.md` at
   2026-01-02T03:06:30Z to the line `gadget_height = 42`, then changes the content of
   `/ws/gamma_scope_a/sprocket.md` at 2026-01-02T03:07:00Z to the line `sprocket_height = 42`.
   Observed: the sandbox records a file modification for each of the three changes.
   Realized by: file modification tracking delegated to `sandbox_file_editor`, which detects each
   write by comparing that file's content against its in-band code hash.

### Scenario 4 — A write that leaves the file content unchanged

Given: an agent session for role delta with no file modification yet, and the workspace file
`/ws/delta_scope_a/widget.md` holding the line `widget_height = 30`.

1. The agent changes the content of `/ws/delta_scope_a/widget.md` at 2026-01-02T03:08:00Z to the
   line `widget_height = 30`, which is the content the file already holds.
   Observed: the file content is unchanged by that write, and the sandbox records no file
   modification for the session.
   Realized by: file modification tracking delegated to `sandbox_file_editor`, whose edit manager
   finds the file content identical to its in-band code hash and so reports no write.

## Implementation-only

### Scenario 5 — Reads performed after a modification

Given: an agent session for role epsilon with no file modification yet, and the workspace file
`/ws/epsilon_scope_a/widget.md` holding the line `widget_height = 30`.

1. The agent changes the content of `/ws/epsilon_scope_a/widget.md` at 2026-01-02T03:09:00Z to the
   line `widget_height = 42`.
   Observed: the sandbox records a file modification for the session.
   Realized by: file modification tracking delegated to `sandbox_file_editor`, whose edit manager
   detects the write by comparing the file content against its in-band code hash.

2. The agent reads `/ws/epsilon_scope_a/widget.md` at 2026-01-02T03:09:30Z.
   Observed: the sandbox still records that file modification for the session.
   Realized by: the same delegated tracking, whose write detection compares file content against its
   in-band code hash and is unaffected by the file reads that `sandbox_file_editor` records
   separately.

### Scenario 6 — A write the session was not permitted to make

Given: an agent session for role zeta with no file modification yet, and the read-only workspace file
`/ws/zeta_scope_a/gadget.md` holding the line `gadget_height = 30`.

1. The agent attempts to change the content of `/ws/zeta_scope_a/gadget.md` at 2026-01-02T03:10:00Z
   to the line `gadget_height = 42`.
   Observed: the change is refused, the file content remains `gadget_height = 30`, and the sandbox
   records no file modification for the session.
   Realized by: file modification tracking delegated to `sandbox_file_editor`, whose write detection
   finds the file content still equal to its in-band code hash after the edit manager refused the
   write for a file that is not a read-write file.

### Scenario 7 — Two sessions tracking independently

Given: an agent session for role alpha with no file modification yet, an agent session for role zeta
with no file modification yet, and the workspace files `/ws/alpha_scope_a/widget.md` and
`/ws/zeta_scope_a/widget.md` each holding the line `widget_height = 30`.

1. The agent changes the content of `/ws/alpha_scope_a/widget.md` at 2026-01-02T03:11:00Z to the
   line `widget_height = 42`.
   Observed: the sandbox records a file modification for the session for role alpha and no file
   modification for the session for role zeta.
   Realized by: the component's own per-session modification state, which each session's delegated
   write detection writes into, so that one session's edit manager reports writes only for its own
   session.

2. The agent changes the content of `/ws/zeta_scope_a/widget.md` at 2026-01-02T03:11:30Z to the line
   `widget_height = 42`.
   Observed: the sandbox records a file modification for the session for role zeta.
   Realized by: the same per-session state and the same delegated write detection for the second
   session.

### Scenario 8 — The modification state once the session concludes

Given: an agent session for role beta with no file modification yet, the session permitted to change
the workspace file `/ws/beta_scope_b/gadget.md`, and an outcome control that requires documentation
of changed files before the session concludes.

1. The agent changes the content of `/ws/beta_scope_b/gadget.md` at 2026-01-02T03:12:00Z to the line
   `gadget_height = 42` and then concludes the session.
   Observed: the sandbox reports that workspace file modifications occurred during the session, and
   the session has concluded.
   Realized by: the component's own per-session modification state, which the delegated write
   detection of `sandbox_file_editor` wrote before the session concluded and which the conclusion
   does not clear.
