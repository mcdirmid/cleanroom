<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:21Z
CHANGE: Author dag dag_storage concrete scenarios
CODE_HASH: c2b45373db5b
-->

# Concrete scenarios for `dag_storage` (interface)

## Scenario 1 — Reading a node's dependencies across the silent partition

Given: the alpha-role node for sprocket depends on the beta-role node for widget and on the beta-role
node for gadget; the beta-role node for widget is silent and the beta-role node for gadget is not
silent; the alpha-role node for widget declares no dependencies.

1. The caller reads the dependencies of the alpha-role node for sprocket.
   Observed: two dependencies, the beta-role node for widget reported silent and the beta-role node
   for gadget reported not silent.

2. The caller reads the dependencies of the alpha-role node for widget.
   Observed: an empty dependency sequence.

## Scenario 2 — Reading a node's messages and marking the node clean

Given: the beta-role node for gadget was marked dirty with the reason "the upstream contract
changed", its source artifact exists on disk, and it holds the unacted feedback message "the
beta-role output omits the required field".

1. The caller reads the messages recorded for the beta-role node for gadget.
   Observed: one message, the text "the beta-role output omits the required field" recorded as
   unacted feedback.

2. The caller marks the beta-role node for gadget clean.
   Observed: the messages recorded for the node are cleared, its in-band metadata carries a clean
   timestamp, and the node's unacted feedback and dirty tag are cleared, so the node reports as not
   dirty.

## Scenario 3 — Marking a node clean with a change message

Given: the alpha-role node for widget's source artifact exists on disk, the node is dirty, and the
caller supplies the change message "the beta-role contract for gadget gained a required field".

1. The caller marks the alpha-role node for widget clean with that change message.
   Observed: the node's in-band metadata carries a clean timestamp, the change summary "the
   beta-role contract for gadget gained a required field" and a change timestamp, and the node
   reports as not dirty.

## Scenario 4 — Marking a node clean whose source artifact is missing

Given: the gamma-role node for sprocket's source artifact is missing on disk, the node holds the
unacted feedback message "the sprocket gamma-role output is stale", and the node is dirty.

1. The caller marks the gamma-role node for sprocket clean.
   Observed: the messages recorded for the node are cleared, but no clean timestamp is written to
   its in-band metadata because its source artifact does not exist, so the node still reports as
   dirty.

2. The caller marks the gamma-role node for sprocket clean with the change message "the beta-role
   contract for gadget gained a required field".
   Observed: neither a clean timestamp nor the change summary "the beta-role contract for gadget
   gained a required field" is written to the node's in-band metadata, and the node still reports
   as dirty.

## Scenario 5 — Reporting dirtiness across its causes

Given: the beta-role node for widget is clean; the alpha-role node for gadget's source artifact is
missing on disk; the alpha-role node for sprocket carries in-band metadata that is invalid; the
alpha-role node for widget was marked dirty with the reason "the upstream contract changed"; the
delta-role node for widget's source artifact exists on disk with no in-band metadata at all.

1. The caller asks whether the beta-role node for widget is dirty.
   Observed: not dirty.

2. The caller asks whether the alpha-role node for gadget is dirty.
   Observed: dirty, because its source artifact is missing on disk.

3. The caller asks whether the alpha-role node for sprocket is dirty.
   Observed: dirty, because its in-band metadata is invalid.

4. The caller asks whether the alpha-role node for widget is dirty.
   Observed: dirty, because it carries a dirty tag.

5. The caller asks whether the delta-role node for widget is dirty.
   Observed: dirty, because its in-band metadata is missing.

## Scenario 6 — Reporting dirtiness from dependency changes

Given: role alpha declares role beta as the role it depends on; the alpha-role node for widget was
marked clean at 2026-01-02T03:04:05Z and depends non-silently on the beta-role node for gadget,
which was marked clean with the change message "the gadget beta-role output gained a required field"
at 2026-01-02T04:05:06Z; the alpha-role node for sprocket was marked clean at 2026-01-02T05:00:00Z
and depends silently on that same beta-role node for gadget; the alpha-role node for gadget was
marked clean at 2026-01-02T07:00:00Z and depends non-silently on the beta-role node for widget,
which was marked clean with the change message "the widget beta-role output gained a required field"
at 2026-01-02T06:00:00Z.

