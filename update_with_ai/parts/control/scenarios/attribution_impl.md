# Concrete scenarios for `attribution_impl` (implementation)

Scenarios 1 through 7 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 8
through 12 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Blaming one eligible upstream dependency among several

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
   Realized by: dag dependency lookups through `dag_storage` for the target node's upstream
   dependencies and role configuration lookups through `agent_node_config` for the node configured
   to receive feedback; the component's own newline check over the explanation; `dag_storage`
   feedback message recording, which writes the critique into the culprit node's in-band metadata
   as unacted feedback through `src_metadata`; `dag_storage` dirty marking on the culprit; and the
   component's own failure marking of the in-batch dependents, scoped through `agent_session`.

### Scenario 2 — Blaming the target itself, a disconnected node, and a downstream dependent

Given: the alpha-role target node for unit widget is configured to receive feedback and declares
the upstream dependency of unit sprocket in role gamma, which is eligible for blame; the delta-role
node for unit sprocket is neither an upstream dependency nor a dependent of the target node; the
beta-role node for unit widget depends on the alpha-role target node; the critique
`the widget contract contradicts the gadget contract` carries no newline character.

1. The agent blames the alpha-role target node for unit widget itself with that critique.
   Observed: the attribution is refused with an explicit error, the alpha-role target node records
   no feedback message, and no node changes status.
   Realized by: `dag_storage` dag dependency lookups, whose result for the target node never
   includes the node itself, and the component's own refusal, which stops before any status
   mutation or feedback write.

2. The agent blames the delta-role node for unit sprocket with that critique.
   Observed: the attribution is refused with an explicit error, and the delta-role node for unit
   sprocket records no feedback message.
   Realized by: `dag_storage` dag dependency lookups, which report no dependency relation to the
   delta-role node, and the component's own refusal.

3. The agent blames the beta-role node for unit widget with that critique.
   Observed: the attribution is refused with an explicit error, and the beta-role node for unit
   widget stays clean and records no feedback message.
   Realized by: `dag_storage` dag dependency lookups, which report the beta-role node as a
   dependent rather than an upstream dependency, and the component's own refusal.

### Scenario 3 — Blaming when the target has no eligible blame target

Given: the alpha-role target node for unit widget is configured to receive feedback and declares no
upstream dependency, so it has no eligible blame target; the critique
`the widget contract contradicts the gadget contract` carries no newline character.

1. The agent blames the gadget beta-role node for the defect with that critique.
   Observed: the attribution is refused with an explicit error, and no node records a feedback
   message.
   Realized by: `dag_storage` dag dependency lookups returning no upstream dependency and role
   configuration lookups through `agent_node_config` returning no blame target, and the
   component's own refusal, which writes nothing.

### Scenario 4 — Blaming with a critique that spans two lines

Given: the alpha-role target node for unit widget is configured to receive feedback and declares
the upstream dependency of unit gadget in role beta, which is eligible for blame; the gadget
beta-role node is clean and records no feedback message; the two-line critique is
`the widget contract contradicts the gadget contract` followed by
`and the sprocket contract is stale`.

1. The agent blames the gadget beta-role node with that two-line critique.
   Observed: the attribution is refused with an explicit error, and the gadget beta-role node stays
   clean and records no feedback message.
   Realized by: the component's own newline check over the explanation, which refuses before
   `dag_storage` feedback message recording is reached.

2. The agent blames the gadget beta-role node with the single-paragraph critique
   `the widget contract contradicts the gadget contract`.
   Observed: an accepted attribution outcome; the gadget beta-role node records the feedback
   message `the widget contract contradicts the gadget contract` and is dirty.
   Realized by: the component's own newline check passing, followed by `dag_storage` feedback
   message recording and dirty marking, and the component's own outcome construction.

### Scenario 5 — Recording task failure for a target node

Given: the alpha-role target node for unit widget is dirty; its in-batch dependent nodes of unit
gadget in role alpha and unit sprocket in role alpha are clean; the failure explanation is
`the widget contract does not declare the gadget field`.

1. The agent records the failure for the alpha-role target node for unit widget with that
   explanation.
   Observed: an accepted attribution outcome; the alpha-role target node for unit widget records
   the failure explanation `the widget contract does not declare the gadget field` and remains
   dirty; and the two in-batch dependent nodes are failed.
   Realized by: `dag_storage` failure recording on the target node and its preservation of the
   node's dirty status; the component's own failure marking of the in-batch dependents; and
   session failure bookkeeping scoped through `agent_session`.

### Scenario 6 — Blaming a culprit file in the canonical repository

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
   Realized by: the component's own resolution of the culprit path against the configured blame
   targets and the canonical repository and workspace roots, with addressing through
   `agent_file_alias`; the component's own newline check over the critique; `src_metadata`, which
   appends the in-band feedback and dirty markers to the canonical file; and the component's own
   synchronization of the updated canonical file back over the role workspace file.

2. The agent blames the file `/repo/parts/widget/widget_spec.md`, which is not among the configured
   blame targets of the file being cleaned.
   Observed: the attribution is refused with an explicit error, and neither the canonical
   repository file nor any local role workspace file is modified.
   Realized by: the component's own comparison of the named path against the blame targets supplied
   by `agent_node_config`, refusing before `src_metadata` is reached.

