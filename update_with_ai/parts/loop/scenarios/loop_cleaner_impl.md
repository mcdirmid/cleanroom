<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T03:11:45Z
CHANGE: Author loop loop_cleaner_impl concrete scenarios
CODE_HASH: 7260081b61c7
-->

# Concrete scenarios for `loop_cleaner_impl` (implementation)

Scenarios 1 through 7 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 8
through 11 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — A subgraph that is already clean

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are clean
with last cleaned timestamp 2026-01-02T03:04:05Z; and the supplied alpha node cleaner cleans the
dirty nodes that share role alpha.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: cleaning concludes, no node is cleaned, and both nodes keep the last cleaned timestamp
   2026-01-02T03:04:05Z.
   Realized by: the component's own subgraph scoping, which sets the alpha-role target for widget as
   the active target node on `dag_subgraph`, and the completion report from `dag_subgraph` that
   every node reachable from it is clean in `dag_storage`.

### Scenario 2 — A dirty dependency is cleaned before the node that depends on it

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are dirty,
the beta-role target for gadget because its in-band source metadata is missing, and the alpha-role
target for widget because the beta-role target for gadget changed at 2026-01-03T04:05:06Z.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked to clean the beta-role target for gadget, which is
   clean afterwards, before it is asked to clean the alpha-role target for widget; then cleaning
   concludes with both nodes clean.
   Realized by: the dependency-first topological order and the ready batch of dirty nodes supplied by
   `dag_subgraph`; node execution delegated to `loop_node_cleaner`; and the component's own
   iteration, which reads the next ready batch after each cleaned batch.

### Scenario 3 — A chain of three dirty nodes cleaned in dependency order

Given: the alpha-role target for widget depends on the beta-role target for gadget, which depends on
the gamma-role target for sprocket, and all three nodes are dirty.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked for the gamma-role target for sprocket, then for the
   beta-role target for gadget, then for the alpha-role target for widget; and cleaning concludes
   with all three nodes clean.
   Realized by: the dependency-first topological order and successive ready batches from
   `dag_subgraph`; node execution delegated to `loop_node_cleaner`; and the component's own
   re-evaluation of the next ready batch after every cleaned batch.

### Scenario 4 — A dirty node outside the target subgraph is not cleaned

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are dirty;
and the gamma-role target for sprocket is dirty but neither it nor anything it reaches is a
dependency of the alpha-role target for widget.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the beta-role target for gadget and the alpha-role target for widget are clean; the
   gamma-role target for sprocket is still dirty and was never asked of the supplied node cleaner;
   and cleaning concludes.
   Realized by: the active subgraph maintained by `dag_subgraph`, which holds only the nodes
   reachable from the target node, and node execution delegated to `loop_node_cleaner` for the
   batches that subgraph supplies.

### Scenario 5 — A dependency between two roles of the same unit

Given: the alpha-role target for widget depends on the beta-role target for widget, and both are
dirty.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked to clean the beta-role target for widget before the
   alpha-role target for widget, and cleaning concludes with both nodes clean.
   Realized by: the dependency-first topological order from `dag_subgraph`, which places the
   beta-role target for widget ahead of the alpha-role target for widget within the same unit, and
   node execution delegated to `loop_node_cleaner`.

### Scenario 6 — Halting when the supplied node cleaner cannot continue

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are dirty;
and the supplied alpha node cleaner communicates that processing cannot continue when it is asked to
clean the beta-role target for gadget.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: cleaning halts immediately; the beta-role target for gadget is still dirty; and the
   alpha-role target for widget was never asked of the supplied node cleaner and is still dirty.
   Realized by: the continuation signal from `loop_node_cleaner` and the component's own immediate
   halt, which stops before requesting another ready batch from `dag_subgraph`.

### Scenario 7 — A dirty node whose dependency an earlier run already cleaned

Given: the alpha-role target for widget depends on the beta-role target for gadget; the beta-role
target for gadget is clean with last cleaned timestamp 2026-01-02T03:04:05Z; and the alpha-role
target for widget is dirty because the beta-role target for gadget changed at 2026-01-03T04:05:06Z.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked only for the alpha-role target for widget, which is
   clean afterwards, and cleaning concludes without asking for the beta-role target for gadget.
   Realized by: the ready batch from `dag_subgraph`, which holds only the dirty nodes whose
   dependencies are clean in `dag_storage`, and node execution delegated to `loop_node_cleaner` for
   that batch.

## Implementation-only

### Scenario 8 — A halt inside a ready batch abandons the rest of the batch

Given: the alpha-role target for widget depends on the beta-role target for gadget and on the
gamma-role target for sprocket; all three nodes are dirty; the beta-role target for gadget and the
gamma-role target for sprocket are ordered ahead of the alpha-role target for widget; and the
supplied alpha node cleaner communicates that processing cannot continue after the beta-role target
for gadget is cleaned.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: cleaning halts with the gamma-role target for sprocket still dirty although it was part
   of the same ready batch, and the alpha-role target for widget was never asked of the supplied node
   cleaner and is still dirty.
   Realized by: the ready batch from `dag_subgraph`, which holds the two independent dirty nodes;
   node execution delegated to `loop_node_cleaner` for that batch; and the component's own immediate
   halt, which abandons the remaining nodes of the batch.

### Scenario 9 — Cleaning a second target re-scopes the active subgraph

Given: the alpha-role target for widget depends on the beta-role target for gadget; the gamma-role
target for sprocket depends on nothing; and all three nodes are dirty.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the beta-role target for gadget and the alpha-role target for widget are clean, and the
   gamma-role target for sprocket is still dirty.
   Realized by: the component's own scoping, which sets the alpha-role target for widget as the
   active target node on `dag_subgraph`, and node execution delegated to `loop_node_cleaner` for the
   batches that subgraph supplies.

2. The caller cleans the gamma-role target for sprocket using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked only for the gamma-role target for sprocket, which is
   clean afterwards, and cleaning concludes.
   Realized by: the component's own re-scoping, which replaces the active target node on
   `dag_subgraph` with the gamma-role target for sprocket before any batch is requested.

### Scenario 10 — A node that keeps returning dirty is failed at the configured visit limit

Given: the alpha-role target for widget is dirty, the supplied node cleaner cleans it while leaving
it dirty, and the visit limit for the target subgraph is 3.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the alpha-role target for widget is visited and recorded three times, cleaning then
   fails explicitly rather than cleaning it a fourth time, and the node is still dirty.
   Realized by: the component's own visit recording for each cleaned batch through `dag_subgraph`,
   which advances the visit count of each node in the batch and fails when a node exceeds the
   configured visit limit.

### Scenario 11 — A complete target subgraph concludes before any ready batch is read

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are clean
with last cleaned timestamp 2026-01-02T03:04:05Z; and the gamma-role target for sprocket is dirty and
lies outside the target subgraph.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: cleaning concludes without the supplied node cleaner being asked to clean any node, and
   the gamma-role target for sprocket is still dirty.
   Realized by: the completion report from `dag_subgraph` over the active subgraph, which the
   component reads before requesting a ready batch.
