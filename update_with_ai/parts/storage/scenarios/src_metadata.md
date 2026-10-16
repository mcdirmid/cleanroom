<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:12:01Z
CHANGE: Author control src_metadata concrete scenarios
CODE_HASH: 1ed050c44e90
-->

# Concrete scenarios for `src_metadata` (interface)

## Scenario 1 — Reading the metadata, code body, and modification status of a clean file

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` holds a metadata comment
block recording last cleaned `2026-01-02T03:04:05Z`, last changed `2026-01-01T09:00:00Z`, change
summary `split the widget contract`, one unacted feedback item carrying the explanation
`the widget field type is not accepted`, no role audit timestamp for any role, no dirty reason, and
code hash `a1b2c3d4e5f6`; the code body of that file is `widget contract body`.

1. The caller asks for the metadata of the file.
   Observed: a record reporting last cleaned `2026-01-02T03:04:05Z`, last changed
   `2026-01-01T09:00:00Z`, change summary `split the widget contract`, one unacted feedback item
   carrying `the widget field type is not accepted`, code hash `a1b2c3d4e5f6`, no role audit
   timestamp for any role, and no dirty reason.

2. The caller asks for the code body of the file.
   Observed: `widget contract body`, with the metadata comment block absent from it.

3. The caller asks whether the file has code modifications.
   Observed: no code modifications, because the code body on disk still hashes to `a1b2c3d4e5f6`,
   the code hash recorded in the file's metadata.

## Scenario 2 — Marking a modified file dirty, documenting the change, and marking it clean

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` is clean, its metadata
recording last cleaned `2026-01-02T03:04:05Z` and no dirty reason; the current UTC timestamp is
`2026-01-05T06:07:08Z`.

1. The caller marks the file dirty with the reason `the beta contract changed`.
   Observed: the file on disk records the dirty reason `the beta contract changed` and no longer
   records a last cleaned timestamp.

2. The caller records the change summary `renamed the widget field` on the file.
   Observed: the file on disk records the change summary `renamed the widget field` and, being a
   modified file, a last changed timestamp of `2026-01-05T06:07:08Z`.

3. The caller marks the file clean.
   Observed: the file on disk records last cleaned `2026-01-05T06:07:08Z` and no dirty reason.

## Scenario 3 — Appending unacted feedback and stamping and clearing a role audit

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` is dirty with the reason
`the beta contract changed`; its metadata records the unacted feedback items `the beta contract
changed` and `the gamma contract changed`, and a role audit timestamp `2026-01-04T00:00:00Z` for
role beta; the current UTC timestamp is `2026-01-06T00:00:00Z`.

1. The caller appends an unacted feedback item carrying the explanation
   `the widget field type is not accepted`.
   Observed: the file on disk records three unacted feedback items, the two it already held and
   `the widget field type is not accepted`.

2. The caller stamps a role audit for role alpha.
   Observed: the file on disk records a role audit timestamp `2026-01-06T00:00:00Z` for role
   alpha, alongside the role beta audit at `2026-01-04T00:00:00Z`.

3. The caller clears the role audit for role alpha.
   Observed: the file on disk records no role audit timestamp for role alpha and still records the
   role beta audit at `2026-01-04T00:00:00Z`.

## Scenario 4 — Rewriting metadata in a content string without updating the file on disk

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` is clean and its metadata
records last cleaned `2026-01-02T03:04:05Z`; the caller holds the content of that file as a content
string.

1. The caller asks for the content string rewritten with the file marked dirty for the reason
   `the gamma contract changed`.
   Observed: the returned content string records the dirty reason `the gamma contract changed` and
   no last cleaned timestamp.

2. The caller asks for the metadata of the file on disk.
   Observed: still last cleaned `2026-01-02T03:04:05Z` and no dirty reason, because no file on
   disk was updated.

3. The caller asks for the content string rewritten with the last cleaned timestamp deleted.
   Observed: the returned content string records no last cleaned timestamp, while the file on disk
   still records last cleaned `2026-01-02T03:04:05Z`.

## Scenario 5 — Marking a file clean when it carries no metadata comment block

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` carries no metadata
comment block, and the current UTC timestamp is `2026-01-07T08:09:10Z`.

1. The caller asks for the metadata of the file.
   Observed: a record with no last cleaned timestamp, no last changed timestamp, no change summary,
   no unacted feedback items, no role audit timestamp for any role, no dirty reason, and no code
   hash.

2. The caller marks the file clean.
   Observed: the file on disk now records last cleaned `2026-01-07T08:09:10Z` and no dirty reason.

## Scenario 6 — The same code body yielding the same code hash

Given: the workspace files `/ws/alpha_scope_a/parts/widget/widget_spec.md` and
`/ws/alpha_scope_a/parts/gadget/gadget_spec.md` have the identical code body
`widget contract body` and differ only in their metadata comment blocks; the metadata of the widget
file records code hash `a1b2c3d4e5f6`.

1. The caller asks for the code hash of each file.
   Observed: one and the same code hash for both files, because their code bodies are identical.

2. The caller changes the code body of the widget file to `widget contract statement` and asks for
   its code hash again.
   Observed: a code hash that differs from the code hash of the gadget file.

3. The caller asks whether the widget file has code modifications.
   Observed: code modifications, because the code body `widget contract statement` no longer hashes
   to `a1b2c3d4e5f6`.
