<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T03:11:54Z
CHANGE: Author sandbox sandbox concrete scenarios
CODE_HASH: f61b9c33cafd
-->

# Concrete scenarios for `sandbox` (interface)

## Scenario 1 — A session that inspects a file without changing it

Given: an agent session for role alpha with no file modification yet, in which the agent reads the
workspace file `/ws/alpha_scope_a/widget.md` at 2026-01-02T03:04:05Z.

1. The agent asks whether workspace file modifications occurred during the session.
   Observed: no modifications occurred during the session.

## Scenario 2 — A session that changes one file

Given: an agent session for role beta with no file modification yet, the workspace file
`/ws/beta_scope_b/gadget.md` holding the line `gadget_height = 30`, and the session permitted to
change that file.

1. The agent changes the content of `/ws/beta_scope_b/gadget.md` at 2026-01-02T03:05:00Z to the line
   `gadget_height = 42`.
   Observed: the sandbox records a file modification for the session.

## Scenario 3 — A session that changes three files

Given: an agent session for role gamma with no file modification yet, and the workspace files
`/ws/gamma_scope_a/widget.md`, `/ws/gamma_scope_a/gadget.md`, and `/ws/gamma_scope_a/sprocket.md`
holding the lines `widget_height = 30`, `gadget_height = 30`, and `sprocket_height = 30`.

1. The agent changes the content of `/ws/gamma_scope_a/widget.md` at 2026-01-02T03:06:00Z to the line
   `widget_height = 42`, then changes the content of `/ws/gamma_scope_a/gadget.md` at
   2026-01-02T03:06:30Z to the line `gadget_height = 42`, then changes the content of
   `/ws/gamma_scope_a/sprocket.md` at 2026-01-02T03:07:00Z to the line `sprocket_height = 42`.
   Observed: the sandbox records a file modification for each of the three changes.

## Scenario 4 — A write that leaves the file content unchanged

Given: an agent session for role delta with no file modification yet, and the workspace file
`/ws/delta_scope_a/widget.md` holding the line `widget_height = 30`.

1. The agent changes the content of `/ws/delta_scope_a/widget.md` at 2026-01-02T03:08:00Z to the
   line `widget_height = 30`, which is the content the file already holds.
   Observed: the file content is unchanged by that write, and the sandbox records no file
   modification for the session.
