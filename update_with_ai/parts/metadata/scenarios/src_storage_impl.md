<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:17:17Z
CHANGE: Author control src_storage_impl concrete scenarios
CODE_HASH: 3a1d23682463
-->

# Concrete scenarios for `src_storage_impl` (implementation)

Scenarios 1 through 27 restate the caller observations of the interface scenarios of both
`agent_storage` and `dag_storage`, whose contracts this component realizes over one workspace-backed
graph, and add beside each observation the realization that produces it. Restating them rather than
writing fresh ones is what makes realizability structural: an implementation scenario that cannot
name a realization for its observation is a defect in the implementation rather than a gap in the
set. Scenarios 28 through 31 cover behaviours the interface does not expose to a caller, and each of
them is a candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Reused from `agent_storage`

### Scenario 1 — A manifest declaring no targets

Given: the workspace target manifest holds the JSON text `{}`, and it declares no target.

1. The caller asks the agent storage for the declared nodes.
   Observed: nothing is returned, and no node definition is provided.
   Realized by: the component's own manifest ingestion, which populates no entry in the in-memory
   graph index and no node definition for an empty declaration.

2. The caller asks for the dependencies of the widget target.
   Observed: the query fails explicitly, because the manifest declares no widget target.
   Realized by: the component's own lookup in the in-memory graph index, which holds no relation for
   a node the manifest never declared, and its own propagation of that failure.

### Scenario 2 — One declared target

Given: the workspace target manifest declares the target `//widget`, whose task prompt is
`clean the widget source`, and declares no dependency.

1. The caller asks for the nodes the manifest declares.
   Observed: exactly one node, addressing the unit widget under the role named by `//widget`.
   Realized by: the component's own manifest ingestion, which records the declared target address in
   the in-memory graph index, binding the unit widget to the role the address names.

2. The caller asks for the task prompt of the widget target.
   Observed: `clean the widget source`.
   Realized by: the component's own node definition, which the manifest ingestion writes with the
   declared task prompt.

3. The caller asks for the node definition of the widget target.
   Observed: a definition identifying the widget target, carrying `clean the widget source`, and
   reporting no dependencies.
   Realized by: the component's own node definition, whose forward dependency set the manifest
   ingestion left empty.

### Scenario 3 — A manifest declaring a dependency structure

Given: the workspace target manifest declares `//widget` whose task prompt is
`clean the widget source` with a dependency on `//gadget`, `//gadget` whose task prompt is
`refresh the gadget index` with a dependency on `//sprocket`, and `//sprocket` whose task prompt is
`verify the sprocket table` with no dependency; `//sprocket` is declared silent under `//widget`.

1. The caller asks for the node definitions of the widget, gadget, and sprocket targets.
   Observed: three definitions, mapping those task prompts to those targets, and no others.
   Realized by: the component's own manifest ingestion, which records one node definition per
   declared target in the in-memory graph index and no more than the manifest declares.

2. The caller asks for the dependencies of the widget target.
   Observed: the gadget and sprocket targets, of which the sprocket target is silent and the gadget
   target is not.
   Realized by: the component's own forward dependency relations and silent dependency filter, which
   the manifest ingestion writes from the declared dependency structure.

3. The caller asks for the dependencies of the gadget target.
   Observed: the sprocket target, declared there as a non-silent dependency.
   Realized by: the same forward dependency relations, read from the in-memory graph index per
   target rather than from the manifest text.

### Scenario 4 — The dirty state of a node over time

Given: the workspace target manifest declares `//widget`, whose task prompt is
`clean the widget source` with a dependency on the non-silent `//gadget`, the widget source
artifact is not present on disk, and the gadget source artifact carries in-band metadata whose clean
timestamp is `2026-02-03T04:05:06Z`.

1. The caller asks whether the widget node is dirty.
   Observed: dirty, because its source artifact is missing on disk.
   Realized by: the component's own resolution of the widget node's declared source file against the
   workspace root, whose absence the component reports as the missing source artifact, and its own
   synthesis of the change message to implement the source file.

