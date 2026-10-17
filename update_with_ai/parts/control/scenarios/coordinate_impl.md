<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:17:16Z
CHANGE: Author control coordinate_impl concrete scenarios
CODE_HASH: 53ab7f84c843
-->

# Concrete scenarios for `coordinate_impl` (implementation)

Scenarios 1 through 10 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 11 through
16 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Dispatching work and populating the open targets

Given: the session has no active target, and the caller holds the execution subgraph rooted at the
alpha-role node for unit widget, holding that node and the beta-role node for unit widget; the
alpha-role node for unit widget is dirty with the file alias `parts/widget/widget_spec.md`, and the
beta-role node for unit widget is dirty with the file alias `parts/widget/widget_contract.md`.

1. The agent asks the session coordinator for work in that execution subgraph.
   Observed: a control dispatch outcome reporting success and carrying the work schedule for the
   alpha-role node for unit widget and the beta-role node for unit widget, and two open targets,
   the alpha-role target for unit widget with the file alias `parts/widget/widget_spec.md` and the
   beta-role target for unit widget with the file alias `parts/widget/widget_contract.md`.
   Realized by: the get work dispatch, which invokes `work_scheduler` with the provided
   execution subgraph; the component's own registration of each newly scheduled node as an open
   target in its registered session nodes, whose last scheduled batch is written by that same
   dispatch; and the file alias mapping through `agent_file_alias`.

### Scenario 2 — Resolving a default target when the parameter is omitted

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, the open beta-role target for unit widget with the file alias
`parts/widget/widget_contract.md`, and the clean gamma-role target for unit gadget with the file
alias `parts/gadget/gadget_spec.md`; the session coordinator most recently accessed the alpha-role
target for unit widget.

1. The agent asks the session coordinator to verify without supplying a target.
   Observed: the verification is performed for the alpha-role target for unit widget, reported
   through the file alias `parts/widget/widget_spec.md`, rather than for the beta-role target for
   unit widget or the clean gamma-role target for unit gadget.
   Realized by: the component's own default target resolution over the registered session nodes,
   which reads the target states and the access order that the get work, submit and blame dispatches
   write, maps the surviving file alias through `agent_file_alias` to its owning node, and ignores
   the clean gamma-role target; the evaluation itself is then delegated to `verification`.

### Scenario 3 — The open targets left once only one remains

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md` and the clean beta-role target for unit widget with the file alias
`parts/widget/widget_contract.md`.

1. The agent asks the session coordinator to verify without supplying a target.
   Observed: the verification is performed for the alpha-role target for unit widget, reported
   through the file alias `parts/widget/widget_spec.md`, because it is the sole open target.
   Realized by: the component's own default target resolution over the registered session nodes,
   which selects the sole open target without consulting the access order, and the delegation of
   that target to `verification`.

### Scenario 4 — Verifying one named target file

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, whose verification check fails with the diagnostic
`the widget field type is not accepted`, and the open beta-role target for unit gadget with the file
alias `parts/gadget/gadget_spec.md`, whose verification check passes.

1. The agent asks the session coordinator to verify the target file
   `parts/widget/widget_spec.md`.
   Observed: a control dispatch outcome reporting the failing diagnostic
   `the widget field type is not accepted` for the alpha-role target for unit widget, and the
   beta-role target for unit gadget is not verified.
   Realized by: the check files dispatch, which resolves the supplied path through the component's
   own registered session nodes and `agent_file_alias` and delegates the evaluation of that single
   target file to `verification`, whose sanitized diagnostics and reuse indication the
   component passes through.

### Scenario 5 — Verifying every open target when no target is supplied

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, whose verification check fails with the diagnostic
`the widget field type is not accepted`, and the open beta-role target for unit gadget with the file
alias `parts/gadget/gadget_spec.md`, whose verification check passes.

1. The agent asks the session coordinator to verify with no target supplied.
   Observed: a control dispatch outcome reporting the failing diagnostic
   `the widget field type is not accepted` for the alpha-role target for unit widget and reporting
   that the beta-role target for unit gadget verified successfully, and reporting for each target
   whether its result was reused from cache.
   Realized by: the check files dispatch, which passes every open session target to
   `verification` when no target path is supplied, and the component's own assembly of the
   per-target outcomes and cache reuse indications into one control dispatch outcome.

### Scenario 6 — Verifying with no open target at all

Given: the session tracks no open target, and its last two targets are the clean alpha-role target
for unit widget and the attributed beta-role target for unit gadget.

1. The agent asks the session coordinator to verify with no target supplied.
   Observed: a control dispatch outcome reporting that no target was verified, and a message
   reporting that no open target is available, so neither the clean alpha-role target for unit
   widget nor the attributed beta-role target for unit gadget is verified.
   Realized by: the component's own default target resolution over the registered session nodes,
   which finds no open target once the clean and attributed targets are set aside by the submit and
   blame dispatches, and the component's own message construction.

### Scenario 7 — Submitting an open target

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md` and the open beta-role target for unit gadget with the file alias
`parts/gadget/gadget_spec.md`.

