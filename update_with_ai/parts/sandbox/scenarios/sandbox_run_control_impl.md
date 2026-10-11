<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:20:02Z
CHANGE: Author sandbox sandbox_run_control_impl concrete scenarios
CODE_HASH: 9f365a5dc443
-->

# Concrete scenarios for `sandbox_run_control_impl` (implementation)

Scenarios 1 through 17 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 18 through
22 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Installing the session tools while step mode is inactive

Given: the agent enters a session for role alpha in the workspace directory `/ws/alpha_scope_a`, the
session holds the two open targets `widget/src/widget.py` and `gadget/src/gadget.py`, guide step
mode is inactive, and no session tool has been installed yet.

1. The agent enters the agent session.
   Observed: the installed tools include the submit tool, the fail tool, the check files tool named
   `check_files`, the get work tool, and the blame tool, and the advance tool is not among the
   installed tools.
   Realized by: tool installation and parameter conversion through
   `tool_provider`, the verification checks and per-node blame targets obtained from
   `agent_node_config`, and the component's own session-entry initialization, which installs the
   submit, fail, check files, get work, and blame tools unconditionally and leaves the advance tool
   uninstalled while guide step mode is inactive; active target tracking and the current get work
   turn are delegated to the session coordinator of `control_coordinate`.

2. The agent reads the tool named `check_files` from the installed tools.
   Observed: the check files tool accepts no parameters.
   Realized by: the argument-free parameter inventory of the installed
   check files tool through `tool_provider`.

### Scenario 2 — Installing the session tools while guide step mode is active

Given: the agent enters a session for role alpha in the workspace directory `/ws/alpha_scope_a`, the
session holds the open target `widget/src/widget.py`, guide step mode is active with the session
guide whose summary is "clean the widget target", whose step section 1 is titled "Inspect the widget
contract" and whose step section 2 is titled "Clean the widget source", and no session tool has been
installed yet.

1. The agent enters the agent session.
   Observed: the installed tools include the submit tool, the fail tool, the check files tool named
   `check_files`, the get work tool, the blame tool, and the advance tool.
   Realized by: the same unconditional installation through
   `tool_provider` and the same configuration access through `agent_node_config`, plus the
   component's own guide-step-mode branch, which adds the advance tool when guide step mode is
   active.

2. The agent reads the tool named `advance` from the installed tools.
   Observed: the advance tool accepts no parameters.
   Realized by: the argument-free parameter inventory of the installed
   advance tool through `tool_provider`.

### Scenario 3 — The exposed verification checks and a reused cached outcome

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the run controller
is configured with the verification check whose criteria is "widget/src/widget.py imports no
undeclared module" and the verification check whose criteria is "gadget/src/gadget.py ends with a
newline", the open targets are `widget/src/widget.py` and `gadget/src/gadget.py`,
`widget/src/widget.py` imports the module `sprocket_helpers`, and `gadget/src/gadget.py` ends with a
newline.

1. The agent asks which verification checks validate the session criteria.
   Observed: exactly the two checks whose criteria are "widget/src/widget.py imports no undeclared
   module" and "gadget/src/gadget.py ends with a newline".
   Realized by: the verification checks supplied by `agent_node_config`,
   exposed through the component's own session configuration access.

2. The agent executes the check files tool.
   Observed: the tool fails, presenting the aggregated verification outcome whose diagnostic
   feedback is "widget/src/widget.py imports the undeclared module sprocket_helpers", and the target
   `widget/src/widget.py` remains open.
   Realized by: verification evaluation delegated to the session
   coordinator of `control_coordinate`, which evaluates each configured check against the latest
   content of the target read-write file read through `sandbox_file_editor`, the component's own
   write of that outcome into its verification cache keyed by the file's edit manager hash, and the
   component's own failure response.

3. The agent executes the check files tool again, no workspace file having been updated since that
   evaluation.
   Observed: the cached verification outcome is reused, so the same diagnostic feedback
   "widget/src/widget.py imports the undeclared module sprocket_helpers" is presented again without
   a fresh evaluation of the checks.
   Realized by: the component's own cached verification outcome, reused
   because the `sandbox_file_editor` file hash of `widget/src/widget.py` is unchanged since the
   evaluation that wrote it.

