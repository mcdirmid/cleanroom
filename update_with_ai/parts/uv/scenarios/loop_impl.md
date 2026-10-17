<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:20:05Z
CHANGE: Author uv loop_impl concrete scenarios
CODE_HASH: bb4eb8c52e1a
-->

# Concrete scenarios for `uv_loop_impl` (implementation)

Scenarios 1 through 31 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 32 through
36 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

The scenarios of the `loop` interface the component implements come first, then the scenarios of the
interface specifications of its imports closure: `loop_cleaner`, `loop_node_cleaner`,
`logger` and `uv_manifest_loader`.

### Scenario 1 — A cleaning pass over a subgraph that is already clean

Given: the alpha-role target for widget, the beta-role target for gadget, and the gamma-role target
for sprocket are clean in graph storage with last cleaned timestamps 2026-01-02T03:04:05Z,
2026-01-02T03:04:05Z, and 2026-01-03T04:05:06Z; and the alpha-role target for widget depends on the
beta-role target for gadget, which depends on the gamma-role target for sprocket.

1. The caller runs a cleaning pass rooted at the alpha-role target for widget. Observed: a build
result reporting success and carrying a summary of the pass; and all three nodes keep the last
cleaned timestamps 2026-01-02T03:04:05Z, 2026-01-02T03:04:05Z, and 2026-01-03T04:05:06Z. Realized
by: target manifest loading through `uv_manifest_loader`; dirty evaluation and graph state storage
through `dag_storage`; topological execution through `loop_cleaner`; and execution telemetry through
`logger`.

### Scenario 2 — A cleaning pass over a dirty dependency and the node that depends on it

Given: the beta-role target for gadget is dirty because its in-band source metadata is missing, the
alpha-role target for widget is dirty because the beta-role target for gadget changed at
2026-01-03T04:05:06Z, the alpha-role target for widget depends on the beta-role target for gadget,
and the cleaning pass runs at 2026-01-04T05:06:07Z.

1. The caller runs a cleaning pass rooted at the alpha-role target for widget. Observed: a build
result reporting success; the beta-role target for gadget is clean with the last cleaned timestamp
2026-01-04T05:06:07Z; and the alpha-role target for widget is clean with the change message
describing how the beta-role target for gadget changed. Realized by: topological execution through
`loop_cleaner` with single-node execution through `loop_node_cleaner`; clean marking and change
message recording through `dag_storage`; and the pass telemetry of `logger`.

### Scenario 3 — Marking a subgraph clean materializes a missing source file

Given: the alpha-role target for widget is dirty and holds the unacted feedback message "widget
reads sprocket output before it is flushed"; the beta-role target for sprocket has no source
artifact on disk and declares the starter template for a sprocket artifact; the gamma-role target
for gadget is clean with the change summary "gadget emits metric names"; and the alpha-role target
for widget depends on the beta-role target for sprocket and on the gamma-role target for gadget.

1. The caller marks the subgraph rooted at the alpha-role target for widget clean.
   Observed: the beta-role target for sprocket holds the source artifact materialized from its
   declared template and is clean with an initialized last cleaned timestamp and the default change
   description; the alpha-role target for widget is clean with no unacted feedback and no dirty tag;
   the gamma-role target for gadget keeps the change summary "gadget emits metric names"; and every
   node reachable from the alpha-role target for widget is clean.
   Realized by: subgraph clean marking through `dag_storage`, whose missing source files the
   component's own stamping of node metadata headers and default change summary accompanies, and
   execution telemetry through `logger`.

### Scenario 4 — Marking a target node dirty

Given: the alpha-role target for widget is clean with last cleaned timestamp 2026-01-02T03:04:05Z
and change summary "widget uses the new parser"; and the gamma-role target for sprocket is clean
with last cleaned timestamp 2026-01-02T03:04:05Z and does not depend on the alpha-role target for
widget.