1. The agent submits the target `parts/widget/widget_spec.md` through the session coordinator with
   the change summary `renamed the widget field`.
   Observed: a control dispatch outcome reporting an accepted submission, the alpha-role target for
   unit widget now clean and no longer among the remaining open targets, and the beta-role target
   for unit gadget still open.
   Realized by: the submit dispatch, which resolves the target through the component's own
   registered session nodes and `agent_file_alias` and delegates validation and resolution to
   `submit`; the component's own update of that target's state to clean; and the component's
   own enumeration of the remaining open targets, which still holds the beta-role target.

### Scenario 8 — Submitting a target that fails its preconditions

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, whose verification check fails with the diagnostic
`the widget field type is not accepted`.

1. The agent submits the target `parts/widget/widget_spec.md` through the session coordinator with
   the change summary `renamed the widget field`.
   Observed: a control dispatch outcome reporting that the submission was not accepted and carrying
   an explicit message naming the failing verification, and the alpha-role target for unit widget
   still among the remaining open targets.
   Realized by: `submit`, whose precondition validation refuses the submission, and the
   component's own preservation of the target's open state and of the refusal message in the
   outcome.

### Scenario 9 — Attributing a defect to a culprit

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, which declares the eligible culprit beta-role target for unit gadget
with the file alias `parts/gadget/gadget_spec.md`, and which has the in-batch dependent alpha-role
target for unit sprocket with the file alias `parts/sprocket/sprocket_spec.md`; the critique
`the gadget contract declares the widget field twice` carries no newline character.

1. The agent attributes the defect through the session coordinator by blaming
   `parts/gadget/gadget_spec.md` with that critique.
   Observed: a control dispatch outcome reporting an accepted attribution that names the beta-role
   target for unit gadget, the alpha-role target for unit widget no longer among the remaining open
   targets, and the in-batch dependent alpha-role target for unit sprocket no longer among the
   remaining open targets.
   Realized by: the blame dispatch, which resolves the culprit path and the source target through
   `agent_file_alias` and delegates the attribution to `attribution`; the component's own
   update of the source target's state to attributed; and the component's own marking of the
   in-batch dependents as failed, both written into the registered session nodes that the dispatch
   also reads for the remaining open targets.

### Scenario 10 — Recording task failure for an open target

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, and the failure explanation is `the widget contract does not declare
the gadget field`.

1. The agent records the task failure through the session coordinator for
   `parts/widget/widget_spec.md` with that explanation.
   Observed: a control dispatch outcome reporting that the failure was recorded and carrying the
   explanation `the widget contract does not declare the gadget field`, and the alpha-role target
   for unit widget no longer among the remaining open targets.
   Realized by: the fail dispatch, which delegates the failure logging to `attribution`; the
   component's own update of that target's state to failed; and the component's own enumeration of
   the remaining open targets.

## Implementation-only

### Scenario 11 — Recording the activity sequence of the session

Given: the session has no active target, the role configuration of the session records the
execution version 1 and no node being cleaned, and the caller holds the execution subgraph rooted
at the alpha-role node for unit widget, holding that node and the beta-role node for unit gadget,
both dirty.

1. The agent asks the session coordinator for work in that execution subgraph.
   Observed: the role configuration records the alpha-role node for unit widget and the beta-role
   node for unit gadget as the sequence of nodes being cleaned, and its execution version is 2.
   Realized by: the component's own synchronization of the scheduled nodes onto the role config
   maintained through `agent_node_config`, whose update of the cleaned node sequence is what
   increments the execution version.