4. The agent updates `widget/src/widget.py` so that it imports no undeclared module, and executes
   the check files tool again.
   Observed: the cached verification outcome is not reused, a fresh evaluation reports that
   verification passed across the two open targets, and the tool does not fail.
   Realized by: the changed file hash reported by `sandbox_file_editor`,
   which outdates the cached outcome, and a fresh evaluation through the session coordinator of
   `control_coordinate`.

### Scenario 4 — The check files tool when verification passes

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, which imports no undeclared module and was modified during the session,
and the configured verification check whose criteria is "widget/src/widget.py imports no undeclared
module" passes.

1. The agent executes the check files tool.
   Observed: the tool presents the aggregated verification outcome that verification passed, tracks
   the last tested file hashes of the target, and does not fail.
   Realized by: verification evaluation through the session coordinator of
   `control_coordinate` over the open targets it tracks, the last tested file hashes recorded by the
   component's own verification cache, and the configured verification success message from
   `agent_node_config`.

### Scenario 5 — The check files tool when verification fails

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, which imports the module `sprocket_helpers` and was modified during the
session, and the configured verification check whose criteria is "widget/src/widget.py imports no
undeclared module".

1. The agent executes the check files tool.
   Observed: the tool fails, presenting the aggregated verification outcome whose diagnostic
   feedback is "widget/src/widget.py imports the undeclared module sprocket_helpers", and the target
   `widget/src/widget.py` is not concluded.
   Realized by: evaluation through the session coordinator of
   `control_coordinate`, diagnostic feedback sanitized through the alias manager of
   `agent_file_alias`, and the component's own failure response.

### Scenario 6 — The check files tool evaluating every open target

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the open targets are
`widget/src/widget.py`, `gadget/src/gadget.py`, and `sprocket/src/sprocket.py`,
`gadget/src/gadget.py` does not end with a newline, and the three configured verification checks
have the criteria "widget/src/widget.py ends with a newline", "gadget/src/gadget.py ends with a
newline", and "sprocket/src/sprocket.py ends with a newline".

1. The agent executes the check files tool.
   Observed: the tool fails, and the aggregated verification outcome reports the passing targets
   `widget/src/widget.py` and `sprocket/src/sprocket.py` together with the failing target
   `gadget/src/gadget.py` and its diagnostic feedback "gadget/src/gadget.py does not end with a
   newline".
   Realized by: the component's own sweep of every open target tracked by
   the session coordinator of `control_coordinate`, each target's checks evaluated against its
   latest content read through `sandbox_file_editor`, and the component's own aggregation of the
   passing and failing outcomes.

### Scenario 7 — The check files tool with nothing to evaluate

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, every active node
has been resolved so that no target is open, and no workspace file has been modified during the
session.

1. The agent executes the check files tool.
   Observed: the aggregated verification outcome is empty, no verification check fails, and the tool
   does not fail.
   Realized by: the session coordinator of `control_coordinate`, which
   reports no open target, the modification state from `sandbox`, and the component's own empty
   aggregated outcome.

