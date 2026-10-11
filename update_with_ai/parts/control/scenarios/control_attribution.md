<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:12:02Z
CHANGE: Author control control_attribution concrete scenarios
CODE_HASH: be57302a3b64
-->

# Concrete scenarios for `control_attribution` (interface)

## Scenario 1 — Blaming one eligible upstream dependency among several

Given: the alpha-role target node for unit widget is configured to receive feedback and declares
the upstream dependencies of unit gadget in role beta and unit sprocket in role gamma, both
eligible for blame; the gadget beta-role node is clean and records no feedback message; the target
node has the in-batch dependent nodes of unit gadget in role alpha and unit sprocket in role
alpha, both of which are clean; the critique
`the widget contract contradicts the gadget contract` carries no newline character.

1. The agent blames the gadget beta-role node for the defect with that critique.
   Observed: an accepted attribution outcome listing the gadget beta-role node among its affected
   nodes; the gadget beta-role node records the feedback message
   `the widget contract contradicts the gadget contract` and is dirty; and the two in-batch
   dependent nodes of unit gadget in role alpha and unit sprocket in role alpha are failed.

## Scenario 2 — Blaming the target itself, a disconnected node, and a downstream dependent

Given: the alpha-role target node for unit widget is configured to receive feedback and declares
the upstream dependency of unit sprocket in role gamma, which is eligible for blame; the delta-role
node for unit sprocket is neither an upstream dependency nor a dependent of the target node; the
beta-role node for unit widget depends on the alpha-role target node; the critique
`the widget contract contradicts the gadget contract` carries no newline character.

1. The agent blames the alpha-role target node for unit widget itself with that critique.
   Observed: the attribution is refused with an explicit error, the alpha-role target node records
   no feedback message, and no node changes status.

2. The agent blames the delta-role node for unit sprocket with that critique.
   Observed: the attribution is refused with an explicit error, and the delta-role node for unit
   sprocket records no feedback message.

3. The agent blames the beta-role node for unit widget with that critique.
   Observed: the attribution is refused with an explicit error, and the beta-role node for unit
   widget stays clean and records no feedback message.

## Scenario 3 — Blaming when the target has no eligible blame target

Given: the alpha-role target node for unit widget is configured to receive feedback and declares no
upstream dependency, so it has no eligible blame target; the critique
`the widget contract contradicts the gadget contract` carries no newline character.

1. The agent blames the gadget beta-role node for the defect with that critique.
   Observed: the attribution is refused with an explicit error, and no node records a feedback
   message.

## Scenario 4 — Blaming with a critique that spans two lines

Given: the alpha-role target node for unit widget is configured to receive feedback and declares
the upstream dependency of unit gadget in role beta, which is eligible for blame; the gadget
beta-role node is clean and records no feedback message; the two-line critique is
`the widget contract contradicts the gadget contract` followed by
`and the sprocket contract is stale`.

1. The agent blames the gadget beta-role node with that two-line critique.
   Observed: the attribution is refused with an explicit error, and the gadget beta-role node stays
   clean and records no feedback message.

2. The agent blames the gadget beta-role node with the single-paragraph critique
   `the widget contract contradicts the gadget contract`.
   Observed: an accepted attribution outcome; the gadget beta-role node records the feedback
   message `the widget contract contradicts the gadget contract` and is dirty.

## Scenario 5 — Recording task failure for a target node

Given: the alpha-role target node for unit widget is dirty; its in-batch dependent nodes of unit
gadget in role alpha and unit sprocket in role alpha are clean; the failure explanation is
`the widget contract does not declare the gadget field`.

1. The agent records the failure for the alpha-role target node for unit widget with that
   explanation.
   Observed: an accepted attribution outcome; the alpha-role target node for unit widget records
   the failure explanation `the widget contract does not declare the gadget field` and remains
   dirty; and the two in-batch dependent nodes are failed.

## Scenario 6 — Blaming a culprit file in the canonical repository

Given: the agent is cleaning the read-write file `/ws/alpha_scope_a/parts/widget/widget_spec.md` as
role alpha, and that file's configured blame targets are the read-only files
`/repo/parts/gadget/gadget_spec.md` and `/repo/parts/sprocket/sprocket_spec.md`; the canonical
repository copy of the gadget file is clean and records no unacted feedback item, and its local
role workspace copy is `/ws/alpha_scope_a/parts/gadget/gadget_spec.md`; the critique
`the gadget contract fixes the widget field type incorrectly` carries no newline character.

1. The agent blames the culprit file `/repo/parts/gadget/gadget_spec.md` with that critique.
   Observed: an accepted attribution outcome; the canonical repository file
   `/repo/parts/gadget/gadget_spec.md` records the critique
   `the gadget contract fixes the widget field type incorrectly` as an unacted feedback item and is
   marked dirty; and the local role workspace file
   `/ws/alpha_scope_a/parts/gadget/gadget_spec.md` carries the same updated content.

2. The agent blames the file `/repo/parts/widget/widget_spec.md`, which is not among the configured
   blame targets of the file being cleaned.
   Observed: the attribution is refused with an explicit error, and neither the canonical
   repository file nor any local role workspace file is modified.

## Scenario 7 — Recording task failure for a file target

Given: the agent is cleaning the read-write file `/ws/alpha_scope_a/parts/widget/widget_spec.md` as
role alpha, whose verification failed with the diagnostics
`the widget field type is not accepted`; the canonical repository copy of that file is
`/repo/parts/widget/widget_spec.md`, and it records no unacted feedback item.

1. The agent records the failure for that file target with those diagnostics.
   Observed: an accepted attribution outcome; the canonical repository file
   `/repo/parts/widget/widget_spec.md` records the diagnostics
   `the widget field type is not accepted` as an unacted feedback item and is marked dirty; and the
   local role workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` carries the same
   updated content.
