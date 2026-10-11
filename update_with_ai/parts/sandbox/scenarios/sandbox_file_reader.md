<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:12:00Z
CHANGE: Author sandbox sandbox_file_reader concrete scenarios
CODE_HASH: cc6e4ebec450
-->

# Concrete scenarios for `sandbox_file_reader` (interface)

## Scenario 1 — Viewing a declared read-only file

Given: the agent session declares `contract.md` as a read-only file whose content is the two lines
"# Contract" and "value must be positive", and declares no read-write files.

1. The caller views `contract.md`.
   Observed: the view succeeds and reports the content of `contract.md`, both the line
   "# Contract" and the line "value must be positive".

## Scenario 2 — Viewing a declared read-write file

Given: the agent session declares `widget.py` as a read-write file whose content is the two lines
"value = 1" and "print(value)", and declares no read-only files.

1. The caller views `widget.py`.
   Observed: the view succeeds and reports the content of `widget.py`, both the line "value = 1"
   and the line "print(value)".

## Scenario 3 — Viewing a file the session does not declare

Given: the agent session declares `contract.md` as a read-only file and `widget.py` as a read-write
file, and declares no file named `sprocket.py`.

1. The caller views `sprocket.py`.
   Observed: the view fails with guidance listing `contract.md` and `widget.py` as the readable file
   aliases, and no file content is reported.

## Scenario 4 — The files the session makes readable

Given: the agent session declares `contract.md` as a read-only file and `widget.py` and `gadget.py`
as read-write files, and declares no other files.

1. The caller asks which files the session makes readable.
   Observed: the reported read-only files are `contract.md` alone, and the reported read-write files
   are `widget.py` and `gadget.py`.

## Scenario 5 — Checking read access for a declared and an undeclared file

Given: the agent session declares `contract.md` as a read-only file and `widget.py` as a read-write
file, and declares no file named `sprocket.py`.

1. The caller asks whether `contract.md` can be read.
   Observed: read access is confirmed for `contract.md`.

2. The caller asks whether `sprocket.py` can be read.
   Observed: read access is refused with guidance listing `contract.md` and `widget.py` as the
   readable file aliases.

## Scenario 6 — Searching the declared files for a pattern

Given: the agent session declares `contract.md` as a read-only file holding the line "value must be
positive" and `widget.py` as a read-write file holding the line "value = 1".

1. The caller searches the session's files for the pattern "value".
   Observed: the search reports the matching line "value must be positive" from `contract.md` and
   reports that `widget.py` also holds a matching line.

2. The caller searches the session's files for the pattern "sprocket".
   Observed: the search reports no matches.