2. The widget source artifact is materialized and carries in-band metadata whose clean timestamp is
   `2026-02-05T06:07:08Z`, and the caller asks whether the widget node is dirty.
   Observed: not dirty, because its in-band metadata is present, names a clean timestamp, and names
   no dependency cleaned after `2026-02-05T06:07:08Z`.
   Realized by: in-band source metadata extraction through `src_metadata` over the widget node's
   source file, and the component's own dynamic forward dirty evaluation, which compares the
   non-silent gadget dependency's last changed timestamp against the widget node's clean timestamp.

3. The caller brings the gadget node clean at `2026-02-06T07:08:09Z` and then asks whether the
   widget node is dirty.
   Observed: dirty, because its non-silent gadget dependency was cleaned after the widget node was
   last cleaned.
   Realized by: the component's own forward dirty evaluation, reading the gadget node's in-band
   metadata through `src_metadata` and finding a last changed timestamp strictly newer than the
   widget node's clean timestamp.

4. The caller brings the widget node clean at `2026-02-07T08:09:10Z` and asks whether it is dirty.
   Observed: not dirty, because the widget node's clean timestamp is later than the gadget node's.
   Realized by: the component's own clean marking, which writes the clean timestamp into the widget
   node's in-band metadata through `src_metadata`, and the same forward dirty evaluation, which now
   finds no newer non-silent dependency.

### Scenario 5 — A manifest declaring a self-dependency

Given: the workspace target manifest declares the target `//widget`, whose task prompt is
`clean the widget source` with a dependency on `//widget`.

1. The caller asks for the nodes the manifest declares.
   Observed: exactly one node, for the widget target.
   Realized by: the component's own manifest ingestion, which records one node definition in the
   in-memory graph index although the declared dependency names the same target.

2. The caller asks for the dependencies of the widget target.
   Observed: the widget target itself, reported as the dependency the manifest declares, and not
   rejected as a self-dependency.
   Realized by: the component's own forward dependency relations, which record the declared relation
   verbatim without rejecting the self-reference.

### Scenario 6 — A manifest declaring a cycle and a disconnected target

Given: the workspace target manifest declares `//widget` whose task prompt is
`clean the widget source` with a dependency on `//gadget`, `//gadget` whose task prompt is
`refresh the gadget index` with a dependency on `//widget`, and `//sprocket` whose task prompt is
`verify the sprocket table` with no dependency.

1. The caller asks for the dependency structure the manifest declares.
   Observed: three nodes, with the widget target depending on the gadget target and the gadget
   target depending on the widget target, and the sprocket target is reachable from the widget
   target through no chain of declared dependencies.
   Realized by: the component's own manifest ingestion into the in-memory graph index, which records
   all three node definitions and both directed relations without rejecting the cycle.

2. The caller asks for the dependencies of the widget target.
   Observed: the gadget target only, reported exactly as the manifest declares it, and not rejected
   because the gadget target depends on the widget target in turn.
   Realized by: the component's own forward dependency relations, read per target from the in-memory
   graph index without walking the relation further.

### Scenario 7 — A manifest that is missing, empty, or malformed

Given: no file named `parts/widget/targets.json` exists in the workspace.

1. The caller asks the agent storage for the nodes declared by `parts/widget/targets.json`.
   Observed: the request fails explicitly, naming `parts/widget/targets.json`, and no node or task
   prompt is provided.
   Realized by: the component's own manifest ingestion, which resolves the manifest location through
   `file_paths` and fails explicitly when the file is absent, naming the offending path.

2. The file `parts/widget/targets.json` is created holding zero bytes, and the caller asks again.
   Observed: the request fails explicitly rather than reporting a manifest that declares no target.
   Realized by: the component's own manifest ingestion, which distinguishes an empty file from a
   manifest that declares no target and fails explicitly on the empty text.

