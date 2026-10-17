<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:59Z
CHANGE: Author sandbox file_editor concrete scenarios
CODE_HASH: ff02eca5383f
-->

# Concrete scenarios for `file_editor` (interface)

## Scenario 1 — Replacing one occurrence inside a declared line range

Given: the agent session declares `widget.py` as a read-write file whose content is the three lines
"import os", "value = 1", and "print(value)", and the session reports that no workspace file writes
have occurred yet.

1. The caller invokes the replace file content tool with the path `widget.py`, start line 2, end
   line 2, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool succeeds, `widget.py` now holds the three lines "import os", "value = 2", and
   "print(value)", and the session reports that workspace file writes have occurred.

## Scenario 2 — Replacing every occurrence inside a declared line range

Given: the agent session declares `widget.py` as a read-write file whose content is the four lines
"value = 1", "other = 2", "value = 1", and "value = 1".

1. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 3, target content "value = 1", replacement content "value = 5", and multiple replacements
   permitted.
   Observed: the tool succeeds and `widget.py` now holds the four lines "value = 5", "other = 2",
   "value = 5", and "value = 1".

## Scenario 3 — Refusing an edit to a file that is not a declared read-write file

Given: the agent session declares `widget.py` as a read-write file and `contract.md` as a read-only
file whose content is the single line "value = 1", and declares no file named `sprocket.py`.

1. The caller invokes the replace file content tool with the path `contract.md`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool fails explicitly, `contract.md` still holds the single line "value = 1", and
   the session reports that no workspace file writes have occurred.

2. The caller invokes the replace file content tool with the path `sprocket.py`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool fails explicitly and the session reports that no workspace file writes have
   occurred.

## Scenario 4 — A file hash computed from the file's content

Given: the agent session declares `widget.py` and `gadget.py` as read-write files, `widget.py`
holding the single line "value = 1" and `gadget.py` holding the single line "value = 1".

1. The caller asks for the file hash of `widget.py` and for the file hash of `gadget.py`.
   Observed: a file hash is reported for each file, and the two reported hashes are equal.

2. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool succeeds and `widget.py` now holds the single line "value = 2".

3. The caller asks again for the file hash of `widget.py` and for the file hash of `gadget.py`.
   Observed: the hash reported for `widget.py` differs from the hash reported for it in step 1,
   while the hash reported for `gadget.py` is the same as the hash reported for it in step 1.

## Scenario 5 — A file update revision that tracks sequential updates

Given: the agent session declares `widget.py` as a read-write file holding the single line
"value = 1".

1. The caller asks for the file update revision.
   Observed: a file update revision is reported.

2. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool succeeds, `widget.py` now holds the single line "value = 2", and the file
   update revision reported afterwards is one greater than the revision reported in step 1.

3. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 1, target content "value = 2", replacement content "value = 3", and multiple replacements
   not permitted.
   Observed: the tool succeeds, `widget.py` now holds the single line "value = 3", and the file
   update revision reported afterwards is two greater than the revision reported in step 1.

## Scenario 6 — The session's last read or edited file

Given: the agent session declares `widget.py` and `gadget.py` as read-write files and reports no
last read or edited file.

1. The caller informs the session that `widget.py` was read.
   Observed: the session reports `widget.py` as the last read or edited file.

2. The caller informs the session that `gadget.py` was edited.
   Observed: the session reports `gadget.py` as the last read or edited file.

## Scenario 7 — Validating write access for declared files

Given: the agent session declares `widget.py` and `gadget.py` as read-write files and `contract.md`
as a read-only file, and declares no file named `sprocket.py`.

1. The caller asks whether `widget.py` can be written.
   Observed: write access is permitted for `widget.py`.

2. The caller asks whether `contract.md` can be written.
   Observed: write access is refused for `contract.md`.

3. The caller asks whether `sprocket.py` can be written.
   Observed: write access is refused for `sprocket.py`.

## Scenario 8 — Guarding metadata header, whitespace tolerance, and edit delta

Given: the agent session declares `widget.py` as a read-write file starting with the metadata header `# --- CLEANROOM METADATA ---` and containing the line `    value = 1  `, with edit delta output configured.

1. The caller attempts to replace content that alters `# --- CLEANROOM METADATA ---`.
   Observed: the tool refuses the edit explicitly, preserving the metadata block unaltered.

2. The caller invokes the replace file content tool with target content `value = 1` matching with normalized whitespace.
   Observed: the tool succeeds via whitespace-tolerant line matching and appends a unified diff to the response output.
