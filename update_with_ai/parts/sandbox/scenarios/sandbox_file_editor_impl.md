<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T21:57:18Z
LAST_CHANGED: 2026-10-11T03:12:00Z
CHANGE: Author sandbox sandbox_file_editor_impl concrete scenarios
CODE_HASH: 6dff0f75ba57
-->

# Concrete scenarios for `sandbox_file_editor_impl` (implementation)

Scenarios 1 through 7 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 8 through
12 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Replacing one occurrence inside a declared line range

Given: the agent session declares `widget.py` as a read-write file whose content is the three lines
"import os", "value = 1", and "print(value)", and the session reports that no workspace file writes
have occurred yet.

1. The caller invokes the replace file content tool with the path `widget.py`, start line 2, end
   line 2, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool succeeds, `widget.py` now holds the three lines "import os", "value = 2", and
   "print(value)", and the session reports that workspace file writes have occurred.
   Realized by: the tool's registration, parameter conversion, and constant response suppression key
   through `tool_provider`; alias resolution through `agent_file_alias` against the read-write files
   of the session configuration supplied by `agent_node_config`; content reading and the write of
   the updated content through `filesystem_ext`; and in-band code hash comparison through
   `src_metadata`, which reports that workspace file writes occurred.

### Scenario 2 — Replacing every occurrence inside a declared line range

Given: the agent session declares `widget.py` as a read-write file whose content is the four lines
"value = 1", "other = 2", "value = 1", and "value = 1".

1. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 3, target content "value = 1", replacement content "value = 5", and multiple replacements
   permitted.
   Observed: the tool succeeds and `widget.py` now holds the four lines "value = 5", "other = 2",
   "value = 5", and "value = 1".
   Realized by: the same registration and alias resolution through `tool_provider`,
   `agent_file_alias`, and `agent_node_config`; content reading and writing through
   `filesystem_ext`; and the component's own handling of permitted multiple replacements across the
   supplied line range.

### Scenario 3 — Refusing an edit to a file that is not a declared read-write file

Given: the agent session declares `widget.py` as a read-write file and `contract.md` as a read-only
file whose content is the single line "value = 1", and declares no file named `sprocket.py`.

1. The caller invokes the replace file content tool with the path `contract.md`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool fails explicitly, `contract.md` still holds the single line "value = 1", and
   the session reports that no workspace file writes have occurred.
   Realized by: alias resolution through `agent_file_alias`, whose declared read-only file kind
   comes from `agent_node_config`, and the component's own refusal, which names the offending target
   and reminds the agent that only declared read-write files can be written.

2. The caller invokes the replace file content tool with the path `sprocket.py`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool fails explicitly and the session reports that no workspace file writes have
   occurred.
   Realized by: alias resolution through `agent_file_alias`, which yields an unbound file for a name
   that is not a declared bound file, and the component's own refusal.

### Scenario 4 — A file hash computed from the file's content

Given: the agent session declares `widget.py` and `gadget.py` as read-write files, `widget.py`
holding the single line "value = 1" and `gadget.py` holding the single line "value = 1".

1. The caller asks for the file hash of `widget.py` and for the file hash of `gadget.py`.
   Observed: a file hash is reported for each file, and the two reported hashes are equal.
   Realized by: alias resolution through `agent_file_alias` to the bound read-write files, content
   reading through `filesystem_ext` at the resolved host path, and the component's own file hash
   computation over that content.

2. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool succeeds and `widget.py` now holds the single line "value = 2".
   Realized by: the write path through `tool_provider`, `agent_file_alias`, and `filesystem_ext`,
   and the component's own replacement of the target content.

3. The caller asks again for the file hash of `widget.py` and for the file hash of `gadget.py`.
   Observed: the hash reported for `widget.py` differs from the hash reported for it in step 1,
   while the hash reported for `gadget.py` is the same as the hash reported for it in step 1.
   Realized by: the component's own file hash computation, re-reading content through
   `filesystem_ext`.

### Scenario 5 — A file update revision that tracks sequential updates

Given: the agent session declares `widget.py` as a read-write file holding the single line
"value = 1".

1. The caller asks for the file update revision.
   Observed: a file update revision is reported.
   Realized by: the component's own file update revision, which every workspace file write advances.

2. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool succeeds, `widget.py` now holds the single line "value = 2", and the file
   update revision reported afterwards is one greater than the revision reported in step 1.
   Realized by: the write through `filesystem_ext` and the component's own increment of the file
   update revision when workspace files are updated.

3. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 1, target content "value = 2", replacement content "value = 3", and multiple replacements
   not permitted.
   Observed: the tool succeeds, `widget.py` now holds the single line "value = 3", and the file
   update revision reported afterwards is two greater than the revision reported in step 1.
   Realized by: the same write path and the component's own successive increment of the file update
   revision.

### Scenario 6 — The session's last read or edited file

Given: the agent session declares `widget.py` and `gadget.py` as read-write files and reports no
last read or edited file.

1. The caller informs the session that `widget.py` was read.
   Observed: the session reports `widget.py` as the last read or edited file.
   Realized by: the component's own last-read-or-edited record, written by the session recording a
   file read.

2. The caller informs the session that `gadget.py` was edited.
   Observed: the session reports `gadget.py` as the last read or edited file.
   Realized by: the component's own last-read-or-edited record, written by the session recording a
   file edit.

### Scenario 7 — Validating write access for declared files

Given: the agent session declares `widget.py` and `gadget.py` as read-write files and `contract.md`
as a read-only file, and declares no file named `sprocket.py`.

1. The caller asks whether `widget.py` can be written.
   Observed: write access is permitted for `widget.py`.
   Realized by: alias resolution through `agent_file_alias` against the read-write files supplied by
   `agent_node_config`, and the component's own write-access validation, which records the file edit
   in the session's edit manager when write access is permitted.