3. The file `parts/widget/targets.json` is rewritten to hold the JSON text
   `"//widget": {"prompt": "clean the widget source"`, which is missing its opening brace, and the
   caller asks again.
   Observed: the request fails explicitly, naming the malformed manifest text, and no node
   definition is provided.
   Realized by: the component's own manifest ingestion, which fails explicitly on text it cannot
   parse and names the offending manifest text in the failure.

### Reused from `dag_storage`

### Scenario 8 — Reading a node's dependencies across the silent partition

Given: the alpha-role node for sprocket depends on the beta-role node for widget and on the beta-role
node for gadget; the beta-role node for widget is silent and the beta-role node for gadget is not
silent; the alpha-role node for widget declares no dependencies.

1. The caller reads the dependencies of the alpha-role node for sprocket.
   Observed: two dependencies, the beta-role node for widget reported silent and the beta-role node
   for gadget reported not silent.
   Realized by: the component's own in-memory graph index, which stores each forward dependency
   relation alongside the silent dependency declaration read from the workspace target manifest.

2. The caller reads the dependencies of the alpha-role node for widget.
   Observed: an empty dependency sequence.
   Realized by: the component's own in-memory graph index, which holds no forward dependency
   relation for a node the manifest declares without dependencies.

### Scenario 9 — Reading a node's messages and marking the node clean

Given: the beta-role node for gadget was marked dirty with the reason "the upstream contract
changed", its source artifact exists on disk, and it holds the unacted feedback message "the
beta-role output omits the required field".

1. The caller reads the messages recorded for the beta-role node for gadget.
   Observed: one message, the text "the beta-role output omits the required field" recorded as
   unacted feedback.
   Realized by: in-band source metadata extraction through `src_metadata` over the node's declared
   source file, and the component's own synthesis of the message from the unacted feedback entry.

2. The caller marks the beta-role node for gadget clean.
   Observed: the messages recorded for the node are cleared, its in-band metadata carries a clean
   timestamp, and the node's unacted feedback and dirty tag are cleared, so the node reports as not
   dirty.
   Realized by: the component's own clean marking, which clears the node's synthesized messages and
   rewrites the in-band metadata header of the node's source file through `src_metadata` with the
   clean timestamp, clearing the unacted feedback, the dirty tag and the dirty reason.

### Scenario 10 — Marking a node clean with a change message

Given: the alpha-role node for widget's source artifact exists on disk, the node is dirty, and the
caller supplies the change message "the beta-role contract for gadget gained a required field".

1. The caller marks the alpha-role node for widget clean with that change message.
   Observed: the node's in-band metadata carries a clean timestamp, the change summary "the
   beta-role contract for gadget gained a required field" and a change timestamp, and the node
   reports as not dirty.
   Realized by: the component's own clean marking, which selects the source file resolved through
   `file_paths` and writes the clean timestamp, the change summary and the change timestamp into its
   in-band metadata header through `src_metadata`, and its own read of that metadata through
   `src_metadata` for the subsequent dirty report.

### Scenario 11 — Marking a node clean whose source artifact is missing

Given: the gamma-role node for sprocket's source artifact is missing on disk, the node holds the
unacted feedback message "the sprocket gamma-role output is stale", and the node is dirty.

1. The caller marks the gamma-role node for sprocket clean.
   Observed: the messages recorded for the node are cleared, but no clean timestamp is written to
   its in-band metadata because its source artifact does not exist, so the node still reports as
   dirty.
   Realized by: the component's own resolution of the node's declared source file against the
   workspace root through `file_paths`, which finds no artifact to update, so the component clears
   only its own synthesized messages and leaves the in-band metadata alone.