### Scenario 12 — Dispatching work across a directory scope

Given: the session has no active target, and the directory scope `/ws/alpha_scope_a/parts` holds the
alpha-role node for unit widget, at `parts/widget/widget_spec.md` and dirty with no dependency.

1. The agent asks the session coordinator for work in that directory scope with no execution
   subgraph.
   Observed: a control dispatch outcome reporting success and carrying the work schedule for the
   alpha-role node for unit widget, and one open target, the alpha-role target for unit widget with
   the file alias `parts/widget/widget_spec.md`.
   Realized by: the get work dispatch, which invokes `work_scheduler` with the directory
   scope when no execution subgraph is supplied, and the component's own registration of the
   scheduled node as an open target.

### Scenario 13 — What the session still tracks after a second work dispatch

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md` from an earlier work dispatch, and the caller now holds the execution
subgraph rooted at the beta-role node for unit gadget, holding that node and the beta-role node for
unit sprocket, both dirty.

1. The agent asks the session coordinator for work in that execution subgraph.
   Observed: a control dispatch outcome carrying the work schedule for the beta-role node for unit
   gadget and the beta-role node for unit sprocket, with the beta-role targets for unit gadget and
   unit sprocket among the remaining open targets alongside the alpha-role target for unit widget.
   Realized by: the component's own registration of each newly scheduled node among the registered
   session nodes whose per-target state and file alias were written by the earlier dispatch, so the
   earlier alpha-role target keeps its recorded state instead of being dropped.

### Scenario 14 — How a failure reaches the dependents of the same batch

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, the open beta-role target for unit gadget with the file alias
`parts/gadget/gadget_spec.md` and the open alpha-role target for unit sprocket with the file alias
`parts/sprocket/sprocket_spec.md`, all three scheduled in one batch; the alpha-role target for unit
widget has the in-batch dependent beta-role target for unit gadget, and the failure explanation is
`the widget contract does not declare the gadget field`.

1. The agent records the task failure through the session coordinator for
   `parts/widget/widget_spec.md` with that explanation.
   Observed: a control dispatch outcome reporting that the failure was recorded and carrying the
   explanation `the widget contract does not declare the gadget field`; the alpha-role target for
   unit widget and its in-batch dependent beta-role target for unit gadget are both no longer among
   the remaining open targets; and the alpha-role target for unit sprocket is still among the
   remaining open targets.
   Realized by: `attribution` for the failure logging on the source target, and the
   component's own propagation of the failed state to the in-batch dependents recorded in its
   registered session nodes, which leaves the node scheduled in a different batch untouched.

### Scenario 15 — Role-compatible file proxy matching

Given: the session tracks the open qa-role target for unit widget with the file alias
`parts/widget/qa_spec.md`; the session tracks no open lib-role or test-role target for unit widget.

1. The agent asks the session coordinator to look up the node for `parts/widget/lib/widget.py`.
   Observed: no node is resolved for `parts/widget/lib/widget.py`, so the file proxy for role lib
   does not mistakenly resolve to the open qa-role target for unit widget.
   Realized by: the component's own file proxy matching with role-compatibility checking, which
   rejects candidate nodes whose declared role differs from the file proxy role pattern.

### Scenario 16 — Attributing blame to an upstream dependency by file path

Given: the session tracks the open qa-role target for unit widget with the file alias
`parts/widget/qa_spec.md`; the upstream blame targets configured for the qa-role target include the
lib-role node for unit widget at `parts/widget/lib/widget.py`; the critique is `missing boundary check`.

1. The agent asks the session coordinator to dispatch blame specifying `parts/widget/lib/widget.py`
   as the blame target and `missing boundary check` as the critique.
   Observed: a control dispatch outcome reporting success, the lib-role node for unit widget is
   registered as attributed in the session coordinator, the qa-role target is marked attributed,
   and neither error nor self-blame is produced.
   Realized by: the blame dispatch, which resolves the blame target alias against the configured
   upstream blame targets via `attribution`, registers the blamed dependency node, and
   delegates defect attribution to `attribution`.