### Scenario 7 — Recording task failure for a file target

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
   Realized by: the component's own resolution of the target path through `agent_file_alias`;
   `src_metadata`, which appends the diagnostics and dirty markers to the canonical file; the
   component's own synchronization of the updated canonical file back to the role workspace; and
   the component's own outcome construction.

## Implementation-only

### Scenario 8 — Refusing attribution while an in-batch dependency is not clean

Given: the alpha-role target node for unit widget is configured to receive feedback, declares the
eligible blame target of unit gadget in role beta, and has the in-batch dependency of unit
sprocket in role beta, which is dirty; the critique
`the widget contract contradicts the gadget contract` carries no newline character.

1. The agent blames the gadget beta-role node with that critique.
   Observed: the attribution is refused with an explicit error, and the gadget beta-role node stays
   clean and records no feedback message.
   Realized by: the component's own in-batch dependency check over the node status reported by
   `dag_storage`, which stops before any feedback write.

2. The sprocket beta-role node is brought clean, and the agent blames the gadget beta-role node
   with that critique again.
   Observed: an accepted attribution outcome, and the gadget beta-role node records the feedback
   message `the widget contract contradicts the gadget contract` and is dirty.
   Realized by: the same check now passing, followed by `dag_storage` feedback recording and dirty
   marking.

### Scenario 9 — What a refused attribution reports

Given: the alpha-role target node for unit widget is configured to receive feedback and declares
the eligible blame targets of unit gadget in role beta and unit sprocket in role gamma; the
critique `the widget contract contradicts the gadget contract` carries no newline character.

1. The agent blames the delta-role node for unit sprocket with that critique.
   Observed: the attribution is refused with an explicit error that names unit gadget in role beta
   and unit sprocket in role gamma as the available blame targets.
   Realized by: role configuration lookups through `agent_node_config` for the configured blame
   targets, and the component's own error construction, which formats the eligible targets into the
   refusal.

### Scenario 10 — How an accepted attribution is reported

Given: the alpha-role target node for unit widget is configured to receive feedback, declares the
eligible blame target of unit gadget in role beta, and has no in-batch dependency; the gadget
beta-role node is clean; the critique `the widget contract contradicts the gadget contract`
carries no newline character.

1. The agent blames the gadget beta-role node with that critique.
   Observed: an accepted attribution outcome whose message is formatted as a blame critique
   carrying the explanation `the widget contract contradicts the gadget contract`.
   Realized by: the component's own outcome construction, which formats the blame critique with the
   validated explanation.

### Scenario 11 — Where the critique of a blamed node is stored

Given: the alpha-role target node for unit widget is configured to receive feedback, declares the
eligible blame target of unit gadget in role beta, and has no in-batch dependency; the gadget
beta-role node is clean, records no feedback message, and carries no unacted feedback item; the
critique `the widget contract contradicts the gadget contract` carries no newline character.

1. The agent blames the gadget beta-role node with that critique.
   Observed: the gadget beta-role node records one unacted feedback item carrying
   `the widget contract contradicts the gadget contract`, and is dirty because it holds that
   unacted feedback item.
   Realized by: `dag_storage` feedback message recording, which delegates the in-band write to
   `src_metadata` so that the critique lands in the culprit node's metadata as unacted feedback,
   and `dag_storage` dirty reporting over that feedback.

### Scenario 12 — Refusing a two-line file critique before the canonical file is touched

Given: the agent is cleaning the read-write file `/ws/alpha_scope_a/parts/widget/widget_spec.md` as
role alpha, and that file's configured blame targets include the read-only file
`/repo/parts/gadget/gadget_spec.md`; the canonical repository file is clean and records no unacted
feedback item, and its local role workspace copy is
`/ws/alpha_scope_a/parts/gadget/gadget_spec.md`; the two-line critique is
`the gadget contract fixes the widget field type incorrectly` followed by
`and the sprocket contract too`.

1. The agent blames the culprit file `/repo/parts/gadget/gadget_spec.md` with that two-line
   critique.
   Observed: the attribution is refused with an explicit error, the canonical repository file
   records no unacted feedback item and stays clean, and the local role workspace file is
   unchanged.
   Realized by: the component's own newline check over the critique, which refuses before
   `src_metadata` appends anything and before the component's own synchronization runs.

### Scenario 13 — Refusing blame critiques that exceed maximum feedback character limits

Given: the agent is cleaning the file `/ws/alpha_scope_a/parts/widget/widget_spec.md`, the blame target is `/repo/parts/gadget/gadget_spec.md`, and the maximum feedback character limit is configured as 600 characters; the critique is a single continuous paragraph of 750 characters.

1. The agent blames the culprit file with that oversized critique.
   Observed: the attribution is refused with an explicit error indicating that the critique exceeds the maximum length of 600 characters (750 provided) and advising to prioritize contract discrepancies to report so the authoring role can make progress; neither the canonical repository file nor the local role workspace copy is modified.
   Realized by: the component's own critique character length validation against configured model limits, refusing before `src_metadata` appends feedback.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:12:03Z
CHANGE: Author control attribution_impl concrete scenarios
-->