2. The caller marks the gamma-role node for sprocket clean with the change message "the beta-role
   contract for gadget gained a required field".
   Observed: neither a clean timestamp nor the change summary "the beta-role contract for gadget
   gained a required field" is written to the node's in-band metadata, and the node still reports
   as dirty.
   Realized by: the same absence of a source artifact, which stops the component before any in-band
   metadata header rewrite through `src_metadata` and leaves the node's missing-source dirtiness in
   place.

### Scenario 12 — Reporting dirtiness across its causes

Given: the beta-role node for widget is clean; the alpha-role node for gadget's source artifact is
missing on disk; the alpha-role node for sprocket carries in-band metadata that is invalid; the
alpha-role node for widget was marked dirty with the reason "the upstream contract changed"; the
delta-role node for widget's source artifact exists on disk with no in-band metadata at all.

1. The caller asks whether the beta-role node for widget is dirty.
   Observed: not dirty.
   Realized by: in-band source metadata extraction through `src_metadata` over the node's source
   file, which supplies a clean timestamp, with no unacted feedback, dirty tag or newer non-silent
   forward dependency for the component's own dirty evaluation to report.

2. The caller asks whether the alpha-role node for gadget is dirty.
   Observed: dirty, because its source artifact is missing on disk.
   Realized by: the component's own resolution of the node's declared source file against the
   workspace root through `file_paths`, which finds no artifact, and its own synthesis of the change
   message to implement the source file.

3. The caller asks whether the alpha-role node for sprocket is dirty.
   Observed: dirty, because its in-band metadata is invalid.
   Realized by: in-band source metadata extraction through `src_metadata`, whose parse of the node's
   source file fails, and the component's own dirty evaluation of unparseable metadata.

4. The caller asks whether the alpha-role node for widget is dirty.
   Observed: dirty, because it carries a dirty tag.
   Realized by: in-band source metadata extraction through `src_metadata`, which reports the dirty
   tag that the component's own dirty marking wrote, and the component's own dirty evaluation of
   that tag.

5. The caller asks whether the delta-role node for widget is dirty.
   Observed: dirty, because its in-band metadata is missing.
   Realized by: in-band source metadata extraction through `src_metadata`, which finds no metadata
   comment block in the node's source file, and the component's own dirty evaluation of missing
   metadata.

### Scenario 13 — Reporting dirtiness from dependency changes

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
   Realized by: the component's own dynamic forward dirty evaluation, which reads the non-silent
   gadget dependency's last changed timestamp through `src_metadata` and finds it strictly newer
   than the widget node's clean timestamp, synthesizing a change message describing the dependency
   update.

2. The caller asks whether the alpha-role node for sprocket is dirty.
   Observed: not dirty, because its dependency is silent and precludes change message propagation.
   Realized by: the component's own silent dependency filter, which excludes the silent gadget
   dependency from the forward dirty evaluation although its last changed timestamp is newer than
   the sprocket node's clean timestamp.

3. The caller asks whether the alpha-role node for gadget is dirty.
   Observed: not dirty, because its non-silent dependency was changed before the node was last
   cleaned.
   Realized by: the same forward dirty evaluation, which compares the widget dependency's last
   changed timestamp of 2026-01-02T06:00:00Z against the gadget node's clean timestamp of
   2026-01-02T07:00:00Z and finds it older.

### Scenario 14 — Adding a feedback message that blames a dependency target

Given: the alpha-role node for sprocket depends non-silently on the beta-role node for widget; the
beta-role node for widget is clean and holds no messages.

1. The caller adds the feedback message "the widget beta-role output omits the required field",
   blaming the beta-role node for widget.
   Observed: that text is recorded as unacted feedback in the beta-role node for widget's in-band
   metadata, the messages recorded for that node now hold it, and the node reports as dirty.
   Realized by: the component's own recording of the feedback against the blamed dependency target
   node, which appends an unacted feedback entry carrying the current timestamp, the blaming node
   address and the explanation to that node's in-band metadata header in place through
   `src_metadata`, and its own read of that entry through `src_metadata` for the dirty report.