1. The caller marks the alpha-role target for widget dirty with the reason "the beta-role contract
   changed".
   Observed: the alpha-role target for widget is dirty, its in-band source metadata carries no last
   cleaned timestamp and records the reason "the beta-role contract changed", and its change summary
   "widget uses the new parser" is unchanged; and the gamma-role target for sprocket is still clean.
   Realized by: dirty marking through `dag_storage`, whose in-band metadata the component's own
   removal of the last cleaned timestamp writes, and target manifest loading through
   `uv_manifest_loader`.

### Scenario 5 — Recording a change message invalidates the non-silent dependents

Given: the beta-role target for sprocket is clean with last cleaned timestamp 2026-01-02T03:04:05Z;
the alpha-role target for widget depends on it non-silently and is clean with the last cleaned
timestamp 2026-01-02T03:04:05Z; and the gamma-role target for gadget depends on it silently and is
clean with the last cleaned timestamp 2026-01-02T03:04:05Z.

1. The caller records the change message "sprocket now emits metric names with a unit suffix" on the
   beta-role target for sprocket.
   Observed: the beta-role target for sprocket carries that change message in its in-band source
   metadata; the alpha-role target for widget is dirty because a non-silent dependency changed after
   2026-01-02T03:04:05Z; and the gamma-role target for gadget is still clean with the last cleaned
   timestamp 2026-01-02T03:04:05Z.
   Realized by: change message recording through `dag_storage`, whose change summary the component's
   own update dynamically invalidates the downstream dependencies with, and execution telemetry
   through `logger`.

### Scenario 6 — Injecting a feedback message and acting on it

Given: the beta-role target for sprocket is clean with last cleaned timestamp 2026-01-02T03:04:05Z,
and the alpha-role target for widget depends on it.

1. The caller injects the feedback message "widget reads sprocket output before it is flushed" into
   the beta-role target for sprocket.
   Observed: the beta-role target for sprocket is dirty and holds that feedback message as unacted
   feedback in its in-band source metadata.
   Realized by: feedback message recording through `dag_storage`, whose unacted feedback the
   component's own feedback routing injects into the blamed dependency node, and execution telemetry
   through `logger`.

2. The caller marks the subgraph rooted at the beta-role target for sprocket clean.
   Observed: the beta-role target for sprocket is clean with no unacted feedback.
   Realized by: subgraph clean marking through `dag_storage`, whose metadata stamping the
   component's own clearing of unacted feedback accompanies.

### Scenario 7 — Injecting an empty feedback message

Given: the beta-role target for sprocket is clean with last cleaned timestamp 2026-01-02T03:04:05Z.

1. The caller injects an empty feedback message into the beta-role target for sprocket.
   Observed: the beta-role target for sprocket is dirty and holds an unacted feedback message.
   Realized by: feedback message recording through `dag_storage`, which records the caller-supplied
   text as unacted feedback without rejecting it, and execution telemetry through `logger`.

### Scenario 8 — A subgraph that is already clean

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are clean
with last cleaned timestamp 2026-01-02T03:04:05Z; and the supplied alpha node cleaner cleans the
dirty nodes that share role alpha.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: cleaning concludes, no node is cleaned, and both nodes keep the last cleaned timestamp
   2026-01-02T03:04:05Z.
   Realized by: topological cleaning through `loop_cleaner` and dirty evaluation through
   `dag_storage`, whose clean statuses the component's own target loading through
   `uv_manifest_loader` supplies.

### Scenario 9 — A dirty dependency is cleaned before the node that depends on it

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are dirty,
the beta-role target for gadget because its in-band source metadata is missing, and the alpha-role
target for widget because the beta-role target for gadget changed at 2026-01-03T04:05:06Z.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked to clean the beta-role target for gadget, which is
   clean afterwards, before it is asked to clean the alpha-role target for widget; then cleaning
   concludes with both nodes clean.
   Realized by: topological cleaning through `loop_cleaner` and clean marking through
   `dag_storage`, with each node cleaned by the node cleaner that shares its role.