### Scenario 8 — Advancing the guide when verification passes

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a` with guide step mode
active, the session guide holds the step section 1 titled "Inspect the widget contract" with the
content "Read widget/contracts/widget.md and confirm the declared field." and the step section 2
titled "Clean the widget source" with the content "Set widget_height to 42 in
widget/src/widget.py.", the only open target is `widget/src/widget.py`, the verification check whose
criteria is "widget/src/widget.py imports no undeclared module" passes, and no step section has been
delivered.

1. The agent executes the advance tool.
   Observed: the step progression coordinates guide delivery so that the content "Read
   widget/contracts/widget.md and confirm the declared field." is delivered as the next milestone,
   and the target `widget/src/widget.py` remains open.
   Realized by: step progression delegated to `sandbox_guide_delivery`,
   driven by the passing verification outcome evaluated through the session coordinator of
   `control_coordinate`.

### Scenario 9 — Submitting the last open target with change documentation

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, verification passes for that target, and `widget/src/widget.py` was
modified during the session so that it imports no undeclared module.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module".
   Observed: the resolve target is marked clean in the current get work turn, the active node is
   concluded, and the response terminates the session because all active nodes are resolved.
   Realized by: submission gating delegated to the session coordinator of
   `control_coordinate`, which validates the preconditions and marks the resolve target clean in the
   current get work turn, the storage writes through `dag_storage`, the modification state from
   `sandbox`, and the component's own change summary validation and terminating response assembly
   formatted through `template_format`.

### Scenario 10 — Submitting one of several open targets

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the open targets are
`widget/src/widget.py` and `gadget/src/gadget.py`, verification passes for both, and
`widget/src/widget.py` was modified during the session.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module".
   Observed: the resolve target is marked clean in the current get work turn and concluded, and the
   response is non-terminating, still listing `gadget/src/gadget.py` as the remaining active node.
   Realized by: the session coordinator of `control_coordinate`, which
   reports the nodes left open by the submission, and the component's own non-terminating response
   assembly whose remaining-node reminder is formatted through `template_format`.

### Scenario 11 — Enforcing change documentation on submission

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, and verification passes for that target.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and no change
   summary, after `widget/src/widget.py` was modified during the session.
   Observed: the request fails because change documentation is enforced when workspace files were
   modified, and `widget/src/widget.py` remains open.
   Realized by: the modification state from `sandbox`, the component's own
   change summary validation, which requires a change summary once workspace files were modified,
   and the resolve target tracking of `control_coordinate`, which leaves the target open.

2. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module", no workspace file having been
   modified during the session.
   Observed: the request fails because a change summary was supplied although no workspace file was
   modified, and `widget/src/widget.py` remains open.
   Realized by: the same modification state and the same validation, which
   refuses a change summary when no workspace file was modified, and the resolve target tracking of
   `control_coordinate`.

### Scenario 12 — Submitting while verification does not pass

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, which imports the module `sprocket_helpers` and was modified during the
session, and the configured verification check whose criteria is "widget/src/widget.py imports no
undeclared module" does not pass.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module".
   Observed: the request fails, the resolve target is not marked clean in the current get work turn,
   and `widget/src/widget.py` remains open.
   Realized by: submission gating delegated to the session coordinator of
   `control_coordinate`, which evaluates the target's verification checks before marking anything
   clean, and the component's own failure response.

### Scenario 13 — Failing the run

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, and its blame target is the read-only file `widget/contracts/widget.md`.

1. The agent executes the fail tool with the resolve target `widget/src/widget.py` and the
   explanation "the widget contract cannot be satisfied without the missing sprocket interface".
   Observed: the active node is marked as failed, the response carries the explanation "the widget
   contract cannot be satisfied without the missing sprocket interface", and the run terminates in
   failure.
   Realized by: the component's own failure termination, which marks the
   active node failed, resolves it through the session coordinator of `control_coordinate`, and
   carries the supplied explanation, with the failure recorded through `dag_storage`.

### Scenario 14 — Blaming an upstream dependency node

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py` with the read-only file `widget/contracts/widget.md` as its configured
blame target, the node owning `widget/contracts/widget.md` is the beta-role node for widget, and
`widget/src/widget.py` was modified during the session.

1. The agent executes the blame tool with the resolve target `widget/src/widget.py`, the blame
   target `widget/contracts/widget.md`, and the explanation "the widget contract omits the required
   field declaration".
   Observed: the task failure is attributed to the upstream dependency node owning
   `widget/contracts/widget.md`, the active node is resolved, and the response terminates the
   session because no other active node remains.
   Realized by: defect attribution delegated to the session coordinator of
   `control_coordinate`, which resolves the active node attributing blame from the specified blame
   target and records the feedback for the owning node through `dag_storage`; the blame target is
   resolved as a read-only file of the session through `agent_file_alias` and addressed through
   `dag_storage`.

### Scenario 15 — Getting work and materializing startup templates