1. The caller asks whether the alpha-role node for widget is dirty.
   Observed: dirty, because a non-silent dependency was changed after the node was last cleaned.

2. The caller asks whether the alpha-role node for sprocket is dirty.
   Observed: not dirty, because its dependency is silent and precludes change message propagation.

3. The caller asks whether the alpha-role node for gadget is dirty.
   Observed: not dirty, because its non-silent dependency was changed before the node was last
   cleaned.

## Scenario 7 — Adding a feedback message that blames a dependency target

Given: the alpha-role node for sprocket depends non-silently on the beta-role node for widget; the
beta-role node for widget is clean and holds no messages.

1. The caller adds the feedback message "the widget beta-role output omits the required field",
   blaming the beta-role node for widget.
   Observed: that text is recorded as unacted feedback in the beta-role node for widget's in-band
   metadata, the messages recorded for that node now hold it, and the node reports as dirty.

## Scenario 8 — Materializing a template for a node whose source artifact is missing

Given: the beta-role node for gadget's source artifact is missing on disk, and the initial content
of the beta-role template is "# gadget beta: describe the beta-role work here".

1. The caller materializes the template for the beta-role node for gadget.
   Observed: the node's source artifact now exists on disk holding "# gadget beta: describe the
   beta-role work here".

## Scenario 9 — Preserving an existing source artifact when materializing a template

Given: the alpha-role node for widget's source artifact exists on disk holding "# widget alpha:
edited by the caller", and the initial content of the alpha-role template is "# widget alpha:
describe the alpha-role work here".

1. The caller materializes the template for the alpha-role node for widget.
   Observed: the source artifact is preserved and still holds "# widget alpha: edited by the
   caller", rather than the template's initial content.

## Scenario 10 — Marking a node dirty with a reason

Given: the beta-role node for widget was marked clean at 2026-01-02T03:04:05Z, and the caller
supplies the reason "the upstream contract changed".

1. The caller marks the beta-role node for widget dirty with that reason.
   Observed: the node's clean status is removed, the reason "the upstream contract changed" is
   recorded in its in-band metadata, and the node reports as dirty.

## Scenario 11 — Marking a subgraph clean over a chain of dependencies

Given: role alpha declares role beta as the role it depends on and role beta declares role gamma as
the role it depends on; the alpha-role node for widget depends on the beta-role node for widget,
which depends on the gamma-role node for widget; the gamma-role node for widget's source artifact is
missing on disk and the initial content of the gamma-role template is "# widget gamma: describe the
gamma-role work here"; the alpha-role, beta-role and gamma-role nodes for widget are dirty; the
alpha-role node for gadget is dirty and lies on no path from the alpha-role node for widget.

1. The caller marks the subgraph clean at the alpha-role node for widget.
   Observed: the gamma-role node for widget's source artifact is materialized from the template, the
   alpha-role, beta-role and gamma-role nodes for widget are all marked clean, and the alpha-role
   node for gadget is still dirty.

## Scenario 12 — Marking a subgraph clean at a node that depends on itself

Given: the alpha-role node for widget declares itself as one of its own dag dependencies and is
dirty; the alpha-role node for gadget is dirty and lies on no path from the alpha-role node for
widget.

1. The caller marks the subgraph clean at the alpha-role node for widget.
   Observed: the alpha-role node for widget is marked clean, the reachable subgraph being that node
   alone, and the alpha-role node for gadget is still dirty.

## Scenario 13 — Marking a subgraph clean across a cycle of dependencies

Given: the alpha-role node for widget depends on the beta-role node for widget and the beta-role
node for widget depends on the alpha-role node for widget; both nodes are dirty; the alpha-role node
for gadget is dirty and lies on no path from either node.

1. The caller marks the subgraph clean at the alpha-role node for widget.
   Observed: both the alpha-role node for widget and the beta-role node for widget are marked clean,
   each being reachable from the other, and the alpha-role node for gadget is still dirty.