### Scenario 15 — Materializing a template for a node whose source artifact is missing

Given: the beta-role node for gadget's source artifact is missing on disk, and the initial content
of the beta-role template is "# gadget beta: describe the beta-role work here".

1. The caller materializes the template for the beta-role node for gadget.
   Observed: the node's source artifact now exists on disk holding "# gadget beta: describe the
   beta-role work here".
   Realized by: the component's own template materialization, which resolves the declared source
   file against the workspace root through `file_paths` and writes the manifest's configured
   template content to that location.

### Scenario 16 — Preserving an existing source artifact when materializing a template

Given: the alpha-role node for widget's source artifact exists on disk holding "# widget alpha:
edited by the caller", and the initial content of the alpha-role template is "# widget alpha:
describe the alpha-role work here".

1. The caller materializes the template for the alpha-role node for widget.
   Observed: the source artifact is preserved and still holds "# widget alpha: edited by the
   caller", rather than the template's initial content.
   Realized by: the component's own template materialization, which writes only when the source file
   it resolved through `file_paths` is absent, so the existing artifact is left untouched.

### Scenario 17 — Marking a node dirty with a reason

Given: the beta-role node for widget was marked clean at 2026-01-02T03:04:05Z, and the caller
supplies the reason "the upstream contract changed".

1. The caller marks the beta-role node for widget dirty with that reason.
   Observed: the node's clean status is removed, the reason "the upstream contract changed" is
   recorded in its in-band metadata, and the node reports as dirty.
   Realized by: the component's own dirty marking, which deletes the clean timestamp, sets the dirty
   tag and records the supplied reason in the in-band metadata header of the node's source file
   through `src_metadata`, without modifying the recorded change summary or last changed timestamp.

### Scenario 18 — Marking a subgraph clean over a chain of dependencies

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
   Realized by: the component's own subgraph clean marking, which walks the reachable dependency
   closure of the target node in its in-memory graph index, materializes each missing source file
   from the manifest's template content, and marks each node of the closure clean through
   `src_metadata`, touching no node outside the closure.

### Scenario 19 — Marking a subgraph clean at a node that depends on itself

Given: the alpha-role node for widget declares itself as one of its own dag dependencies and is
dirty; the alpha-role node for gadget is dirty and lies on no path from the alpha-role node for
widget.

1. The caller marks the subgraph clean at the alpha-role node for widget.
   Observed: the alpha-role node for widget is marked clean, the reachable subgraph being that node
   alone, and the alpha-role node for gadget is still dirty.
   Realized by: the component's own subgraph clean marking, whose reachable dependency closure walk
   terminates on the self-reference and marks the node clean, so no node outside the closure is
   touched.

### Scenario 20 — Marking a subgraph clean across a cycle of dependencies

Given: the alpha-role node for widget depends on the beta-role node for widget and the beta-role
node for widget depends on the alpha-role node for widget; both nodes are dirty; the alpha-role node
for gadget is dirty and lies on no path from either node.

1. The caller marks the subgraph clean at the alpha-role node for widget.
   Observed: both the alpha-role node for widget and the beta-role node for widget are marked clean,
   each being reachable from the other, and the alpha-role node for gadget is still dirty.
   Realized by: the component's own subgraph clean marking, whose reachable dependency closure walk
   visits each node once and marks both nodes of the cycle clean, leaving the alpha-role node for
   gadget outside the closure.

### Reused from `file_paths`

### Scenario 21 — An absolute path for a file at the filesystem root

Given: the caller holds no path representation for the file /repo/alpha/widget.py.

1. The caller asks for the absolute path of the string /repo/alpha/widget.py.
   Observed: an absolute path record naming /repo/alpha/widget.py from the filesystem root.
   Realized by: the component's own resolution of declared source files through `file_paths`, whose
   creation of an absolute path validates the supplied path string against that path kind.

### Scenario 22 — A workspace path naming a location inside a workspace