Given: the agent enters a session for role alpha in `/ws/alpha_scope_a`, no target is open, guide
step mode is inactive, the active dirty nodes are the alpha-role nodes for widget and gadget, whose
source artifacts `widget/src/widget.py` and `gadget/src/gadget.py` are missing on disk, and the
startup templates for those two read-write files hold "widget_height = 30" and "gadget_height = 30".

1. The agent executes the get work tool with the max batch size 2.
   Observed: the two dirty nodes are retrieved as active nodes, the source artifacts
   `widget/src/widget.py` and `gadget/src/gadget.py` now exist on disk holding "widget_height = 30"
   and "gadget_height = 30", and the session task prompt is delivered naming both targets.
   Realized by: work discovery delegated to the session coordinator of
   `control_coordinate` across `dag_storage` and `dag_subgraph`, bounded by the batch size from
   `dag_config`, startup template materialization through `dag_storage`, the retrieved nodes
   recorded on the role config through `agent_node_config`, and the component's own task primer
   assembly formatted through `template_format`.

### Scenario 16 — Getting work while guide step mode is active

Given: the agent enters a session for role alpha in `/ws/alpha_scope_a`, no target is open, guide
step mode is active with the session guide whose summary is "clean the widget target", the active
dirty node is the alpha-role node for widget, whose source artifact `widget/src/widget.py` is
missing on disk, and its startup template holds "widget_height = 30".

1. The agent executes the get work tool with the max batch size 1.
   Observed: the dirty node is retrieved as an active node, `widget/src/widget.py` now exists on
   disk holding "widget_height = 30", the session task prompt is delivered, and the response
   specifies a follow-up execution of the advance tool.
   Realized by: the same discovery, materialization, and role config
   update path, plus the component's own guide-step-mode branch, which specifies a follow-up
   execution of the advance tool through `tool_provider`.

### Scenario 17 — Getting work when no dirty node is ready

Given: the agent enters a session for role alpha in `/ws/alpha_scope_a`, no target is open, no
workspace file has been modified during the session, and no dirty node is ready to be cleaned.

1. The agent executes the get work tool with the max batch size 2.
   Observed: no active node is retrieved, no startup template is materialized, and no session task
   prompt naming a target is delivered.
   Realized by: work discovery through the session coordinator of
   `control_coordinate` over `dag_storage` and `dag_subgraph`, which finds no ready dirty node, and
   the component's own idle response.

## Implementation-only

### Scenario 18 — Resolving the resolve target parameter against open active nodes

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, guide step mode is
inactive, verification passes for every node, no workspace file has been modified during the
session, and the open active nodes are the alpha-role node for `part_a/widget`, which declares the
source file alias `part_a/widget/src/widget.py`, the alpha-role node for `part_b/widget`, which
declares the source file alias `part_b/widget/src/widget.py`, and the beta-role node for
`part_a/gadget`, which declares no source file alias and whose short unit name `gadget` is unique
among the open active nodes.

1. The agent executes the submit tool with the resolve target `widget` and no change summary.
   Observed: the request fails and reminds the agent to specify an open target, because the short
   unit name `widget` is ambiguous among the open active nodes, and all three nodes remain open.
   Realized by: the component's own resolve target matching, which finds
   the short unit name `widget` ambiguous among the nodes tracked by the session coordinator of
   `control_coordinate` and therefore matches nothing, and its own refusal reminding the agent to
   specify an open target.

2. The agent executes the submit tool with the resolve target `part_b/widget` and no change summary.
   Observed: the package-qualified unit name resolves the alpha-role node for `part_b/widget`, that
   node is marked clean in the current get work turn and concluded, and the response is
   non-terminating, still listing the alpha-role node for `part_a/widget` and the beta-role node for
   `part_a/gadget`.
   Realized by: the component's own resolve target matching on the
   `pkg/unit_name` form, the resolve target tracking of `control_coordinate`, and the component's
   own non-terminating response whose remaining-node reminder is formatted through
   `template_format`.

