<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T11:27:00Z
CHANGE: Remove max batch size parameter from get work tool
CODE_HASH: 9a598a65676a
-->

# Concrete scenarios for `run_control` (interface)

## Scenario 1 — Installing the session tools while step mode is inactive

Given: the agent enters a session for role alpha in the workspace directory `/ws/alpha_scope_a`, the
session holds the two open targets `widget/src/widget.py` and `gadget/src/gadget.py`, guide step
mode is inactive, and no session tool has been installed yet.

1. The agent enters the agent session.
   Observed: the installed tools include the submit tool, the fail tool, the check files tool named
   `check_files`, and the get work tool, and the blame tool and advance tool are not among the
   installed tools.

2. The agent reads the tool named `check_files` from the installed tools.
   Observed: the check files tool accepts no parameters.

## Scenario 2 — Installing the session tools while guide step mode is active

Given: the agent enters a session for role alpha in the workspace directory `/ws/alpha_scope_a`, the
session holds the open target `widget/src/widget.py`, guide step mode is active with the session
guide whose summary is "clean the widget target", whose step section 1 is titled "Inspect the widget
contract" and whose step section 2 is titled "Clean the widget source", and no session tool has been
installed yet.

1. The agent enters the agent session.
   Observed: the installed tools include the submit tool, the fail tool, the check files tool named
   `check_files`, the get work tool, and the advance tool, and the blame tool is not among the installed tools.

2. The agent reads the tool named `advance` from the installed tools.
   Observed: the advance tool accepts no parameters.

## Scenario 3 — The exposed verification checks and a reused cached outcome

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the run controller is
configured with the verification check whose criteria is "widget/src/widget.py imports no undeclared
module" and the verification check whose criteria is "gadget/src/gadget.py ends with a newline", the
open targets are `widget/src/widget.py` and `gadget/src/gadget.py`, `widget/src/widget.py` imports
the module `sprocket_helpers`, and `gadget/src/gadget.py` ends with a newline.

1. The agent asks which verification checks validate the session criteria.
   Observed: exactly the two checks whose criteria are "widget/src/widget.py imports no undeclared
   module" and "gadget/src/gadget.py ends with a newline".

2. The agent executes the check files tool.
   Observed: the tool fails, presenting the aggregated verification outcome whose diagnostic feedback
   is "widget/src/widget.py imports the undeclared module sprocket_helpers", and the target
   `widget/src/widget.py` remains open.

3. The agent executes the check files tool again, no workspace file having been updated since that
   evaluation.
   Observed: the cached verification outcome is reused, so the same diagnostic feedback
   "widget/src/widget.py imports the undeclared module sprocket_helpers" is presented again without a
   fresh evaluation of the checks.

4. The agent updates `widget/src/widget.py` so that it imports no undeclared module, and executes the
   check files tool again.
   Observed: the cached verification outcome is not reused, a fresh evaluation reports that
   verification passed across the two open targets, and the tool does not fail.

## Scenario 4 — The check files tool when verification passes

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, which imports no undeclared module and was modified during the session,
and the configured verification check whose criteria is "widget/src/widget.py imports no undeclared
module" passes.

1. The agent executes the check files tool.
   Observed: the tool presents the aggregated verification outcome that verification passed, tracks
   the last tested file hashes of the target, and does not fail.

## Scenario 5 — The check files tool when verification fails

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, which imports the module `sprocket_helpers` and was modified during the
session, and the configured verification check whose criteria is "widget/src/widget.py imports no
undeclared module".

1. The agent executes the check files tool.
   Observed: the tool fails, presenting the aggregated verification outcome whose diagnostic feedback
   is "widget/src/widget.py imports the undeclared module sprocket_helpers", and the target
   `widget/src/widget.py` is not concluded.

## Scenario 6 — The check files tool evaluating every open target

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the open targets are
`widget/src/widget.py`, `gadget/src/gadget.py`, and `sprocket/src/sprocket.py`, `gadget/src/gadget.py`
does not end with a newline, and each of the three targets is configured with the verification check
whose criteria is that its own source file ends with a newline.

1. The agent executes the check files tool.
   Observed: the tool fails, and the aggregated verification outcome reports the passing targets
   `widget/src/widget.py` and `sprocket/src/sprocket.py` together with the failing target
   `gadget/src/gadget.py` and its diagnostic feedback "gadget/src/gadget.py does not end with a
   newline".

## Scenario 7 — The check files tool with nothing to evaluate

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, every active node has
been resolved so that no target is open, and no workspace file has been modified during the session.

1. The agent executes the check files tool.
   Observed: the aggregated verification outcome is empty, no verification check fails, and the tool
   does not fail.

