<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:11:14Z
CHANGE: Author agent agent_node_config interface scenarios
CODE_HASH: 2edcb8d7679d
-->

# Concrete scenarios for `agent_node_config` (interface)

## Scenario 1 — The files the session restricts to reading

Given: the active agent session config supplies the read-only files
`widget/contracts/widget.md` and `gadget/contracts/gadget.md`.

1. The caller reads the read-only files of the session config.
   Observed: exactly the two entries `widget/contracts/widget.md` and
   `gadget/contracts/gadget.md`, and no other file.

## Scenario 2 — The files the session permits for reading and writing

Given: the active agent session config supplies the read-write files `widget/notes/draft.md` and
`widget/src/widget.py`.

1. The caller reads the read-write files of the session config.
   Observed: exactly the two entries `widget/notes/draft.md` and `widget/src/widget.py`, and no
   other file.

## Scenario 3 — Reading and writing the same file kinds as the session config

Given: the active agent session config supplies the read-only file `widget/contracts/widget.md` and
the read-write file `widget/notes/draft.md`, and the widget node declares
`widget/contracts/widget.md` as a read-only file and `widget/notes/draft.md` as a read-write file.

1. The caller reads the read-write files and the read-only files of the session config.
   Observed: `widget/notes/draft.md` is reported among the read-write files,
   `widget/contracts/widget.md` is reported among the read-only files, and neither file is reported
   under the other kind.

## Scenario 4 — The session guide when step mode is active

Given: step mode is active, and the session guide holds the summary `clean the widget target`, the
step section numbered 1 titled `Inspect the widget contract` with its content, the step section
numbered 2 titled `Clean the widget source` with its content, and the verification failure
instruction whose text is `report the failing widget contract line`.

1. The caller reads the session guide of the session config.
   Observed: the guide carries the summary `clean the widget target`, step sections 1 and 2 in
   order, and the verification failure instruction `report the failing widget contract line`.

2. The caller asks for the step sections of that guide.
   Observed: two step sections, numbered 1 and 2, titled `Inspect the widget contract` and
   `Clean the widget source`, each carrying its content and no other section.

## Scenario 5 — The session config while step mode is inactive

Given: step mode is inactive, and the session guide holds the summary `clean the widget target`.

1. The caller reads the session guide of the session config.
   Observed: no session guide is provided, so the summary `clean the widget target` and the step
   sections are not reported, and the read fails explicitly rather than reporting a guide without
   step mode.

## Scenario 6 — A verification check that fails and one that passes

Given: the session config supplies the verification check whose criteria is
`widget/src/widget.py imports no undeclared module` and the verification check whose criteria is
`widget/notes/draft.md exists`.

1. The caller evaluates the first verification check against a session in which
   `widget/src/widget.py` imports the module `sprocket_helpers`.
   Observed: the check communicates that verification did not pass, together with the diagnostic
   feedback `widget/src/widget.py imports the undeclared module sprocket_helpers`.

2. The caller evaluates the second verification check against a session in which
   `widget/notes/draft.md` exists.
   Observed: the check communicates that verification passed.

## Scenario 7 — The verification success message

Given: the session config supplies the verification success message
`widget verification passed: the draft and the widget source agree`, the verification check whose
criteria is `widget/notes/draft.md exists`, and a session in which `widget/notes/draft.md` exists.

1. The caller evaluates that verification check and reads the verification success message.
   Observed: the check communicates that verification passed, and the success message is
   `widget verification passed: the draft and the widget source agree`.

## Scenario 8 — Templates and template parameters

Given: the session config supplies the template mapping the read-write file `widget/notes/draft.md`
to the initial file content `draft for [[unit]] at [[timestamp]]` and the template parameters
binding the value `widget` for the name `unit` and the value `2026-01-02T03:04:05Z` for the name
`timestamp`.

1. The caller reads the templates of the session config.
   Observed: one template, mapping `widget/notes/draft.md` to the initial file content
   `draft for [[unit]] at [[timestamp]]`.

2. The caller reads the template parameters of the session config.
   Observed: two bindings, the value `widget` for the name `unit` and the value
   `2026-01-02T03:04:05Z` for the name `timestamp`, which are the values template evaluation uses
   for the initial file content of `widget/notes/draft.md`.

## Scenario 9 — Blame targets and session messages

Given: the session config supplies the blame targets mapping the read-write file
`widget/notes/draft.md` to the read-only file `widget/contracts/widget.md` and the session messages
mapping `widget/notes/draft.md` to the message `the widget contract requires two draft sections`.

1. The caller reads the blame targets of `widget/notes/draft.md` and the message recorded for it.
   Observed: the single blame target `widget/contracts/widget.md`, and the message
   `the widget contract requires two draft sections`.

2. The caller reads the blame targets of the read-write file `widget/src/widget.py`, which the
   session config supplies no blame target for.
   Observed: no blame target is reported, and the lookup fails explicitly rather than naming a
   substitute read-only file.

## Scenario 10 — The role config maintaining the active role and cleaned nodes

Given: the role config of the agent session holds no active role, holds no node being cleaned, and
names the execution version 1.

1. The caller sets the active role to `alpha`.
   Observed: the active role is `alpha`, no node is being cleaned, and the execution version remains
   1.

2. The caller updates the sequence of nodes being cleaned to name the widget node only.
   Observed: the active role is `alpha`, the sequence names the widget node only, and the execution
   version is 2.

3. The caller updates the sequence of nodes being cleaned to name the widget node, the gadget node,
   and the sprocket node in that order.
   Observed: the sequence names those three nodes in that order, and the execution version is 3.

4. The caller updates the sequence of nodes being cleaned to name no node.
   Observed: the sequence names no node, and the execution version is 4 because the cleaned nodes
   changed.