### Scenario 10 — A chain of three dirty nodes cleaned in dependency order

Given: the alpha-role target for widget depends on the beta-role target for gadget, which depends on
the gamma-role target for sprocket, and all three nodes are dirty.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
Observed: the supplied node cleaner is asked for the gamma-role target for sprocket, then for the
beta-role target for gadget, then for the alpha-role target for widget; and cleaning concludes with
all three nodes clean. Realized by: topological cleaning through `loop_cleaner` over the dependency
edges the component's own `uv_manifest_loader` loading records, and clean marking through
`dag_storage`.

### Scenario 11 — A dirty node outside the target subgraph is not cleaned

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are dirty;
and the gamma-role target for sprocket is dirty but neither it nor anything it reaches is a
dependency of the alpha-role target for widget.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the beta-role target for gadget and the alpha-role target for widget are clean; the
   gamma-role target for sprocket is still dirty and was never asked of the supplied node cleaner;
   and cleaning concludes.
   Realized by: topological cleaning through `loop_cleaner`, which walks the reachable subgraph the
   component's own `uv_manifest_loader` loading records, and clean marking through `dag_storage`.

### Scenario 12 — A dependency between two roles of the same unit

Given: the alpha-role target for widget depends on the beta-role target for widget, and both are
dirty.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked to clean the beta-role target for widget before the
   alpha-role target for widget, and cleaning concludes with both nodes clean.
   Realized by: topological cleaning through `loop_cleaner` over the role dependency edges the
   component's own `uv_manifest_loader` loading records, and clean marking through `dag_storage`.

### Scenario 13 — Halting when the supplied node cleaner cannot continue

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are dirty;
and the supplied alpha node cleaner communicates that processing cannot continue when it is asked to
clean the beta-role target for gadget.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: cleaning halts immediately; the beta-role target for gadget is still dirty; and the
   alpha-role target for widget was never asked of the supplied node cleaner and is still dirty.
   Realized by: topological cleaning through `loop_cleaner`, whose halt the component's own failing
   build result reports, and dirty evaluation through `dag_storage`.

### Scenario 14 — A dirty node whose dependency an earlier run already cleaned

Given: the alpha-role target for widget depends on the beta-role target for gadget; the beta-role
target for gadget is clean with last cleaned timestamp 2026-01-02T03:04:05Z; and the alpha-role
target for widget is dirty because the beta-role target for gadget changed at 2026-01-03T04:05:06Z.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked only for the alpha-role target for widget, which is
   clean afterwards, and cleaning concludes without asking for the beta-role target for gadget.
   Realized by: topological cleaning through `loop_cleaner` and dirty evaluation through
   `dag_storage`, whose clean statuses the component's own target loading through
   `uv_manifest_loader` supplies.

### Scenario 15 — No dirty node shares the role

Given: no node in graph storage is dirty in role alpha, and the beta-role target for gadget is clean
with last cleaned timestamp 2026-01-02T03:04:05Z.

1. The alpha node cleaner cleans the dirty nodes that share role alpha. Observed: processing
continues, and the beta-role target for gadget still carries the last cleaned timestamp
2026-01-02T03:04:05Z. Realized by: single-node execution through `loop_node_cleaner` over the nodes
the component's own `uv_manifest_loader` loading records, with dirty evaluation through
`dag_storage`.

### Scenario 16 — One dirty node in the role, and a dirty node of another role left alone

Given: the alpha-role target for widget is dirty because its in-band source metadata is missing, the
beta-role target for gadget is dirty, and neither node depends on the other.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, the alpha-role target for widget is clean in graph storage, and
   the beta-role target for gadget is still dirty.
   Realized by: single-node execution through `loop_node_cleaner`, clean marking through
   `dag_storage`, and the component's own topological walk over the reachable subgraph.

### Scenario 17 — Several dirty nodes sharing the role

