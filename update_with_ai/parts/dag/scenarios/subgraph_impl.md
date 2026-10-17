<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:22Z
CHANGE: Author dag subgraph_impl concrete scenarios
CODE_HASH: 4a7f97df62bf
-->

# Concrete scenarios for `subgraph_impl` (implementation)

Scenarios 1 through 8 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 9 through
12 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Establishing the active subgraph and its dependency-first order

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index, which the set-target operation
   writes.

2. The caller reads the topological order of the active subgraph.
   Observed: the beta-role node for gadget, then the beta-role node for widget, then the alpha-role
   node for widget, then the alpha-role node for gadget.
   Realized by: the component's own dependency-first ordering pass over that index, which emits a
   node only after its dependencies, orders the remaining ties by role tier depth and unit address,
   and separates the last tie by role address, realizing `subgraph`'s maintained topological
   order.

### Scenario 2 — A complete subgraph beside a dirty node it does not reach

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; those four nodes are all clean; the gamma-role node for sprocket is dirty and lies
on no path from the alpha-role node for gadget.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget, and does not hold the
   gamma-role node for sprocket.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index.

2. The caller reads whether the active subgraph is complete.
   Observed: complete, because every node reachable from the alpha-role node for gadget is clean,
   and the dirty gamma-role node for sprocket is not in the subgraph.
   Realized by: the component's own completion check, which reads the clean status of every indexed
   node through `dag_storage`.

3. The caller reads the next ready batch.
   Observed: an empty batch, because no dirty node in the target subgraph has all of its dependencies
   clean.
   Realized by: the component's own batch scan over the indexed topological order, which reports an
   empty sequence when no indexed dirty node has all of its dependencies clean through `dag_storage`.

### Scenario 3 — An incomplete subgraph holding a dirty node

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; the beta-role node for widget is dirty, and the alpha-role node for gadget, the
alpha-role node for widget and the beta-role node for gadget are clean.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index.

2. The caller reads whether the active subgraph is complete.
   Observed: not complete, because the beta-role node for widget is reachable and dirty.
   Realized by: the component's own completion check over the index, with the beta-role node for
   widget's dirtiness read through `dag_storage`.

### Scenario 4 — The next ready batch grouped by role address

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; the beta-role nodes for gadget and widget are clean, and the alpha-role nodes for
gadget and widget are dirty.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index.

2. The caller reads the next ready batch.
   Observed: the alpha-role node for widget and then the alpha-role node for gadget, because the
   earliest ready dirty node is the alpha-role node for widget, and the alpha-role node for gadget is
   collected into the same batch with both of its dependencies satisfied.
   Realized by: the component's own batch scan, which begins at the earliest dirty indexed node
   whose dependencies are clean through `dag_storage` and extends over the contiguous nodes sharing
   that node's role address, bounded by the batch size supplied by `dag_config`.

### Scenario 5 — The next ready batch beginning at a beta-role node

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; the beta-role nodes for gadget and widget are dirty, and the alpha-role nodes for
gadget and widget are dirty.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index.

2. The caller reads the next ready batch.
   Observed: the beta-role node for gadget and then the beta-role node for widget, because the
   earliest ready dirty node in topological order is the beta-role node for gadget, and the batch
   follows that node's role address.
   Realized by: the component's own batch scan over the indexed order, which groups the batch by
   role address and takes node status from `dag_storage`.

### Scenario 6 — A batch that leaves out a node whose dependency is dirty

Given: role alpha declares no role dependency, so the alpha tier depth is zero, and role beta
declares role alpha as the role it depends on, so the beta tier depth is one; the alpha-role node for
gadget depends on the beta-role node for widget; the beta-role node for widget depends on the
alpha-role node for widget; the alpha-role node for widget declares no dependencies; all three nodes
are dirty.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget and the beta-role node for widget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index.

2. The caller reads the next ready batch.
   Observed: the alpha-role node for widget alone, because the next alpha-role node in order, the
   alpha-role node for gadget, depends on the dirty beta-role node for widget, which is neither
   clean nor present in the same batch.
   Realized by: the component's own batch scan, which collects a node only when its dependencies are
   clean through `dag_storage` or already collected into the same batch.

### Scenario 7 — A target node with no dependencies

Given: the alpha-role node for widget declares no dependencies and is dirty.

1. The caller sets the target node to the alpha-role node for widget.
   Observed: the active subgraph holds the alpha-role node for widget alone.
   Realized by: the component's own indexing of the target node into its in-memory graph index, its
   dependency query through `dag_storage` finding no dependencies.

2. The caller reads whether the active subgraph is complete.
   Observed: not complete, because the alpha-role node for widget is dirty.
   Realized by: the component's own completion check, reading the single indexed node's status
   through `dag_storage`.

3. The caller reads the next ready batch.
   Observed: the alpha-role node for widget alone.
   Realized by: the component's own batch scan over the indexed order.

