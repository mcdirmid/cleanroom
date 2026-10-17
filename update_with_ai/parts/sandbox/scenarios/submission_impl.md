<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:30:00Z
CHANGE: Concrete scenarios for submission_impl
CODE_HASH: a0fe0dac0fbd
-->

# Concrete scenarios for `submission_impl` (implementation)

Scenarios 1 through 7 restate caller observations from the interface scenarios alongside their realizations.

## Reused from the interface

### Scenario 1 — Submitting the last open target with change documentation

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, verification passes for that target, and `widget/src/widget.py` was
modified during the session so that it imports no undeclared module.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module".
   Observed: the resolve target is marked clean in the current get work turn, the active node is
   concluded, and the response terminates the session because all active nodes are resolved.
   Realized by: submission dispatch through `coordinate`, which validates change documentation and marks the node clean, and the component's own termination check.

### Scenario 2 — Submitting one of several open targets

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the open targets are
`widget/src/widget.py` and `gadget/src/gadget.py`, verification passes for both, and
`widget/src/widget.py` was modified during the session.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module".
   Observed: the resolve target is marked clean in the current get work turn and concluded, and the
   response is non-terminating, still listing `gadget/src/gadget.py` as the remaining active node.
   Realized by: target resolution and clean dispatch through `coordinate`, followed by remaining target formatting via `template_format`.

### Scenario 3 — Enforcing change documentation on submission

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, and verification passes for that target.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and no change
   summary, after `widget/src/widget.py` was modified during the session.
   Observed: the request fails because change documentation is enforced when workspace files were
   modified, and `widget/src/widget.py` remains open.
   Realized by: change summary validation comparing modification state from `sandbox` against the presence of a change summary parameter.

2. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module", no workspace file having been
   modified during the session.
   Observed: the request fails because a change summary was supplied although no workspace file was
   modified, and `widget/src/widget.py` remains open.
   Realized by: change summary rejection when `sandbox` reports no modifications.

### Scenario 4 — Submitting while verification does not pass

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, which imports the module `sprocket_helpers` and was modified during the
session, and the configured verification check whose criteria is "widget/src/widget.py imports no
undeclared module" does not pass.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module".
   Observed: the request fails, the resolve target is not marked clean in the current get work turn,
   and `widget/src/widget.py` remains open.
   Realized by: verification outcome checking from `run_control`, gating submission on passing status.

### Scenario 5 — Failing the run

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, and its blame target is the read-only file `widget/contracts/widget.md`.

1. The agent executes the fail tool with the resolve target `widget/src/widget.py` and the
   explanation "the widget contract cannot be satisfied without the missing sprocket interface".
   Observed: the active node is marked as failed, the response carries the explanation "the widget
   contract cannot be satisfied without the missing sprocket interface", and the run terminates in
   failure.
   Realized by: failure dispatch through `coordinate`, which marks the node as failed and yields a failure response.

### Scenario 6 — Blaming an upstream dependency node

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py` with the read-only file `widget/contracts/widget.md` as its configured
blame target, the node owning `widget/contracts/widget.md` is the beta-role node for widget, and
`widget/src/widget.py` was modified during the session.

1. The agent executes the blame tool with the resolve target `widget/src/widget.py`, the blame target
   `widget/contracts/widget.md`, and the explanation "the widget contract omits the required field
   declaration".
   Observed: the task failure is attributed to the upstream dependency node owning
   `widget/contracts/widget.md`, the active node is resolved, and the response terminates the session
   because no other active node remains.
   Realized by: single-paragraph explanation validation, defect feedback recording via `dag_storage`, and node resolution through `coordinate`.

### Scenario 7 — Blaming an upstream dependency specifying target as blame target

Given: the agent has entered the session for role qa in `/ws/qa_scope_a`, the only open target
is `parts/widget/qa_spec.md`, and its configured blame target is `parts/widget/lib/widget.py`.

1. The agent executes the blame tool with the resolve target `parts/widget/lib/widget.py` and the
   explanation "missing boundary check on widget capacity".
   Observed: the resolve target is treated as the blame target matching the configured blame target,
   blame is dispatched to `coordinate`, and the session terminates because all active nodes
   are resolved.
   Realized by: the component's own blame target matching and resolution, which treats the resolve
   target parameter as the blame target when matching a configured blame target in a single-target
   context.

### Scenario 8 — Submitting with unresolved session feedback and no modifications

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target is `widget/src/widget.py`, session feedback is present for the target, and no workspace files were modified during the session.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py`.
   Observed: the request fails with the message explaining that workspace files must be modified to address feedback or fail must be called, accompanied by a reminder to modify workspace files to address feedback or call fail, and without a change summary reminder.
   Realized by: relaying rejection feedback from `coordinate` and generating a feedback resolution reminder.