2. The caller asks whether `contract.md` can be written.
   Observed: write access is refused for `contract.md`.
   Realized by: alias resolution through `agent_file_alias` and the component's own write-access
   validation refusing a bound read-only file.

3. The caller asks whether `sprocket.py` can be written.
   Observed: write access is refused for `sprocket.py`.
   Realized by: alias resolution through `agent_file_alias`, which yields an unbound file, and the
   component's own write-access validation refusing it.

## Implementation-only

### Scenario 8 — A call that omits the target content

Given: the agent session declares `widget.py` as a read-write file holding the three lines
"import os", "value = 1", and "print(value)".

1. The caller invokes the replace file content tool with the path `widget.py`, start line 2, end
   line 2, replacement content "value = 2", and no target content.
   Observed: the call fails, the response explains that start line and end line restrict the search
   window only when line range arguments are supplied and that target content must match existing
   text to append or insert content when line range arguments are omitted, and `widget.py` still
   holds the three lines "import os", "value = 1", and "print(value)".
   Realized by: the missing note configured on the target content parameter through `tool_provider`,
   which builds it from the present parameter names, and the component's own failure for the omitted
   parameter.

### Scenario 9 — A target content that matches one whitespace-stripped line window

Given: the agent session declares `widget.py` as a read-write file holding the two lines
"if value:" and "    return 1".

1. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 2, target content the two lines "if value:" and "return 1", replacement content the two
   lines "if value:" and "    return 2", and multiple replacements not permitted.
   Observed: the tool succeeds and `widget.py` now holds the two lines "if value:" and
   "    return 2".
   Realized by: the component's own exact-match attempt, which finds no occurrence of the indented
   target text, its line-by-line whitespace-stripped match across the designated line range, which
   finds exactly one matching window, and content reading and writing through `filesystem_ext`.

### Scenario 10 — Feedback when the target content is ambiguous or lies outside the window

Given: the agent session declares `widget.py` as a read-write file holding the five lines
"import os", "value = 1", "other = 2", "value = 1", and "print(value)".

1. The caller invokes the replace file content tool with the path `widget.py`, target content
   "value = 1", no start line and no end line, replacement content "value = 5", and multiple
   replacements not permitted.
   Observed: the tool fails, the feedback indicates line 2 and line 4 as the first two matching line
   numbers, and `widget.py` still holds its five lines.
   Realized by: the component's own exact-match search, which finds several occurrences in the file,
   and the component's own failure feedback naming the first two matching line numbers.

2. The caller invokes the replace file content tool with the path `widget.py`, start line 5, end
   line 5, target content "value = 1", replacement content "value = 5", and multiple replacements
   not permitted.
   Observed: the tool fails, the feedback indicates line 2 and line 4 as the line numbers where the
   target content was located, and `widget.py` still holds its five lines.
   Realized by: the component's own search of the designated line range, which finds no occurrence
   there, followed by its own whole-file search that locates the target elsewhere.

### Scenario 11 — An omitted path bound to the last read or edited file

Given: the agent session declares `widget.py` and `gadget.py` as read-write files and `contract.md`
as a read-only file, `widget.py` holds the single line "value = 1", `contract.md` holds the single
line "value = 1", and no file has been read or edited in the session.

1. The caller invokes the replace file content tool with no path, start line 1, end line 1, target
   content "value = 1", replacement content "value = 2", and multiple replacements not permitted.
   Observed: the tool fails and `widget.py` still holds the single line "value = 1".
   Realized by: the component's own fallback to the session's last read or edited file, which finds
   none, and the component's own refusal.

2. The caller informs the session that `widget.py` was read.
   Observed: the session reports `widget.py` as the last read or edited file.
   Realized by: the component's own last-read-or-edited record, written by the session recording a
   file read.

3. The caller invokes the replace file content tool with no path, start line 1, end line 1, target
   content "value = 1", replacement content "value = 2", and multiple replacements not permitted.
   Observed: the tool succeeds against `widget.py`, warns the agent that the path was implicitly
   bound to `widget.py`, and `widget.py` now holds the single line "value = 2".
   Realized by: the component's own fallback to the last read or edited file of the session's edit
   manager, with the implicit-binding warning, and the write through `filesystem_ext`.

4. The caller informs the session that `contract.md` was read.
   Observed: the session reports `contract.md` as the last read or edited file.
   Realized by: the component's own last-read-or-edited record, written by the session recording a
   file read.

5. The caller invokes the replace file content tool with no path, start line 1, end line 1, target
   content "value = 1", replacement content "value = 2", and multiple replacements not permitted.
   Observed: the tool fails and `contract.md` still holds the single line "value = 1".
   Realized by: the component's own fallback to the last read or edited file, which is not a
   read-write file, and the component's own refusal.

### Scenario 12 — A no-change edit and a reported diff delta

Given: the session's delta output policy is configured, and the agent session declares `widget.py`
as a read-write file holding the single line "value = 1".

1. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 1", and multiple replacements
   not permitted.
   Observed: the tool fails, reminding the agent that the edit had no effect, and `widget.py` still
   holds the single line "value = 1".
   Realized by: the component's own comparison of the updated content against the original content,
   and the component's own reminder that the edit had no effect.

2. The caller invokes the replace file content tool with the path `widget.py`, start line 1, end
   line 1, target content "value = 1", replacement content "value = 2", and multiple replacements
   not permitted.
   Observed: the tool succeeds, `widget.py` now holds the single line "value = 2", and the response
   reports the change as a diff delta rather than the complete file content, carrying the constant
   suppression key shared by editing tool responses.
   Realized by: the delta output policy from `agent_config`, the component's own diff delta
   construction in the response, and the constant response suppression key through `tool_provider`.