Given: the alpha-role targets for widget, gadget, and sprocket are dirty, and none of them depends
on another.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, and all three nodes are clean in graph storage.
   Realized by: single-node execution through `loop_node_cleaner`, clean marking through
   `dag_storage`, and the component's own batch over the reachable subgraph.

### Scenario 18 — A failure that another node cleaning addresses

Given: the alpha-role target for widget is dirty, cleaning it fails on the widget source file, and
the beta node cleaning also addresses the alpha-role target for widget.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, and the alpha-role target for widget is still dirty.
   Realized by: single-node execution through `loop_node_cleaner`, whose failure the component's own
   continuation reports alongside execution telemetry through `logger`.

2. The beta node cleaner cleans the dirty nodes it addresses.
   Observed: processing continues, and the alpha-role target for widget is clean in graph storage.
   Realized by: single-node execution through `loop_node_cleaner` under the beta role, and clean
   marking through `dag_storage`.

### Scenario 19 — A failure that no other node cleaning addresses

Given: the alpha-role target for widget is dirty, cleaning it fails on the widget source file, and
no other node cleaning addresses the widget source file.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing cannot continue, and the alpha-role target for widget is still dirty.
   Realized by: single-node execution through `loop_node_cleaner`, whose failure the component's own
   failing build result captures in the pass summary, and dirty evaluation through `dag_storage`.

### Scenario 20 — Consuming one execution event

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event named render_pass with the summary rendered widget in 12 milliseconds and a transcript
representation four lines long.

1. The caller consumes that event.
   Observed: standard output gains one single-line summary naming the event render_pass and
   carrying the text rendered widget in 12 milliseconds, and the transcript log gains a record
   whose text is the full four-line transcript representation of the event.
   Realized by: execution telemetry through `logger`, whose events the component's own passes
   emit.

### Scenario 21 — Two events of the same kind

Given: no events have been consumed yet and no transcript log exists; the caller holds the runner
log events named evaluate with a summary of evaluated gadget and named evaluate with a summary of
evaluated sprocket.

1. The caller consumes the first event.
   Observed: standard output gains one single-line summary naming the event evaluate and carrying
   the text evaluated gadget, and the transcript log gains the transcript representation of the
   first event.
   Realized by: execution telemetry through `logger`, whose events the component's own passes
   emit.

2. The caller consumes the second event. Observed: standard output gains one further single-line
summary naming the event evaluate and carrying the text evaluated sprocket, and the transcript log
gains the transcript representation of the second event as a record distinct from the record of step
1. Realized by: execution telemetry through `logger`, whose transcript records the
component's own passes append.

### Scenario 22 — A long run of events

Given: no events have been consumed yet and no transcript log exists; the caller holds 120 runner
log events whose names are pass_1 through pass_120, each with a distinct transcript
representation.

1. The caller consumes the 120 events, one after another in that order. Observed: standard output
carries 120 single-line summaries in the order the events were consumed, and the transcript log
carries all 120 verbose records in that same order without loss. Realized by: execution telemetry
through `logger`, whose events a long cleaning pass of the component emits.

### Scenario 23 — An event with no summary text

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event named start_up whose summary is absent and whose transcript representation is two lines
long.

1. The caller consumes that event.
   Observed: standard output gains a summary line naming the event start_up, and the transcript
   log gains the full two-line transcript representation of the event.
   Realized by: execution telemetry through `logger`, whose events the component's own pass
   startup emits.

### Scenario 24 — An event with an empty event name and an empty summary

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event whose event name is the empty string, whose summary is the empty string, and whose
transcript representation is the text nothing to report.

1. The caller consumes that event.
   Observed: standard output gains one single-line summary carrying the empty summary text with
   no event name, and the transcript log gains a record whose text is nothing to report.
   Realized by: execution telemetry through `logger`, which the component's own events feed
   without rewriting their names or summaries.

### Scenario 25 — An event whose transcript spans many lines