3. The agent executes the submit tool with the resolve target `part_a/widget/src/widget.py` and no
   change summary.
   Observed: the declared source file alias resolves the alpha-role node for `part_a/widget`, that
   node is marked clean in the current get work turn and concluded, and the response is
   non-terminating, still listing the beta-role node for `part_a/gadget`.
   Realized by: the component's own resolve target matching on the
   declared source file alias of the alpha-role node for `part_a/widget`, paired with the node's
   declared alias read through `dag_storage`, and the same non-terminating response assembly.

4. The agent executes the submit tool with the resolve target `gadget` and no change summary.
   Observed: the unique short unit name resolves the beta-role node for `part_a/gadget`, that node
   is marked clean in the current get work turn and concluded, and the response terminates the
   session because all active nodes are resolved.
   Realized by: the same resolve target matching on a unique short unit
   name, and the component's own terminating response assembly.

5. The agent executes the submit tool with the resolve target `sprocket` and no change summary.
   Observed: the request fails and reminds the agent to specify an open target, because `sprocket`
   matches no open active node.
   Realized by: the component's own resolve target matching over the nodes
   tracked by `control_coordinate`, which finds no open active node named `sprocket`, and its own
   refusal.

### Scenario 19 — Defaulting an omitted resolve target to the node being processed

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, guide step mode is
inactive, the current get work turn is processing the alpha-role node for widget alone, whose
read-write file is `widget/src/widget.py` and whose short unit name `widget` is unique among the
open active nodes, verification passes for that node, and no workspace file has been modified during
the session.

1. The agent executes the submit tool with no resolve target and no change summary.
   Observed: the resolve target defaults to the single unsubmitted open active node, the alpha-role
   node for widget, which is marked clean in the current get work turn and concluded, and the
   response terminates the session because all active nodes are resolved.
   Realized by: the component's own resolve target defaulting, which takes
   the single remaining unsubmitted open active node from the session coordinator of
   `control_coordinate` when only one node is being processed.

### Scenario 20 — Defaulting an omitted resolve target from the last read or written file

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, guide step mode is
inactive, the current get work turn is processing the alpha-role node for widget and the alpha-role
node for gadget, whose read-write files are `widget/src/widget.py` and `gadget/src/gadget.py`,
verification passes for both nodes, no workspace file has been modified during the session, and the
last read or written path in the session is `gadget/src/gadget.py`.

1. The agent executes the submit tool with no resolve target and no change summary.
   Observed: the resolve target defaults to the last read or written path `gadget/src/gadget.py`,
   the alpha-role node for gadget is marked clean in the current get work turn and concluded, and
   the response is non-terminating, still listing `widget/src/widget.py`.
   Realized by: the component's own resolve target defaulting, which reads
   the last read or written record of the session's edit manager through `sandbox_file_editor` and
   matches that path to an open active node tracked by `control_coordinate`.

2. The caller informs the session that `widget/notes/draft.md` was read, which corresponds to no
   open active node.
   Observed: `widget/notes/draft.md` is the session's last read or written path.
   Realized by: the last-read-or-edited record of the edit manager through
   `sandbox_file_editor`, which the recording of a file read writes.

3. The agent executes the submit tool with no resolve target and no change summary.
   Observed: the request fails and reminds the agent to specify an open target, because the resolve
   target parameter cannot be defaulted, and `widget/src/widget.py` remains open.
   Realized by: the component's own resolve target defaulting, which
   matches the last read or written path against the nodes tracked by `control_coordinate` and finds
   none, and its own refusal.

### Scenario 21 — The blame tool's blame target defaulting and refusals

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, guide step mode is
inactive, the current get work turn is processing the alpha-role node for widget alone, whose
read-write file is `widget/src/widget.py`, the node's configured blame target is the read-only file
`widget/contracts/widget.md`, the session configuration also lists the read-only file
`widget/contracts/gadget.md`, which is not a blame target for the node, and the node owning
`widget/contracts/widget.md` is the beta-role node for widget.

