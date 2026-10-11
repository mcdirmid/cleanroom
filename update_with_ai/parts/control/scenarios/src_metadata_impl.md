<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:12:02Z
CHANGE: Author control src_metadata_impl concrete scenarios
CODE_HASH: 05f2bff10eff
-->

# Concrete scenarios for `src_metadata_impl` (implementation)

Scenarios 1 through 6 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 7
through 11 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Reading the metadata, code body, and modification status of a clean file

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
   Realized by: the component's own comment boundary location and in-band field parsing, with the
   comment delimiters, header placement, and field grammar supplied by `src_metadata_ext`, and the
   `src_metadata` interface exposed within the active `agent_session`.

2. The caller asks for the code body of the file.
   Observed: `widget contract body`, with the metadata comment block absent from it.
   Realized by: the component's own extraction of the lines outside the located metadata comment
   boundaries, joined with whitespace stripped.

3. The caller asks whether the file has code modifications.
   Observed: no code modifications, because the code body on disk still hashes to `a1b2c3d4e5f6`,
   the code hash recorded in the file's metadata.
   Realized by: the component's own establishment of file existence on disk and its comparison of
   the recomputed code hash against the recorded in-band code hash.

### Scenario 2 — Marking a modified file dirty, documenting the change, and marking it clean

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` is clean, its metadata
recording last cleaned `2026-01-02T03:04:05Z` and no dirty reason; the current UTC timestamp is
`2026-01-05T06:07:08Z`.

1. The caller marks the file dirty with the reason `the beta contract changed`.
   Observed: the file on disk records the dirty reason `the beta contract changed` and no longer
   records a last cleaned timestamp.
   Realized by: the component's own document serialization, which rewrites the located comment
   block with the dirty reason and without a last cleaned timestamp, and its in-place file
   mutation, writing UTF-8 encoded text through the comment mechanics of `src_metadata_ext`.

2. The caller records the change summary `renamed the widget field` on the file.
   Observed: the file on disk records the change summary `renamed the widget field` and, being a
   modified file, a last changed timestamp of `2026-01-05T06:07:08Z`.
   Realized by: the component's own in-place header rewrite, which advances the last changed
   timestamp to the current UTC timestamp and writes the change summary into the block.

3. The caller marks the file clean.
   Observed: the file on disk records last cleaned `2026-01-05T06:07:08Z` and no dirty reason.
   Realized by: the component's own in-place header rewrite, which advances the last cleaned
   timestamp to the current UTC timestamp and clears the dirty reason.

### Scenario 3 — Appending unacted feedback and stamping and clearing a role audit

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` is dirty with the reason
`the beta contract changed`; its metadata records the unacted feedback items `the beta contract
changed` and `the gamma contract changed`, and a role audit timestamp `2026-01-04T00:00:00Z` for
role beta; the current UTC timestamp is `2026-01-06T00:00:00Z`.

1. The caller appends an unacted feedback item carrying the explanation
   `the widget field type is not accepted`.
   Observed: the file on disk records three unacted feedback items, the two it already held and
   `the widget field type is not accepted`.
   Realized by: the component's own in-place header rewrite, which appends the entry to the
   unacted feedback list under the feedback grammar of `src_metadata_ext`.

2. The caller stamps a role audit for role alpha.
   Observed: the file on disk records a role audit timestamp `2026-01-06T00:00:00Z` for role
   alpha, alongside the role beta audit at `2026-01-04T00:00:00Z`.
   Realized by: the component's own role audit stamping inside the rewritten comment block,
   writing the current UTC timestamp against the named role.

3. The caller clears the role audit for role alpha.
   Observed: the file on disk records no role audit timestamp for role alpha and still records the
   role beta audit at `2026-01-04T00:00:00Z`.
   Realized by: the component's own removal of that role's audit timestamp from the rewritten
   comment block, which leaves the other roles' stamps in place.

