<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:12:01Z
CHANGE: Author sandbox file_reader_impl concrete scenarios
CODE_HASH: c9a2868c9b53
-->

# Concrete scenarios for `file_reader_impl` (implementation)

Scenarios 1 through 6 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 7 through
11 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Viewing a declared read-only file

Given: the agent session declares `contract.md` as a read-only file whose content is the two lines
"# Contract" and "value must be positive", and declares no read-write files.

1. The caller views `contract.md`.
   Observed: the view succeeds and reports the content of `contract.md`, both the line
   "# Contract" and the line "value must be positive".
   Realized by: alias resolution through `agent_file_alias` against the read-only files supplied by
   `agent_node_config`, content reading through `filesystem_ext`, and the component's own
   line-numbered rendering of that content.

### Scenario 2 — Viewing a declared read-write file

Given: the agent session declares `widget.py` as a read-write file whose content is the two lines
"value = 1" and "print(value)", and declares no read-only files.

1. The caller views `widget.py`.
   Observed: the view succeeds and reports the content of `widget.py`, both the line "value = 1"
   and the line "print(value)".
   Realized by: alias resolution through `agent_file_alias` against the read-write files supplied by
   `agent_node_config`, content reading through `filesystem_ext`, the component's own line-numbered
   rendering, and the read-write response suppression key through `tool_provider`.

### Scenario 3 — Viewing a file the session does not declare

Given: the agent session declares `contract.md` as a read-only file and `widget.py` as a read-write
file, and declares no file named `sprocket.py`.

1. The caller views `sprocket.py`.
   Observed: the view fails with guidance listing `contract.md` and `widget.py` as the readable file
   aliases, and no file content is reported.
   Realized by: the component's own read-access check, whose refusal guidance lists the readable
   file aliases drawn from `agent_node_config` and resolved through `agent_file_alias`.

### Scenario 4 — The files the session makes readable

Given: the agent session declares `contract.md` as a read-only file and `widget.py` and `gadget.py`
as read-write files, and declares no other files.

1. The caller asks which files the session makes readable.
   Observed: the reported read-only files are `contract.md` alone, and the reported read-write files
   are `widget.py` and `gadget.py`.
   Realized by: the declared read-only and read-write files of the session configuration supplied by
   `agent_node_config`, resolved through `agent_file_alias`.

### Scenario 5 — Checking read access for a declared and an undeclared file

Given: the agent session declares `contract.md` as a read-only file and `widget.py` as a read-write
file, and declares no file named `sprocket.py`.

1. The caller asks whether `contract.md` can be read.
   Observed: read access is confirmed for `contract.md`.
   Realized by: the component's own read-access check over the declared files supplied by
   `agent_node_config` and resolved through `agent_file_alias`.

2. The caller asks whether `sprocket.py` can be read.
   Observed: read access is refused with guidance listing `contract.md` and `widget.py` as the
   readable file aliases.
   Realized by: the component's own read-access failure, whose guidance lists the readable file
   aliases.

### Scenario 6 — Searching the declared files for a pattern

Given: the agent session declares `contract.md` as a read-only file holding the line "value must be
positive" and `widget.py` as a read-write file holding the line "value = 1".

1. The caller searches the session's files for the pattern "value".
   Observed: the search reports the matching line "value must be positive" from `contract.md` and
   reports that `widget.py` also holds a matching line.
   Realized by: regular expression line scanning through `filesystem_ext` over the declared files
   from `agent_node_config`, and the component's own edit-safety guard, which states that matches in
   a read-write file were found but cannot be displayed.

2. The caller searches the session's files for the pattern "sprocket".
   Observed: the search reports no matches.
   Realized by: the same scan through `filesystem_ext`, which finds no matching line.

## Implementation-only

### Scenario 7 — Numbered lines in a viewed file

Given: the agent session declares `contract.md` as a read-only file holding the ten lines "rule 1"
through "rule 10".

1. The caller views `contract.md`.
   Observed: the view succeeds and reports the ten lines each prefixed by its one-indexed,
   right-aligned line number followed by a colon and a space, so the ninth line is reported as
   " 9: rule 9" and the tenth as "10: rule 10".
   Realized by: content reading through `filesystem_ext` and the component's own line-number
   formatting of that content.

### Scenario 8 — Template placeholders in a read-only markdown file

Given: the agent session declares `guide.md` as a read-only file whose content is the three
paragraphs "Step one for <role>.", "> META: internal note for <role>.", and "Step two is final.",
and the session's template parameters bind `role` to "alpha".

1. The caller views `guide.md`.
   Observed: the view succeeds and reports "Step one for alpha." and "Step two is final.", with the
   paragraph beginning "> META:" left out of the rendered instructions.
   Realized by: template evaluation through `template_format` with the template parameters supplied
   by `agent_node_config`, and the component's own filtering of paragraphs that begin with
   "> META:".

### Scenario 9 — A missing read-write file and a missing read-only file

Given: the agent session declares `widget.py` as a read-write file and `contract.md` as a read-only
file, and no file exists at either `widget.py` or `contract.md`.

1. The caller views `widget.py`.
   Observed: the view succeeds and reports empty content for `widget.py`.
   Realized by: `filesystem_ext` reporting the absent file and the component's own treatment of a
   missing read-write file as empty content.

2. The caller views `contract.md`.
   Observed: the view fails, the response guides the agent's recovery, and no file content is
   reported.
   Realized by: `filesystem_ext` reporting the absent file and the component's own failure when a
   required read-only file is missing from disk.

### Scenario 10 — Suppression keys and host path masking

Given: the agent session declares `contract.md` as a read-only file holding the single line
"This file lives at /ws/alpha_scope_a/contract.md" and `widget.py` as a read-write file holding the
single line "value = 1".

1. The caller views `widget.py`.
   Observed: the view succeeds, reports the content of `widget.py`, and carries a suppression key
   equal to the relative path `widget.py`, so that a later view of `widget.py` supersedes this
   response.
   Realized by: the response suppression mechanism of `tool_provider`, keyed by the relative path
   supplied by `agent_file_alias`.

2. The caller views `contract.md`.
   Observed: the view succeeds and reports the line "This file lives at contract.md", carrying no
   suppression key.
   Realized by: the masking performed by `agent_file_alias`, which hides the workspace directory
   behind the file alias relative path, and the component's own omission of a suppression key for
   read-only file responses.

### Scenario 11 — A malformed search pattern and a guarded read-write search

Given: the agent session declares `contract.md` as a read-only file holding the line "value must be
positive" and `widget.py` as a read-write file holding the line "value = 1".

1. The caller searches the session's files for the pattern "value(".
   Observed: the search fails because the pattern is not a valid regular expression, and no matching
   lines are reported.
   Realized by: the component's own regex pattern parameter type, whose conversion of the wire
   string into a pattern fails, and the component's own propagation of that failure.

2. The caller searches the session's files for the pattern "value".
   Observed: the search reports the matching line "value must be positive" from `contract.md` with
   its line number, and states that `widget.py` holds a matching line that cannot be displayed
   without viewing the file directly.
   Realized by: regular expression line scanning through `filesystem_ext` and the component's own
   edit-safety guard over read-write file matches.