Given: no events have been consumed yet and no transcript log exists; the caller holds a runner
log event named compile_pass whose summary is compiled widget in 8 seconds and whose transcript
representation is 500 lines long.

1. The caller consumes that event.
   Observed: standard output gains exactly one single-line summary naming the event compile_pass
   and carrying the text compiled widget in 8 seconds, and the transcript log gains one record
   whose text is all 500 lines of the transcript representation.
   Realized by: execution telemetry through `logger`, whose verbose records the component's
   own pass events produce.

### Scenario 26 — Retrieving the manifest of one declared target

Given: role alpha is defined in the workspace directory /ws/alpha_scope_a and declares the widget
unit of the parts package with the source file `parts/widget/widget.md` and the task prompt
`rework the widget source so it reads the sprocket table`, and no target has been loaded from that
definition yet.

1. The caller asks the uv manifest loader for the manifest of the alpha-role target for widget.
   Observed: one target node, the alpha-role target for widget of the workspace at
   /ws/alpha_scope_a, and its manifest carries the task prompt `rework the widget source so it reads
   the sprocket table` and the declared source file `parts/widget/widget.md`.
   Realized by: target manifest loading through `uv_manifest_loader` and graph state storage through
   `dag_storage`.

### Scenario 27 — Resolving declared direct dependencies into graph edges

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and that unit declares direct dependencies on the gadget unit and on the
sprocket unit of the same package.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records exactly two edges, to
   the alpha-role target for gadget and to the alpha-role target for sprocket; the alpha-role target
   for gadget carries a task prompt and an edge to the alpha-role target for sprocket; and the
   alpha-role target for sprocket carries a task prompt and no edge.
   Realized by: target manifest loading through `uv_manifest_loader` and graph state storage through
   `dag_storage`.

