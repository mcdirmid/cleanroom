<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T03:23:52Z
CHANGE: Restrict reused scenarios to the declared imports closure and renumber
CODE_HASH: 756989ea38c7
-->

# Concrete scenarios for `uv_node_config_impl` (implementation)

Scenarios 1 through 27 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 28 through
32 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

The scenarios of the interfaces the component implements come in this order: `agent_file_alias` and
`agent_node_config`, followed by the scenarios of the interface specification of its imports
closure that it realizes: `tool_provider`.

### Scenario 1 — Converting a declared read-write file

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, and the widget
node declares the bound file whose workspace path is `widget/notes/draft.md` as a read-write file.

1. The caller converts the wire string `widget/notes/draft.md`.
   Observed: a bound file owning the workspace path `widget/notes/draft.md`, of the read-write kind,
   owned by the widget node, displaying itself as `widget/notes/draft.md`.
   Realized by: the component's own parameter conversion over file aliases, which matches the wire
   string against the bound files the widget node declares and keeps the read-write kind.

### Scenario 2 — Converting a declared read-only file

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, the widget node
declares the bound file whose workspace path is `widget/contracts/widget.md` as a read-only file,
and no target declares the workspace path `widget/notes/draft.md`.

1. The caller converts the wire string `widget/contracts/widget.md`.
   Observed: a bound file owning the workspace path `widget/contracts/widget.md`, of the read-only
   kind, owned by the widget node, displaying itself as `widget/contracts/widget.md`.
   Realized by: the component's own parameter conversion over file aliases, which keeps the
   read-only kind for a bound file the node declares read-only.

2. The caller converts the read-only file to a string.
   Observed: `widget/contracts/widget.md`, the file's relative path within the agent session rather
   than its physical filesystem location.
   Realized by: the component's own alias display path, which the component's workspace root
   resolution through `file_paths` keeps relative.

### Scenario 3 — A string that names no declared file

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, and no target
declares the workspace path `widget/notes/scratch.md`.

1. The caller converts the wire string `widget/notes/scratch.md`.
   Observed: the conversion succeeds and yields an unbound file that maps to no workspace file and
   is owned by no node, rather than refusing the undeclared path.
   Realized by: the component's own parameter conversion, which yields an unbound file for a wire
   string no node declares.