1. The agent executes the blame tool with the blame target `widget/contracts/gadget.md` and the
   explanation "the gadget contract omits the required field declaration".
   Observed: the request fails, the error response lists the available blame target
   `widget/contracts/widget.md` and reminds the agent that only upstream files configured as blame
   targets can be blamed, and the alpha-role node for widget remains open.
   Realized by: the configured blame targets supplied by
   `agent_node_config` and resolved as read-only files through `agent_file_alias`, and the
   component's own refusal, which lists the available blame targets.

2. The agent executes the blame tool with the blame target `widget/contracts/widget.md` and the
   explanation "the widget contract omits the required field declaration." followed by a line break
   and "the gadget contract omits the batch size.".
   Observed: the request fails, the error response reminds the agent that a blame explanation must
   be a single paragraph without newlines, and the alpha-role node for widget remains open.
   Realized by: the component's own inspection of the supplied explanation
   for newline characters and its own refusal.

3. The agent executes the blame tool with no blame target and the explanation "the widget contract
   omits the required field declaration.".
   Observed: the blame target defaults to `widget/contracts/widget.md`, defect feedback is recorded
   for the beta-role node for widget, the blame target is marked attributed, the alpha-role node for
   widget is resolved, and the response terminates the session because no other active node remains.
   Realized by: the component's own blame target defaulting over the
   single configured blame target of the remaining active node, the resolve target defaulting rules,
   and defect attribution through the session coordinator of `control_coordinate`, which records the
   feedback through `dag_storage`.

### Scenario 22 — The advance tool's refusals and terminal follow-ups

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a` with guide step mode
active, the session guide holds the summary "clean the widget target", the step section 1 titled
"Inspect the widget contract" with the content "Read widget/contracts/widget.md and confirm the
declared field." and the step section 2 titled "Clean the widget source" with the content "Set
widget_height to 42 in widget/src/widget.py.", the current get work turn is processing the
alpha-role node for widget alone, whose read-write file is `widget/src/widget.py`, and verification
has not been evaluated for the current workspace files.

1. The agent executes the advance tool.
   Observed: the request fails, the response repeats the primer and summary content through guide
   delivery, reminds the agent to call the check files tool first, and specifies a follow-up
   execution of the check files tool whose reasoning text indicates that verification results must
   be inspected before advancing.
   Realized by: the component's own verification cache, which holds no
   outcome for the current `sandbox_file_editor` file hashes, the repeated primer and summary
   content assembled by `sandbox_guide_delivery`, and the component's own failure response with its
   follow-up tool call through `tool_provider`.

2. The agent executes the check files tool.
   Observed: verification passes for the alpha-role node for widget and the aggregated verification
   outcome is presented.
   Realized by: verification evaluation through the session coordinator of
   `control_coordinate` and the outcome recorded by the component's own verification cache against
   the current file hash.

3. The agent executes the advance tool.
   Observed: guide delivery delivers the content "Read widget/contracts/widget.md and confirm the
   declared field." as the next milestone, and guide steps remain because step section 2 has not
   been delivered.
   Realized by: step progression through `sandbox_guide_delivery`, driven
   by the passing outcome in the component's own verification cache.

4. The agent executes the advance tool.
   Observed: guide delivery delivers the content "Set widget_height to 42 in widget/src/widget.py."
   as the next milestone, and no guide steps remain.
   Realized by: the same step progression through
   `sandbox_guide_delivery`, which reports that no further step section remains.

5. The agent executes the advance tool, no workspace file having been modified during the session.
   Observed: the response specifies a follow-up execution of the submit tool without a change
   summary, with reasoning text indicating that all guide steps are complete.
   Realized by: the modification state from `sandbox`, which reports no
   workspace file modification, and the component's own follow-up tool call through `tool_provider`.

6. The agent modifies the content of `widget/src/widget.py` during the session.
   Observed: the session records a workspace file modification.
   Realized by: the write detection of `sandbox` over the write made
   through `sandbox_file_editor`.

7. The agent executes the advance tool.
   Observed: the request fails, reminding the agent to call the submit tool with a change summary
   describing the modifications to workspace files.
   Realized by: the modification state from `sandbox`, which now reports a
   workspace file modification, and the component's own failure response.