### Scenario 8 — Recording visits up to the configured visit limit

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for gadget; the alpha-role node for widget depends on the beta-role
node for widget; the beta-role nodes for gadget and widget are clean, and the alpha-role nodes for
gadget and widget are dirty; the node visit limit for the system is two.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget, the beta-role node for gadget and the beta-role node for widget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index.

2. The caller reads the next ready batch.
   Observed: the alpha-role node for widget and then the alpha-role node for gadget.
   Realized by: the component's own batch scan over the indexed order.

3. The caller records the visit for that batch.
   Observed: both nodes of the batch have their visit count advanced, and no visit limit failure is
   reported.
   Realized by: the component's own visit counters for the batch, whose bound is the node visit
   limit supplied by `dag_config`.

4. The caller records the visit for the same batch a second time.
   Observed: both nodes of the batch have their visit count advanced to the limit of two, and no
   visit limit failure is reported.
   Realized by: the same visit counters, now at the node visit limit supplied by `dag_config`.

5. The caller records the visit for the same batch a third time.
   Observed: the recording fails explicitly, because a node of the batch exceeds the visit limit of
   two.
   Realized by: the node visit limit supplied by `dag_config` and the component's own visit
   counters, which raise the explicit failure for the offending node.

## Implementation-only

### Scenario 9 — The batch never exceeds the configured batch size

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for sprocket depends on the alpha-role node for
widget and on the alpha-role node for gadget; the alpha-role nodes for gadget and widget each depend
on the beta-role node for gadget; the beta-role node for gadget is clean; the alpha-role nodes for
gadget, sprocket and widget are dirty; the batch size for the system is two and the node visit limit
is three.

1. The caller sets the target node to the alpha-role node for sprocket.
   Observed: the active subgraph holds the alpha-role node for sprocket, the alpha-role node for
   gadget, the alpha-role node for widget and the beta-role node for gadget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index.

2. The caller reads the next ready batch.
   Observed: the alpha-role node for gadget and then the alpha-role node for widget, and not the
   alpha-role node for sprocket, because the batch does not exceed the batch size of two.
   Realized by: the component's own batch scan, whose contiguous run over the first node's role
   address is truncated at the batch size supplied by `dag_config`.

### Scenario 10 — The batch stops at the first node of a different role address

Given: role alpha declares no role dependency, so the alpha tier depth is zero, and role beta
declares role alpha as the role it depends on, so the beta tier depth is one; the alpha-role node for
gadget depends on the beta-role node for widget; the beta-role node for widget depends on the
alpha-role node for widget; the alpha-role node for widget is dirty, the beta-role node for widget is
clean and the alpha-role node for gadget is dirty; the batch size for the system is four.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget and the beta-role node for widget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index.

2. The caller reads the next ready batch.
   Observed: the alpha-role node for widget alone, although the alpha-role node for gadget is dirty
   and shares that role address, because the batch extends only over the contiguous nodes that share
   the first node's role address and the clean beta-role node for widget lies between them.
   Realized by: the component's own batch scan over the indexed topological order, which stops at the
   first indexed node whose role address differs from the batch's.

### Scenario 11 — A tier-depth and unit-address tie separated by role address

Given: role alpha declares no role dependency and role beta declares no role dependency, so both the
alpha tier depth and the beta tier depth are zero; the alpha-role node for widget declares no
dependencies; the beta-role node for widget declares no dependencies; the alpha-role node for gadget
depends on the alpha-role node for widget and on the beta-role node for widget.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget and the beta-role node for widget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index.

2. The caller reads the topological order of the active subgraph.
   Observed: the alpha-role node for widget, then the beta-role node for widget, then the alpha-role
   node for gadget, because the two widget nodes share a tier depth and a unit address and are
   separated by role address.
   Realized by: the component's own ordering pass, whose third tie break is the role address, after
   the role tier depth and the unit address.

### Scenario 12 — Node status is read when the batch is drawn, not when the target is indexed

Given: role alpha declares role beta as the role it depends on, so the alpha tier depth is one and
the beta tier depth is zero; the alpha-role node for gadget depends on the alpha-role node for
widget and on the beta-role node for widget; the alpha-role node for widget is clean; the beta-role
node for widget and the alpha-role node for gadget are dirty.

1. The caller sets the target node to the alpha-role node for gadget.
   Observed: the active subgraph holds the alpha-role node for gadget, the alpha-role node for
   widget and the beta-role node for widget.
   Realized by: reachability and dependency queries through `dag_storage`, and the component's own
   indexing of every reachable node into its in-memory graph index, which holds structure rather
   than status.

2. The caller reads the next ready batch.
   Observed: the beta-role node for widget alone.
   Realized by: the component's own batch scan, which consults node status through `dag_storage` for
   each query.

3. The caller marks the beta-role node for widget clean in dag storage and reads the next ready
   batch again.
   Observed: the alpha-role node for gadget alone.
   Realized by: the component's own batch scan, which reads the freshly cleaned status through
   `dag_storage` instead of reusing the status captured when the target was indexed.