### Scenario 4 — Converting nothing at all

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`.

1. The caller converts the empty wire string.
   Observed: an unbound file that names no workspace file and no owning node.
   Realized by: the component's own parameter conversion, which treats the empty wire string the
   same way it treats any string no node declares.

### Scenario 5 — Read-only and read-write bound files

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, the widget node
declares `widget/notes/draft.md` as a read-write file and `widget/contracts/widget.md` as a
read-only file, the workspace file for `widget/notes/draft.md` holds the file content
`widget notes v1`, and the workspace file for `widget/contracts/widget.md` holds the file content
`widget contract v1`.

1. The caller asks both bound files for their owning node and their kind.
   Observed: both are owned by the widget node, `widget/notes/draft.md` is a read-write file, and
   `widget/contracts/widget.md` is a read-only file.
   Realized by: the component's own bound-file records and the write-access check that reads the
   node's declared file kinds.

2. The caller asks the read-write bound file to read the file content of its workspace file.
   Observed: `widget notes v1`.
   Realized by: the component's own bound-file content read, which the session config supplies.

3. The caller asks the read-only bound file to write the file content `widget contract v2` to its
   workspace file.
   Observed: the request fails explicitly, naming the read-only file `widget/contracts/widget.md`,
   and the workspace file still holds `widget contract v1`.
   Realized by: the write-access check of the component's own alias management, which refuses a
   write through a read-only bound file.

### Scenario 6 — Masking a workspace path in text

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, and the widget
node declares the bound file whose workspace path is `widget/notes/draft.md`.

1. The caller sanitizes the text `the file parts/widget/notes/draft.md holds draft notes`.
   Observed: the same text with `parts/widget/notes/draft.md` replaced by the file alias
   `widget/notes/draft.md`, since parts/widget/notes/draft.md is a relative workspace path.
   Realized by: the component's own path masking, which replaces a relative workspace path with its
   file alias.

2. The caller sanitizes the text `the file /ws/alpha_scope_a/parts/widget/notes/draft.md holds
   draft notes`.
   Observed: the same text with the whole host path `/ws/alpha_scope_a/parts/widget/notes/draft.md`
   replaced by `widget/notes/draft.md`, so that neither the workspace root nor the directory
   prefixes before the relative workspace path remain visible.
   Realized by: the component's own path masking over the workspace root path that the component's
   workspace root resolution through `file_paths` establishes.

3. The caller sanitizes the text `the file /ws/alpha_scope_a/widget/notes/draft.md holds draft
   notes`.
   Observed: the same text with `/ws/alpha_scope_a/widget/notes/draft.md` replaced by
   `widget/notes/draft.md`.
   Realized by: the same path masking through `file_paths`.

4. The caller sanitizes the text `the file /ws/alpha_scope_b/widget/notes/draft.md is elsewhere`.
   Observed: the text is returned unchanged, because `/ws/alpha_scope_b/widget/notes/draft.md`
   contains no relative workspace path of this alias manager.
   Realized by: the same path masking, which leaves a workspace root other than its own untouched.

### Scenario 7 — The files the session restricts to reading

Given: the session config supplies the read-only file `widget/contracts/widget.md` and the
read-write file `widget/notes/draft.md`, and the widget node declares
`widget/contracts/widget.md` as a read-only file and `widget/notes/draft.md` as a read-write file.

1. The caller reads the read-only files of the session config.
   Observed: `widget/contracts/widget.md` is reported among the read-only files, and
   `widget/notes/draft.md` is not.
   Realized by: the component's own per-node parameter resolution from `uv_manifest_loader`
   manifests, which classifies the bound files the widget node declares.

### Scenario 8 — The files the session permits for reading and writing

Given: the session config supplies the read-only file `widget/contracts/widget.md` and the
read-write file `widget/notes/draft.md`, and the widget node declares
`widget/contracts/widget.md` as a read-only file and `widget/notes/draft.md` as a read-write file.

1. The caller reads the read-write files of the session config.
   Observed: `widget/notes/draft.md` is reported among the read-write files, and
   `widget/contracts/widget.md` is not.
   Realized by: the component's own per-node parameter resolution from `uv_manifest_loader`
   manifests.

### Scenario 9 — Reading and writing the same file kinds as the session config

Given: the active agent session config supplies the read-only file `widget/contracts/widget.md` and
the read-write file `widget/notes/draft.md`, and the widget node declares
`widget/contracts/widget.md` as a read-only file and `widget/notes/draft.md` as a read-write file.

1. The caller reads the read-write files and the read-only files of the session config.
   Observed: `widget/notes/draft.md` is reported among the read-write files,
   `widget/contracts/widget.md` is reported among the read-only files, and neither file is reported
   under the other kind.
   Realized by: the component's own per-node parameter resolution from `uv_manifest_loader`
   manifests, whose read-only aggregation excludes every file of the read-write aggregation.

### Scenario 10 — The session guide when step mode is active

Given: step mode is active, and the session guide holds the summary `clean the widget target`, the
step section numbered 1 titled `Inspect the widget contract` with its content, the step section
numbered 2 titled `Clean the widget source` with its content, and the verification failure
instruction whose text is `report the failing widget contract line`.

1. The caller reads the session guide of the session config.
   Observed: the guide carries the summary `clean the widget target`, step sections 1 and 2 in
   order, and the verification failure instruction `report the failing widget contract line`.
   Realized by: the component's own parsing of the node guide markdown, and guide markdown content
   that `uv_manifest_loader` resolves through the guide target manifest.

2. The caller asks for the step sections of that guide.
   Observed: two step sections, numbered 1 and 2, titled `Inspect the widget contract` and
   `Clean the widget source`, each carrying its content and no other section.
   Realized by: the component's own creation of sequential step sections for the level-two headings
   that are not the summary, lint checks, or verification failure sections.

### Scenario 11 — The session config while step mode is inactive

Given: step mode is inactive, and the session guide holds the summary `clean the widget target`.

1. The caller reads the session guide of the session config.
   Observed: no session guide is provided, so the summary `clean the widget target` and the step
   sections are not reported, and the read fails explicitly rather than reporting a guide without
   step mode.
   Realized by: the component's own step mode eligibility, which withholds the session guide while
   step mode is inactive.

### Scenario 12 — A verification check that fails and one that passes

Given: the session config supplies the verification check whose criteria is
`widget/src/widget.py imports no undeclared module` and the verification check whose criteria is
`widget/notes/draft.md exists`, and the caller has run the two checks against the widget node.

1. The caller reads the verification checks and their outcomes.
   Observed: the two checks in the order supplied, with the first reporting failure and the second
   reporting success.
   Realized by: the component's own verification check resolution from the widget node's manifest
   through `uv_manifest_loader`.

### Scenario 13 — The verification success message

Given: the session config supplies the verification success message `widget verified clean`.

1. The caller reads the verification success message of the session config.
   Observed: `widget verified clean`.
   Realized by: the component's own session parameter resolution from the widget node's manifest
   through `uv_manifest_loader`.

### Scenario 14 — Templates and template parameters

Given: the widget node's manifest declares the template `widget/notes/draft.md` with the initial
file content `draft for [[unit]]` and the template parameter binding `unit` to `widget`.

1. The caller reads the templates and the template parameters of the session config.
   Observed: the template `widget/notes/draft.md` carrying the initial file content
   `draft for [[unit]]`, with the template parameter binding `unit` to `widget`.
   Realized by: the component's own per-node parameter resolution from `uv_manifest_loader`
   manifests.

### Scenario 15 — Blame targets and session messages

Given: the session config supplies the blame targets mapping the read-write file
`widget/notes/draft.md` to the read-only file `widget/contracts/widget.md` and the session messages
mapping `widget/notes/draft.md` to the message `the widget contract requires two draft sections`.

1. The caller reads the blame targets of `widget/notes/draft.md` and the message recorded for it.
   Observed: the single blame target `widget/contracts/widget.md`, and the message
   `the widget contract requires two draft sections`.
   Realized by: the component's own session parameter aggregation from the widget node's manifest
   through `uv_manifest_loader`.

2. The caller reads the blame targets of the read-write file `widget/src/widget.py`, which the
   session config supplies no blame target for.
   Observed: no blame target is reported, and the lookup fails explicitly rather than naming a
   substitute read-only file.
   Realized by: the component's own session parameter resolution, whose lookup of an unrecorded
   blame target fails rather than substituting a read-only file.

### Scenario 16 — The role config maintaining the active role and cleaned nodes

Given: the role config of the agent session holds no active role, holds no node being cleaned, and
names the execution version 1.

1. The caller sets the active role to `alpha`.
   Observed: the active role is `alpha`, no node is being cleaned, and the execution version remains
   1.
   Realized by: the component's own role config bookkeeping, whose execution version advances only
   when the cleaned nodes change.

2. The caller updates the sequence of nodes being cleaned to name the widget node only.
   Observed: the active role is `alpha`, the sequence names the widget node only, and the execution
   version is 2.
   Realized by: the component's own role config bookkeeping, which increments the execution version
   on a changed cleaned-node sequence.

3. The caller updates the sequence of nodes being cleaned to name the widget node, the gadget node,
   and the sprocket node in that order.
   Observed: the sequence names those three nodes in that order, and the execution version is 3.
   Realized by: the same role config bookkeeping, now over three nodes.

4. The caller updates the sequence of nodes being cleaned to name no node.
   Observed: the sequence names no node, and the execution version is 4 because the cleaned nodes
   changed.
   Realized by: the same role config bookkeeping, which increments the version even when the
   sequence becomes empty.

### Scenario 17 — Installing tools and reporting what is installed

Given: an agent session for role alpha in which no tool has been installed yet.

1. The agent asks which tools the session has installed.
   Observed: an empty mapping of tool names to tools.
   Realized by: installed tools through `tool_provider`, whose tool manager the component's own node
   configuration prepares the session for.

2. The agent installs the tool `inspect_widget`, described as reading one named widget, whose
   parameters are the required parameter `widget` and the unrequired parameter `unit` with the
   default value `widget`.
   Observed: no tool is called, and the installed tools now map the name `inspect_widget` to a tool
   of that name and description with the parameters `widget` and `unit`.
   Realized by: the tool manager of `tool_provider`, whose installed tools the component's own
   session preparation exposes.

3. The agent installs the tool `resize_widget`, described as changing the size of one widget, whose
   parameters are the required parameter `widget` and the required parameter `height`.
   Observed: the installed tools map the name `inspect_widget` and the name `resize_widget` to their
   respective tools.
   Realized by: the tool manager of `tool_provider`, whose installed tools the component's own
   session preparation exposes.

4. The agent asks which tools the session has installed.
   Observed: the mapping holds exactly two entries, keyed by the names `inspect_widget` and
   `resize_widget`.
   Realized by: installed tools through `tool_provider`, whose mapping the component's own session
   preparation leaves under the tool manager's control.

### Scenario 18 — Executing an installed tool by name

Given: the tool `resize_widget` is installed with the required parameter `widget` and the required
parameter `height`, and the session records the call to that tool.

1. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `height` to the wire integer `30`.
   Observed: the tool `resize_widget` is called once with action parameter bindings mapping its
   parameter `widget` to the actual value for `widget_a` and its parameter `height` to the actual
   value for `30`, and the tool response carries that tool's output and reports that execution did
   not fail.
   Realized by: the tool manager of `tool_provider`, whose wire parameter conversions the
   component's own alias manager participates in for file parameters.

2. The agent executes the tool `resize_widget` with the argument mappings binding `widget` to the
   wire string `widget_b` and `height` to the wire integer `42`.
   Observed: the tool `resize_widget` is called once more, with the same two actual parameters
   carrying the values for `widget_b` and `42`, and the tool response reports that execution did not
   fail.
   Realized by: the tool manager of `tool_provider`, whose wire parameter conversions the
   component's own alias manager participates in for file parameters.

### Scenario 19 — Naming a tool that is not installed

Given: the tool `inspect_widget` is installed and the tool `paint_widget` is not installed.

1. The agent executes the tool `paint_widget` with the wired parameter bindings binding `widget` to
   the wire string `widget_a`.
   Observed: the call fails with diagnostic feedback, the response reports that execution failed,
   no tool is called, and the session still holds `inspect_widget` among its installed tools.
   Realized by: the tool manager of `tool_provider`, whose installed tools the component's own
   session preparation does not alter on a failed call.

2. The agent executes the tool `paint_widget` with no wired parameter bindings.
   Observed: the call fails with diagnostic feedback, and no tool is called.
   Realized by: the tool manager of `tool_provider`, whose name lookup the component's own session
   preparation leaves to the tool manager.

### Scenario 20 — Supplying a name that the tool does not declare

Given: the tool `inspect_widget` is installed with the required parameter `widget` and the
unrequired parameter `unit`, and the session records the call to that tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `colour` to the wire string `red`.
   Observed: the call fails with diagnostic feedback that only declared parameters of the tool can
   be provided, the tool `inspect_widget` is not called, and the response reports that execution
   failed.
   Realized by: the tool manager of `tool_provider`, whose parameter specifications the component's
   own session preparation declares.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `unit` to the wire string `sprocket`.
   Observed: the call does not fail, and the tool `inspect_widget` is called with its parameter
   `widget` bound to the actual value for `widget_a` and its parameter `unit` bound to the actual
   value for `sprocket`.
   Realized by: the tool manager of `tool_provider`, whose parameter specifications the component's
   own session preparation declares.

### Scenario 21 — Omitting a required parameter and taking a default value

Given: the tool `inspect_widget` is installed with the required parameter `widget` and the
unrequired parameter `unit` with the default value `widget`, the required parameter `widget` carries
the missing note `supply widget, the name of the widget to inspect`, and the session records the
call to that tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `unit` to
   the wire string `gadget`.
   Observed: the call fails with diagnostic feedback incorporating the missing note `supply widget,
   the name of the widget to inspect`, the feedback states that required parameters of the tool must
   be supplied, and the tool `inspect_widget` is not called.
   Realized by: the tool manager of `tool_provider`, whose required parameter the component's own
   session preparation declares with its missing note.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the default value `widget` is bound for the omitted parameter `unit`, and the tool
   `inspect_widget` is called with its parameter `unit` bound to the actual value for `widget`.
   Realized by: the tool manager of `tool_provider`, whose default value the component's own session
   preparation declares for the unrequired parameter.

3. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `unit` to the wire string `sprocket`.
   Observed: the tool `inspect_widget` is called with `unit` bound to the actual value for
   `sprocket`, and the default value `widget` is not used.
   Realized by: the tool manager of `tool_provider`, whose default value the component's own session
   preparation declares for the unrequired parameter.

### Scenario 22 — A parameter type that converts without failing

Given: the tool `inspect_widget` is installed with the required parameter `widget`, whose parameter
type is the identity parameter type, and the session records the call to that tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the wire string `widget_a` converts to an identical actual value, the tool
   `inspect_widget` is called with its parameter `widget` bound to that actual value, and the
   response reports that execution did not fail.
   Realized by: the parameter conversion contract of `tool_provider`, which the component's own
   alias manager participates in for file parameters.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire boolean `true`.
   Observed: the conversion does not fail, and the tool `inspect_widget` is called with its
   parameter `widget` bound to the identical actual value for the wire boolean `true`.
   Realized by: the parameter conversion contract of `tool_provider`, which the component's own
   alias manager participates in for file parameters.

### Scenario 23 — A list parameter type and a mapping parameter type

Given: the tool `label_widgets` is installed, described as labelling widgets, whose required
parameter `widgets` has a list parameter type whose element parameter type is the identity parameter
type, and whose required parameter `labels` has a mapping parameter type whose key parameter type
and value parameter type are both the identity parameter type.

1. The agent executes the tool `label_widgets` with the wired parameter bindings binding `widgets`
   to the wire list of the wire strings `widget_a` and `widget_b`, and binding `labels` to the wire
   mapping from the wire string `owner` to the wire string `alpha`.
   Observed: the list converts element-wise into an actual list of the actual values for `widget_a`
   and `widget_b`, the mapping converts key-wise and value-wise into an actual mapping from the
   actual value for `owner` to the actual value for `alpha`, and the tool `label_widgets` is called
   with both actual values.
   Realized by: the parameter conversion contract of `tool_provider`, which the component's own
   alias manager participates in for file parameters.

2. The agent executes the tool `label_widgets` with the wired parameter bindings binding `widgets`
   to the wire list of the wire string `widget_a` and the wire list of the wire string `widget_b`,
   and binding `labels` to the wire mapping from the wire string `owner` to the wire string `alpha`.
   Observed: the call fails with diagnostic feedback from the element parameter type, and no tool is
   called.
   Realized by: the parameter conversion contract of `tool_provider`, whose element parameter type
   rejects the nested wire list.

3. The agent executes the tool `label_widgets` with the wired parameter bindings binding `widgets`
   to the wire list of the wire string `widget_a`, and binding `labels` to the wire mapping from the
   wire string `owner` to the wire list of the wire string `alpha`.
   Observed: the call fails with diagnostic feedback from the value parameter type, and no tool is
   called.
   Realized by: the parameter conversion contract of `tool_provider`, whose value parameter type
   rejects the nested wire list.

### Scenario 24 — A composite parameter type propagating constituent failures

Given: the tool `file_widgets` is installed, described as filing widgets, whose required parameter
`entries` has a mapping parameter type whose key parameter type is the identity parameter type and
whose value parameter type is a list parameter type with the identity parameter type as its element
parameter type.

1. The agent executes the tool `file_widgets` with the wired parameter bindings binding `entries` to
   the wire mapping from the wire string `cabinet_a` to the wire list of the wire strings `widget_a`
   and `widget_b`.
   Observed: the mapping converts into an actual mapping from the actual value for `cabinet_a` to an
   actual list of the actual values for `widget_a` and `widget_b`, and the tool `file_widgets` is
   called with it.
   Realized by: the parameter conversion contract of `tool_provider`, which the component's own
   alias manager participates in for file parameters.

2. The agent executes the tool `file_widgets` with the wired parameter bindings binding `entries` to
   the wire mapping from the wire string `cabinet_a` to the wire mapping from the wire string
   `widget_a` to the wire string `widget_b`.
   Observed: the call fails with diagnostic feedback propagated from the constituent parameter
   types, and no tool is called.
   Realized by: the parameter conversion contract of `tool_provider`, whose constituent parameter
   types propagate the failure.

### Scenario 25 — Responses that carry a suppression key and a follow-up tool call

Given: the tool `inspect_widget` and the tool `resize_widget` are installed, no suppression key is
declared for the tool `inspect_widget`, and the session records the calls to those tools.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the tool response carries tool output, reports that execution did not fail, and carries
   no suppression key.
   Realized by: the tool response of `tool_provider`, whose suppression key the component's own
   session preparation declares for the tool.

2. The agent executes the tool `inspect_widget` again with the wired parameter bindings binding
   `widget` to the wire string `widget_a`.
   Observed: the second tool response also carries no suppression key, so the prior conversation
   response is retained.
   Realized by: the tool response of `tool_provider`, whose absent suppression key the component's
   own session preparation declares for the tool.

3. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_b`.
   Observed: the tool response designates the follow-up tool call of the tool `resize_widget` with
   wired parameter bindings binding `widget` to the wire string `widget_b` and `height` to the wire
   integer `40`, with reasoning text articulating why the next tool is being called.
   Realized by: the follow-up tool call of `tool_provider`, whose tool the component's own session
   preparation installs.