Given: the caller holds no path representation for alpha/scope_a/widget.py.

1. The caller asks for the workspace path of the string alpha/scope_a/widget.py.
   Observed: a workspace path record naming alpha/scope_a/widget.py relative to a workspace root,
   with no leading separator.
   Realized by: the component's own resolution of declared source files through `file_paths`, whose
   creation of a workspace path requires the string to be relative to the workspace root without a
   leading separator.

### Scenario 23 — Telling an absolute path apart from its workspace twin

Given: the caller holds no path representation for either /repo/alpha/widget.py or
alpha/widget.py.

1. The caller asks for the absolute path of the string /repo/alpha/widget.py.
   Observed: an absolute path whose leading separator makes it a location from the filesystem
   root.
   Realized by: the component's own resolution of declared source files through `file_paths`, which
   keeps the absolute path distinct from the workspace path of the same name.

2. The caller asks for the workspace path of the string alpha/widget.py.
   Observed: a workspace path that is a different kind of location from the absolute path of step
   1, with no leading separator.
   Realized by: the component's own resolution of declared source files through `file_paths`, whose
   workspace path creation keeps no leading separator and names a location inside the workspace
   root.

### Scenario 24 — A workspace path asked for as an absolute path

Given: the caller holds no path representation for alpha/widget.py.

1. The caller asks for the absolute path of the string alpha/widget.py.
   Observed: the request is refused, because the string names a location relative to the current
   working directory rather than a location from the filesystem root.
   Realized by: the component's own resolution of declared source files through `file_paths`, whose
   validation refuses the string before the component inspects any artifact.

### Scenario 25 — An absolute path asked for as a workspace path

Given: the caller holds no path representation for /repo/alpha/widget.py.

1. The caller asks for the workspace path of the string /repo/alpha/widget.py.
   Observed: the request is refused, because the string names a location from the filesystem root
   rather than a location within a workspace.
   Realized by: the component's own resolution of declared source files through `file_paths`, whose
   validation refuses the leading separator before the component inspects any artifact.

### Scenario 26 — Resolving a workspace path against a workspace root

Given: the caller holds the absolute path of the workspace root /repo/alpha_scope_a and the
workspace path scope_a/widget.py.

1. The caller resolves the workspace path scope_a/widget.py against the absolute root path
   /repo/alpha_scope_a.
   Observed: the absolute path /repo/alpha_scope_a/scope_a/widget.py, being the workspace root
   path joined with the workspace path.
   Realized by: the component's own resolution of declared source files through `file_paths`, whose
   resolution of a workspace path against the workspace root yields the absolute location the
   component then reads and writes for in-band metadata mutation.

### Scenario 27 — Resolving against a root that is not absolute

Given: the caller holds the workspace path scope_a/widget.py and a relative string
alpha_scope_a held in place of an absolute workspace root.

1. The caller resolves the workspace path scope_a/widget.py against the relative string
   alpha_scope_a.
   Observed: the resolution is refused, because the supplied root does not name a location from
   the filesystem root.
   Realized by: the component's own resolution of declared source files through `file_paths`, whose
   validation refuses a supplied root that is not an absolute path.

## Implementation-only

### Scenario 28 — Marking an auditor node dirty and clean through its verified feedback targets

Given: the epsilon-role node for widget is an auditor node whose verified feedback targets are the
alpha-role node for widget, whose source file carries the epsilon-role audit timestamp
2026-01-02T03:04:05Z, and the beta-role node for widget, whose source file carries no audit
timestamp for role epsilon.

1. The caller asks whether the epsilon-role node for widget is dirty.
   Observed: dirty, because a verified feedback target file lacks the audit timestamp for the
   auditor node.
   Realized by: in-band source metadata extraction through `src_metadata` over each verified
   feedback target file, and the component's own auditor dirty evaluation, which compares the audit
   timestamp for the auditor node against each target's last changed timestamp.