### Scenario 4 — Rewriting metadata in a content string without updating the file on disk

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` is clean and its metadata
records last cleaned `2026-01-02T03:04:05Z`; the caller holds the content of that file as a content
string.

1. The caller asks for the content string rewritten with the file marked dirty for the reason
   `the gamma contract changed`.
   Observed: the returned content string records the dirty reason `the gamma contract changed` and
   no last cleaned timestamp.
   Realized by: the component's own serialization over the supplied content string, which replaces
   the located comment block slice with the updated block.

2. The caller asks for the metadata of the file on disk.
   Observed: still last cleaned `2026-01-02T03:04:05Z` and no dirty reason, because no file on
   disk was updated.
   Realized by: the component's own separation of content-string rewriting from in-place file
   mutation, so that only the latter reaches disk.

3. The caller asks for the content string rewritten with the last cleaned timestamp deleted.
   Observed: the returned content string records no last cleaned timestamp, while the file on disk
   still records last cleaned `2026-01-02T03:04:05Z`.
   Realized by: the component's own serialization of a block that omits the last cleaned field,
   again without an in-place file mutation.

### Scenario 5 — Marking a file clean when it carries no metadata comment block

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` carries no metadata
comment block, and the current UTC timestamp is `2026-01-07T08:09:10Z`.

1. The caller asks for the metadata of the file.
   Observed: a record with no last cleaned timestamp, no last changed timestamp, no change summary,
   no unacted feedback items, no role audit timestamp for any role, no dirty reason, and no code
   hash.
   Realized by: the component's own boundary location, which finds no metadata comment markers and
   yields a record whose every attribute is unset.

2. The caller marks the file clean.
   Observed: the file on disk now records last cleaned `2026-01-07T08:09:10Z` and no dirty reason.
   Realized by: the component's own insertion of a new metadata comment block at the placement the
   format conventions of `src_metadata_ext` require, followed by its in-place file mutation.

### Scenario 6 — The same code body yielding the same code hash

Given: the workspace files `/ws/alpha_scope_a/parts/widget/widget_spec.md` and
`/ws/alpha_scope_a/parts/gadget/gadget_spec.md` have the identical code body
`widget contract body` and differ only in their metadata comment blocks; the metadata of the widget
file records code hash `a1b2c3d4e5f6`.

1. The caller asks for the code hash of each file.
   Observed: one and the same code hash for both files, because their code bodies are identical.
   Realized by: the component's own code body extraction, which strips whitespace from the lines
   outside the comment boundaries, and its hashing of that body, which depends on nothing else.

2. The caller changes the code body of the widget file to `widget contract statement` and asks for
   its code hash again.
   Observed: a code hash that differs from the code hash of the gadget file.
   Realized by: the same extraction and hashing path over the new body.

3. The caller asks whether the widget file has code modifications.
   Observed: code modifications, because the code body `widget contract statement` no longer hashes
   to `a1b2c3d4e5f6`.
   Realized by: the component's own comparison of the recomputed code hash against the recorded
   in-band code hash.

## Implementation-only