## Scenario 8 — Advancing the guide when verification passes

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a` with guide step mode
active, the session guide holds the step section 1 titled "Inspect the widget contract" with the
content "Read widget/contracts/widget.md and confirm the declared field." and the step section 2
titled "Clean the widget source" with the content "Set widget_height to 42 in widget/src/widget.py.",
the only open target is `widget/src/widget.py`, the verification check whose criteria is
"widget/src/widget.py imports no undeclared module" passes, and no step section has been delivered.

1. The agent executes the advance tool.
   Observed: the step progression coordinates guide delivery so that the content "Read
   widget/contracts/widget.md and confirm the declared field." is delivered as the next milestone,
   and the target `widget/src/widget.py` remains open.

## Scenario 9 — Submitting the last open target with change documentation

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, verification passes for that target, and `widget/src/widget.py` was
modified during the session so that it imports no undeclared module.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module".
   Observed: the resolve target is marked clean in the current get work turn, the active node is
   concluded, and the response terminates the session because all active nodes are resolved.

## Scenario 10 — Submitting one of several open targets

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the open targets are
`widget/src/widget.py` and `gadget/src/gadget.py`, verification passes for both, and
`widget/src/widget.py` was modified during the session.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module".
   Observed: the resolve target is marked clean in the current get work turn and concluded, and the
   response is non-terminating, still listing `gadget/src/gadget.py` as the remaining active node.

## Scenario 11 — Enforcing change documentation on submission

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, and verification passes for that target.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and no change
   summary, after `widget/src/widget.py` was modified during the session.
   Observed: the request fails because change documentation is enforced when workspace files were
   modified, and `widget/src/widget.py` remains open.

2. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module", no workspace file having been
   modified during the session.
   Observed: the request fails because a change summary was supplied although no workspace file was
   modified, and `widget/src/widget.py` remains open.

## Scenario 12 — Submitting while verification does not pass

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, which imports the module `sprocket_helpers` and was modified during the
session, and the configured verification check whose criteria is "widget/src/widget.py imports no
undeclared module" does not pass.

1. The agent executes the submit tool with the resolve target `widget/src/widget.py` and the change
   summary "the widget source now imports no undeclared module".
   Observed: the request fails, the resolve target is not marked clean in the current get work turn,
   and `widget/src/widget.py` remains open.

## Scenario 13 — Failing the run

Given: the agent has entered the session for role alpha in `/ws/alpha_scope_a`, the only open target
is `widget/src/widget.py`, and its blame target is the read-only file `widget/contracts/widget.md`.

1. The agent executes the fail tool with the resolve target `widget/src/widget.py` and the
   explanation "the widget contract cannot be satisfied without the missing sprocket interface".
   Observed: the active node is marked as failed, the response carries the explanation "the widget
   contract cannot be satisfied without the missing sprocket interface", and the run terminates in
   failure.

## Scenario 14 — Blaming an upstream dependency node

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

## Scenario 15 — Getting work and materializing startup templates

Given: the agent enters a session for role alpha in `/ws/alpha_scope_a`, no target is open, guide
step mode is inactive, the active dirty nodes are the alpha-role nodes for widget and gadget, whose
source artifacts `widget/src/widget.py` and `gadget/src/gadget.py` are missing on disk, and the
startup templates for those two read-write files hold "widget_height = 30" and "gadget_height = 30".

1. The agent executes the get work tool without arguments.
   Observed: the two dirty nodes are retrieved as active nodes, the source artifacts
   `widget/src/widget.py` and `gadget/src/gadget.py` now exist on disk holding "widget_height = 30"
   and "gadget_height = 30", and the session task prompt is delivered naming both targets.

## Scenario 16 — Getting work while guide step mode is active

Given: the agent enters a session for role alpha in `/ws/alpha_scope_a`, no target is open, guide
step mode is active with the session guide whose summary is "clean the widget target", the active
dirty node is the alpha-role node for widget, whose source artifact `widget/src/widget.py` is missing
on disk, and its startup template holds "widget_height = 30".

1. The agent executes the get work tool without arguments.
   Observed: the dirty node is retrieved as an active node, `widget/src/widget.py` now exists on disk
   holding "widget_height = 30", the session task prompt is delivered, and the response specifies a
   follow-up execution of the advance tool.

## Scenario 17 — Getting work when no dirty node is ready

Given: the agent enters a session for role alpha in `/ws/alpha_scope_a`, no target is open, no
workspace file has been modified during the session, and no dirty node is ready to be cleaned.

1. The agent executes the get work tool without arguments.
   Observed: no active node is retrieved, no startup template is materialized, and no session task
   prompt naming a target is delivered.

## Scenario 18 — Installing the blame tool when active nodes have blame targets

Given: the agent enters a session for role alpha in `/ws/alpha_scope_a`, no target is open, guide step mode is inactive, the active dirty node has configured blame targets in node config, and no session tool other than submit, fail, check_files, and get_work has been installed.

1. The agent executes the get work tool without arguments.
   Observed: the dirty node is retrieved as an active node and the blame tool is installed in the session tools.

## Scenario 19 — Guide delivery fallback from read-only documentation

Given: the agent enters a session for role alpha in `/ws/alpha_scope_a`, the active dirty node has no `guide_file` configured in node config, but `read_only_files` includes `/repo/guides/alpha_guide.md`.

1. The agent executes the get work tool without arguments.
   Observed: the dirty node is retrieved as an active node, and the delivered task prompt references `alpha_guide.md` as the resolved guide.