### Scenario 26 — A tool with no parameters and a session whose tool list is absent

Given: the tool `list_widgets` is installed with no parameters, the tool `inspect_widget` is
installed in the session for role alpha, and no tool has ever been installed in the session for role
beta.

1. The agent executes the tool `list_widgets` with an empty mapping of wired parameter bindings.
   Observed: the tool `list_widgets` is called with empty action parameter bindings and the response
   reports that execution did not fail.
   Realized by: the tool manager of `tool_provider`, whose installed tools the component's own
   session preparation exposes.

2. The agent asks which tools the session for role beta has installed.
   Observed: an empty mapping of tool names to tools.
   Realized by: installed tools through `tool_provider`, whose per-session mapping the component's
   own node configuration does not share across sessions.

3. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` in the session for role beta.
   Observed: the call fails with diagnostic feedback that no installed tool matches the name, and
   the session for role alpha is unaffected.
   Realized by: the tool manager of `tool_provider`, whose per-session installed tools the
   component's own node configuration keeps apart.

### Scenario 27 — Bindings that a caller could not mean

Given: the tool `resize_widget` is installed with the required parameter `widget` and the required
parameter `height`, and the session records the call to that tool.

1. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` twice.
   Observed: the call fails with diagnostic feedback, no tool is called, and the response reports
   that execution failed.
   Realized by: the tool manager of `tool_provider`, whose wire parameter bindings the component's
   own session preparation leaves under the tool manager's control.

2. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire list of the wire strings `widget_a` and `widget_b` and `height` to the wire integer
   `30`.
   Observed: the call fails with diagnostic feedback from the parameter type of `widget`, and no
   tool is called.
   Realized by: the parameter conversion contract of `tool_provider`, whose parameter type rejects
   the wire list.

3. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `height` to the wire mapping from the wire string `rows` to the
   wire integer `30`.
   Observed: the call fails with diagnostic feedback from the parameter type of `height`, and no
   tool is called.
   Realized by: the parameter conversion contract of `tool_provider`, whose parameter type rejects
   the wire mapping.

## Implementation-only

### Scenario 28 — Resolving a node's parameters from its manifest

Given: the widget node's manifest declares the source file `widget/src/widget.py`, the template
`widget/notes/draft.md` with the initial file content `draft for [[unit]]`, the direct dependency on
the gadget node, the silent dependency on the sprocket node, the transitive star dependency on the
gamma-role target for gadget, and the feedback dependency on the beta-role target for sprocket; the
widget node's manifest also declares the read-write file `widget/contracts/widget.md`.

1. The caller reads the read-write files, the templates, the template parameters and the read-only
   files of the session config.
   Observed: `widget/src/widget.py` and `widget/notes/draft.md` are the read-write files,
   `widget/notes/draft.md` carries the template `draft for [[unit]]` with the template parameter
   binding `unit` to `widget`, and the read-only files hold `widget/contracts/gadget.md` from the
   direct gadget dependency and the gamma-role contract of gadget from the star dependency while
   omitting the sprocket node's files and `widget/contracts/widget.md`.
   Realized by: the component's own parameter resolution from the node manifest that
   `uv_manifest_loader` supplies, including the transitive star dependency manifests, and the
   exclusion of declared silent dependencies and of every file of the read-write set.