### Scenario 28 — A dependency declared neither direct nor propagating

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md` and its direct dependency on the sprocket unit of the same package, and the
widget unit separately marks that sprocket dependency as one the role alpha target does not
propagate.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records the sprocket dependency
   once, marked non-propagating, and the alpha-role target for sprocket carries a task prompt while
   the edge carries no prompt of its own.
   Realized by: target manifest loading through `uv_manifest_loader`, whose non-propagating edges
   the component's own topological execution through `loop_cleaner` reads from `dag_storage`.

### Scenario 29 — A declared dependency with no manifest of its own

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and that unit declares the direct dependency on the gadget unit of the
same package, which no role definition declares.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records the edge to the
   alpha-role target for gadget, and the alpha-role target for gadget is present in graph storage
   with no task prompt and no source file.
   Realized by: target manifest loading through `uv_manifest_loader` and graph state storage through
   `dag_storage`.

### Scenario 30 — A unit whose component type is not active for the role

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, that unit declares the direct dependency on the gadget unit of the same
package, the gadget unit holds the constituent unit widget, and role alpha marks the component type
of the gadget unit as not active.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: one node definition for the alpha-role target for gadget carrying no task prompt, and
   it forwards the dependencies of the gadget unit as edges to the alpha-role targets of its
   constituent units rather than edges to implementations of the gadget unit itself.
   Realized by: target manifest loading through `uv_manifest_loader` and graph state storage through
   `dag_storage`.

### Scenario 31 — A target that declares no dependency at all

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and that unit declares neither a direct dependency nor a dependency the
role alpha target does not propagate.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records no edge, and no other
   node definition is synthesized.
   Realized by: target manifest loading through `uv_manifest_loader` and graph state storage through
   `dag_storage`.

## Implementation-only

### Scenario 32 — Loading workspace targets into graph storage

Given: the workspace directory /ws/alpha_scope_a defines role alpha with the widget unit, the gadget
unit, and the widget unit's declared dependency on the gadget unit, and graph storage holds no node
for either unit.

1. The caller loads the alpha-role target for widget into the loop.
   Observed: graph storage holds the alpha-role target for widget and the alpha-role target for
   gadget with the edge from widget to gadget, and the cleaning pass rooted at the alpha-role target
   for widget visits both nodes.
   Realized by: target manifest loading through `uv_manifest_loader` and graph state storage through
   `dag_storage`, whose node population the component's own pass reads.

### Scenario 33 — A target label the workspace cannot resolve

Given: the workspace directory /ws/alpha_scope_a defines role alpha with the widget unit only, and
graph storage holds no node for the sprocket unit.

1. The caller loads the alpha-role target for sprocket into the loop.
   Observed: the load fails explicitly, naming the sprocket target, and graph storage still holds no
   node for the sprocket unit rather than a synthesized node with an empty task prompt.
   Realized by: target manifest loading through `uv_manifest_loader`, whose failure the component's
   own propagation reports, and graph state storage through `dag_storage`.

### Scenario 34 — Stamping node metadata headers and deleting the last cleaned timestamp

Given: the beta-role target for gadget has no source artifact on disk, declares the starter template
with the initial content "# gadget beta", holds the unacted feedback message "the gadget output
omits the required field", and carries in-band metadata with a missing last changed timestamp and no
change summary; the pass marking the subgraph clean runs at 2026-01-05T06:07:08Z.

1. The caller marks the subgraph rooted at the beta-role target for gadget clean.
   Observed: the source artifact now exists holding "# gadget beta"; the node's metadata header
   carries the last cleaned timestamp 2026-01-05T06:07:08Z, a last changed timestamp initialized to
   2026-01-05T06:07:08Z, the default change summary, and no unacted feedback.
   Realized by: subgraph clean marking and template materialization through `dag_storage`, whose
   metadata header the component's own stamping writes with the current timestamp.

2. The caller deletes the last cleaned timestamp from the node's source file metadata header and
   asks whether the node is dirty.
   Observed: the beta-role target for gadget reports as dirty, although its source artifact exists
   and holds no unacted feedback.
   Realized by: the component's own removal of the last cleaned timestamp from the source file
   metadata header and dirty evaluation through `dag_storage`.

### Scenario 35 — Recording feedback and changes in the run log

Given: the parts directory /ws/alpha_scope_a/parts contains the `.cleanroom.log` file, the beta-role
target for sprocket is clean at 2026-01-02T03:04:05Z, the alpha-role target for widget is clean at
2026-01-02T03:04:05Z and depends on the beta-role target for sprocket.

1. The caller records the change message "sprocket now emits metric names with a unit suffix" on the
beta-role target for sprocket. Observed: the beta-role target for sprocket's change summary becomes
"sprocket now emits metric names with a unit suffix", its last cleaned timestamp is cleared so that
the alpha-role target for widget is dirty, and the `.cleanroom.log` file in /ws/alpha_scope_a/parts
gains the change message. Realized by: change message recording through `dag_storage` and the
component's own appending of the record to the `.cleanroom.log` file in the directory containing the
parts.

2. The caller injects the feedback message "widget reads sprocket output before it is flushed",
blaming the beta-role target for sprocket, from the alpha-role target for widget. Observed: the
beta-role target for sprocket's in-band metadata holds the feedback with the blamed dependency node
and the diagnostic reason, the node reports as dirty, and the `.cleanroom.log` file gains the
feedback entry. Realized by: feedback message recording through `dag_storage` and the component's
own appending of the feedback entry to the `.cleanroom.log` file in the directory containing the
parts.

### Scenario 36 — Telemetry for a pass and its outcome

Given: the alpha-role target for widget depends on the beta-role target for gadget, both are dirty,
and no transcript log exists yet.

1. The caller runs a cleaning pass rooted at the alpha-role target for widget.
   Observed: standard output gains one single-line summary for each execution event of the pass,
   the transcript log gains the verbose record of each event together with the pass duration and the
   successful build outcome, and the pass duration the transcript records covers the cleaning of
   both nodes.
   Realized by: execution telemetry and event streaming through `logger`, whose events the
   component's own topological pass through `loop_cleaner` emits.