### Scenario 7 — What the code hash is taken over

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` has the code body
`  widget contract body` with two leading spaces and a trailing newline, and the workspace file
`/ws/alpha_scope_a/parts/gadget/gadget_spec.md` has the code body `widget contract body` with no
surrounding whitespace.

1. The caller asks for the code hash of each file.
   Observed: one and the same twelve-character hexadecimal code hash for both files, being the
   first twelve hexadecimal characters of the SHA-256 digest of the whitespace-stripped code body.
   Realized by: the component's own whitespace stripping of the extracted code body followed by
   its SHA-256 digest, of which only the leading twelve hexadecimal characters are recorded.

2. The caller asks for the code hash of a file whose code body is `widget contract statement`.
   Observed: a different twelve-character hexadecimal code hash.
   Realized by: the same stripping and digesting path over the changed body.

### Scenario 8 — Where a metadata comment block sits in each file format

Given: the workspace holds a Markdown specification whose frontmatter delimiter precedes a block
written between HTML comment markers, a Python source file whose shebang line and encoding
directive precede a block written in line hash comments, a Starlark build file whose block is
written in line hash comments, and a shell script whose shebang line precedes a block written in
line hash comments.

1. The caller asks for the metadata of each of the four files.
   Observed: for each file the timestamps, change summary, unacted feedback items, role audits, and
   code hash recorded in its own block, with the frontmatter delimiter, the shebang lines, and the
   encoding directive preserved outside the block.
   Realized by: the comment syntax, header placement, and boundary extraction conventions of
   `src_metadata_ext`, applied by the component's own boundary location.

### Scenario 9 — Writing a metadata block into a file that does not exist yet

Given: no file exists at `/ws/alpha_scope_a/parts/sprocket/sprocket_spec.md`, and the directory
`/ws/alpha_scope_a/parts/sprocket` does not exist; the current UTC timestamp is
`2026-01-08T00:00:00Z`.

1. The caller marks that file clean.
   Observed: the directory `/ws/alpha_scope_a/parts/sprocket` and a UTF-8 encoded file now exist,
   and the file records last cleaned `2026-01-08T00:00:00Z` with no dirty reason.
   Realized by: the component's own in-place mutation, which reads the absent content as empty,
   creates the missing parent directory, and writes the UTF-8 encoded text.

2. The caller asks for the code body of the file.
   Observed: empty, because the file holds nothing outside its metadata comment block.
   Realized by: the component's own code body extraction over a file with no lines outside the
   block.

### Scenario 10 — Placing a new block below directives inside a content string

Given: the caller holds, as a content string, a Python module whose first line is
`#!/usr/bin/env python3`, whose second line is `# -*- coding: utf-8 -*-`, and whose remaining lines
are `widget = 1` and `gadget = 2`; the caller also holds, as a content string, a Markdown
specification whose frontmatter delimiter is followed by the body line `widget contract body`; the
current UTC timestamp is `2026-01-10T00:00:00Z`.

1. The caller asks for the Python content string rewritten with the file marked clean.
   Observed: the returned string still begins with `#!/usr/bin/env python3` and
   `# -*- coding: utf-8 -*-`, then carries a metadata comment block recording last cleaned
   `2026-01-10T00:00:00Z`, then the unchanged lines `widget = 1` and `gadget = 2`.
   Realized by: the component's own serialization, which inserts the new block below the shebang
   and encoding directive as the placement rules of `src_metadata_ext` require.

2. The caller asks for the Markdown content string rewritten with the file marked clean.
   Observed: the returned string keeps the frontmatter delimiter above a metadata comment block
   recording last cleaned `2026-01-10T00:00:00Z`, then the unchanged line
   `widget contract body`.
   Realized by: the component's own serialization, which inserts the new block after the
   frontmatter delimiter as those same placement rules require.

### Scenario 11 — Advancing lifecycle stamps while feedback is appended

Given: the workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` is dirty with the reason
`the beta contract changed`, records no last cleaned timestamp, and holds the unacted feedback item
`the gamma contract changed`; the current UTC timestamp is `2026-01-11T00:00:00Z`.

1. The caller appends the unacted feedback item `the widget field type is not accepted`.
   Observed: the file on disk records both `the gamma contract changed` and
   `the widget field type is not accepted` as unacted feedback items, and stays dirty with the
   reason `the beta contract changed`.
   Realized by: the component's own in-place header rewrite, which appends to the existing
   feedback list without disturbing the remaining fields.

2. The caller marks the file clean.
   Observed: the file on disk records last cleaned `2026-01-11T00:00:00Z` and no dirty reason.
   Realized by: the component's own in-place header rewrite, advancing the last cleaned timestamp
   to the current UTC timestamp and clearing the dirty reason.