### Scenario 29 — Guide markdown resolved across workspace trees and parsed into sections

Given: the widget node's manifest declares the guide target whose source file is
`guides/widget_guide.md`, the guide file is absent beside the widget source file and present at the
candidate relative path of the guide target label, and the guide markdown holds the text preceding
its first heading, a heading `Summary`, a heading `Lint checks`, a heading `Verification failure
instructions`, and the level-two headings `Inspect the widget contract` and `Clean the widget
source`.

1. The caller reads the session guide of the session config.
   Observed: the guide carries the text preceding the first heading as its summary, the step
   sections numbered 1 and 2 titled `Inspect the widget contract` and `Clean the widget source`, and
   the verification failure instruction of the `Verification failure instructions` section, and
   reports no section titled `Lint checks`.
   Realized by: guide target manifest retrieval through `uv_manifest_loader`, the component's own
   resolution of the guide file across workspace trees using candidate relative paths, and the
   component's own parsing of the guide markdown.

2. The guide file is removed, and the caller reads the session guide again.
   Observed: an unbound guide file is provided whose relative filename derives from the guide target
   label, rather than the parsed sections of the removed file.
   Realized by: the component's own unbound guide file, whose relative filename derives from the
   guide target label the manifest retrieval through `uv_manifest_loader` supplies.

