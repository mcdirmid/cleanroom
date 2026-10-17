<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:21Z
CHANGE: Author dag dag_subgraph concrete scenarios
CODE_HASH: b227c1b0f898
-->

# Concrete scenarios for `dag_subgraph` (interface)

## Scenario 1 — Establishing the active subgraph and its dependency-first order

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.

2. The caller reads the topological order of the active subgraph.
   Observed: the beta-role node for gadget, then the beta-role node for widget, then the alpha-role
   node for widget, then the alpha-role node for gadget.

## Scenario 2 — A complete subgraph beside a dirty node it does not reach

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; those four nodes are all clean; the gamma-role node for sprocket is dirty and lies
on no path from the alpha-role node for gadget.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget, and does not hold the
   gamma-role node for sprocket.

2. The caller reads whether the active subgraph is complete.
   Observed: complete, because every node reachable from the alpha-role node for gadget is clean,
   and the dirty gamma-role node for sprocket is not in the subgraph.

3. The caller reads the next ready batch.
   Observed: an empty batch, because no dirty node in the target subgraph has all of its dependencies
   clean.

## Scenario 3 — An incomplete subgraph holding a dirty node

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; the beta-role node for widget is dirty, and the alpha-role node for gadget, the
alpha-role node for widget and the beta-role node for gadget are clean.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.

2. The caller reads whether the active subgraph is complete.
   Observed: not complete, because the beta-role node for widget is reachable and dirty.

## Scenario 4 — The next ready batch grouped by role address

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; the beta-role nodes for gadget and widget are clean, and the alpha-role nodes for
gadget and widget are dirty.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.

2. The caller reads the next ready batch.
   Observed: the alpha-role node for widget and then the alpha-role node for gadget, because the
   earliest ready dirty node is the alpha-role node for widget, and the alpha-role node for gadget is
   collected into the same batch with both of its dependencies satisfied.

## Scenario 5 — The next ready batch beginning at a beta-role node

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; the beta-role nodes for gadget and widget are dirty, and the alpha-role nodes for
gadget and widget are dirty.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.

2. The caller reads the next ready batch.
   Observed: the beta-role node for gadget and then the beta-role node for widget, because the
   earliest ready dirty node in topological order is the beta-role node for gadget, and the batch
   follows that node's role address.

## Scenario 6 — A batch that leaves out a node whose dependency is dirty

Given: role alpha declares no role dependency, so the alpha tier depth is zero, and role beta
declares role alpha as the role it depends on, so the beta tier depth is one; the alpha-role node for
gadget depends on the beta-role node for widget; the beta-role node for widget depends on the
alpha-role node for widget; the alpha-role node for widget declares no dependencies; all three nodes
are dirty.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget and the beta-role node for widget.

2. The caller reads the next ready batch.
   Observed: the alpha-role node for widget alone, because the next alpha-role node in order, the
   alpha-role node for gadget, depends on the dirty beta-role node for widget, which is neither
   clean nor present in the same batch.

## Scenario 7 — A target node with no dependencies

Given: the alpha-role node for widget declares no dependencies and is dirty.

1. The caller sets the target node to the alpha-role node for widget.
   Observed: the active subgraph holds the alpha-role node for widget alone.

2. The caller reads whether the active subgraph is complete.
   Observed: not complete, because the alpha-role node for widget is dirty.

3. The caller reads the next ready batch.
   Observed: the alpha-role node for widget alone.

## Scenario 8 — Recording visits up to the configured visit limit

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; the beta-role nodes for gadget and widget are clean, and the alpha-role nodes for
gadget and widget are dirty; the node visit limit for the system is two.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.

2. The caller reads the next ready batch.
   Observed: the alpha-role node for widget and then the alpha-role node for gadget.

3. The caller records the visit for that batch.
   Observed: both nodes of the batch have their visit count advanced, and no visit limit failure is
   reported.

4. The caller records the visit for the same batch a second time.
   Observed: both nodes of the batch have their visit count advanced to the limit of two, and no
   visit limit failure is reported.

5. The caller records the visit for the same batch a third time.
   Observed: the recording fails explicitly, because a node of the batch exceeds the visit limit of
   two.

## Scenario 9 — Breaking ties between nodes of identical role tier depth with colon-qualified role addresses

Given: role `//my/scope:alpha` and role `//my/scope:beta` both have role tier depth zero; node `//my/pkg:widget#//my/scope:alpha` and node `//my/pkg:widget#//my/scope:beta` have no dependency ordering relative to each other.

1. The caller computes topological order.
   Observed: `//my/pkg:widget#//my/scope:alpha` precedes `//my/pkg:widget#//my/scope:beta` based on alphabetical comparison of the unqualified role names `alpha` vs `beta` extracted after the final colon delimiter.