2. The epsilon-role audit timestamp 2026-01-06T00:00:00Z is stamped on the beta-role node for
   widget, and the caller asks whether the epsilon-role node for widget is dirty.
   Observed: not dirty, because every verified feedback target file carries an audit timestamp for
   the auditor node that is no older than its last changed timestamp.
   Realized by: the same auditor dirty evaluation, which now finds an audit timestamp for role
   epsilon on both verified feedback target files.

3. The caller marks the epsilon-role node for widget clean at 2026-01-07T00:00:00Z.
   Observed: both verified feedback target files carry the audit timestamp 2026-01-07T00:00:00Z for
   role epsilon, and neither target file records a changed last changed timestamp.
   Realized by: the component's own auditor clean marking, which stamps the current timestamp as the
   role epsilon audit timestamp in each verified feedback target file's in-band metadata header
   through `src_metadata` without modifying the target file last changed timestamp.

4. The caller marks the epsilon-role node for widget dirty.
   Observed: neither verified feedback target file carries an audit timestamp for role epsilon any
   more.
   Realized by: the component's own auditor dirty marking, which removes the role epsilon audit
   timestamp from each verified feedback target file's in-band metadata header through
   `src_metadata`.

### Scenario 29 — An auditor node that declares no verified feedback target

Given: the epsilon-role node for widget is an auditor node that declares no configured verified
feedback target, and it declares the non-silent forward dependency alpha-role node for gadget, whose
source file carries in-band metadata whose last changed timestamp is 2026-01-05T00:00:00Z.

1. The caller asks whether the epsilon-role node for widget is dirty.
   Observed: dirty, and the resolved change state is that of the alpha-role node for gadget.
   Realized by: the component's own auditor dirty evaluation, which falls back to the non-silent
   forward dependencies when the auditor node configures no verified feedback target, and reads the
   gadget node's dirtiness through the component's own dirty evaluation of that node.

2. The caller asks for the verified feedback dependencies of the epsilon-role node for widget.
   Observed: the request fails explicitly, because no feedback dependency is configured for the
   auditor node.
   Realized by: the component's own fail-fast check over the configured verified feedback targets of
   an auditor node, which refuses the query rather than reporting an empty relation.

### Scenario 30 — Materializing a template through the configured role template command

Given: the alpha-role node for widget's source artifact is missing on disk, and the node configures
the role template command `materialize-widget --scope scope_a` instead of template content.

1. The caller materializes the template for the alpha-role node for widget.
   Observed: the node's source artifact now exists on disk holding the content the configured
   command produced.
   Realized by: the component's own template materialization, which executes the configured role
   template command when the node configures no template content and writes the command's output to
   the declared source file it resolved through `file_paths`.

### Scenario 31 — A silent forward dependency that changed after the node was cleaned

Given: the alpha-role node for widget was marked clean at 2026-01-02T03:04:05Z; it declares the
silent forward dependency beta-role node for gadget and the non-silent forward dependency beta-role
node for sprocket; the gadget node was marked clean at 2026-01-02T05:00:00Z and the sprocket node
was marked clean at 2026-01-02T03:00:00Z.

1. The caller asks whether the alpha-role node for widget is dirty.
   Observed: not dirty, because the newer change belongs to a silent forward dependency, so it
   produces no change message.
   Realized by: the component's own silent dependency filter over the forward dirty evaluation,
   which skips the gadget dependency whose last changed timestamp is newer than the node's clean
   timestamp.

2. The caller marks the sprocket node clean at 2026-01-02T06:00:00Z and asks whether the alpha-role
   node for widget is dirty again.
   Observed: dirty, because its non-silent beta-role sprocket dependency changed after it was last
   cleaned.
   Realized by: the same forward dirty evaluation, which now finds the non-silent sprocket
   dependency's last changed timestamp strictly newer than the node's clean timestamp, and
   synthesizes the change message describing the dependency update.