### Scenario 30 — Aggregating session parameters across several active nodes

Given: the session holds the active widget node and the active gadget node; the widget node declares
the read-write file `widget/notes/draft.md` and the template mapping it to `draft for [[unit]]` with
the template parameter binding `unit` to `widget`; the gadget node declares the read-only file
`widget/notes/draft.md` and the read-write file `gadget/notes/gadget.md`, whose template maps it to
`gadget draft`; and the single-node step mode permission is absent.

1. The caller reads the session read-write files, the session read-only files, the session templates
and the session template parameters. Observed: the read-write files are `widget/notes/draft.md` and
`gadget/notes/gadget.md`, the session templates map both files to their initial contents, the
template parameters bind `unit` to `widget` only, and `widget/notes/draft.md` is absent from the
read-only files. Realized by: the component's own dynamic aggregation of the session parameters
across the per node info of the active nodes, which exclude every read-write file from the read-only
aggregation.

2. The caller asks whether the session is eligible for step mode.
   Observed: not eligible, because the session holds more than one active node rather than a single
   node whose target allows step mode.
   Realized by: the component's own step mode eligibility and the per-node parameters that
   `uv_manifest_loader` supplies.

### Scenario 31 — File aliases for the accessible workspace files

Given: the active nodes are the widget node, which declares `widget/notes/draft.md` and
`widget/src/widget.py`, and the gadget node, which declares `gadget/notes/draft.md`; the workspace
root is `/ws/alpha_scope_a`; and the workspace file `other/notes/scratch.md` belongs to no active
node.

1. The caller reads the file alias generated for every accessible workspace file.
   Observed: one alias each for `widget/notes/draft.md`, `widget/src/widget.py` and
   `gadget/notes/draft.md`, and no alias for `other/notes/scratch.md`.
   Realized by: the component's own generation of a file alias with a relative path for every
   accessible workspace file associated with the active nodes in the role config.

2. The caller converts the wire string `widget/notes/draft.md`.
   Observed: the bound read-write file of the widget node, matching the alias of step 1 rather than
   a workspace path prefix of the host filesystem.
   Realized by: the component's own matching of relative paths to file aliases, which
   `agent_file_alias` converts.

### Scenario 32 — Step mode activation across its three conditions

Given: the session holds the single active widget node, whose target allows step mode; the agent
configuration supplies the step mode policy; and the session feedback is the message
`the widget contract requires two draft sections` for `widget/notes/draft.md`.

1. The caller reads whether step mode is active.
   Observed: inactive, because session feedback is present, although the agent configuration permits
   step mode and the session is eligible for it.
   Realized by: the component's own step mode activation over the agent configuration step mode
   policy supplied through `agent_config`, the session eligibility, and the feedback messages
   `dag_storage` holds.

2. The session feedback is cleared, and the caller reads whether step mode is active.
   Observed: active, and the session guide file and the task guide of the widget node are provided.
   Realized by: the component's own step mode activation, which supplies the session guide file and
   the single active node's task guide, and the feedback messages `dag_storage` holds.
