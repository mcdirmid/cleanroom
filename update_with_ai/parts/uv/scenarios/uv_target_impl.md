<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T03:20:04Z
CHANGE: Author uv uv_target_impl concrete scenarios
CODE_HASH: 773dff92540d
-->

# Concrete scenarios for `uv_target_impl` (implementation)

Scenarios 1 through 26 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 27 through
31 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

The scenarios of the `uv_target` interface the component implements come first, then the scenarios
of the interface specifications of its imports closure: `file_paths` and `dag_storage`.

### Scenario 1 — Normalizing a package-qualified target label

Given: the workspace root `/repo/alpha_scope_a` holds the package `parts` and the unit widget, and
the caller holds no canonical node for either.

1. The caller normalizes the raw target label `//parts:widget`, which names the widget unit of the
   parts package.
   Observed: a canonical node addressing the unit widget in the role alpha of the workspace at
   `/repo/alpha_scope_a`.
   Realized by: label syntax normalization and package resolution rules through
   `uv_target_labels_ext`, graph node referencing through `dag_storage`, and workspace path
   representation through `file_paths`.

### Scenario 2 — Two spellings of one target label

Given: the caller holds no canonical node for the widget unit of the parts package.

1. The caller normalizes the raw target labels `//parts:widget` and `parts:widget`, both naming the
   widget unit of the parts package.
   Observed: one canonical node, identical for both spellings, because the repository qualifier the
   second spelling omits carries no package or unit information.
   Realized by: label syntax normalization through `uv_target_labels_ext`, whose canonical
   package-and-unit coordinates strip the leading repository qualifier before graph node referencing
   through `dag_storage`.

### Scenario 3 — An omitted target name

Given: the caller holds no canonical node for the unit widget of the workspace root package and no
canonical node for the unit sprocket of the parts package.

1. The caller normalizes the raw target labels `//:widget` and `//parts:sprocket`.
   Observed: a canonical node addressing the unit widget of the workspace root package and a
   canonical node addressing the unit sprocket of the parts package, which are two different nodes.
   Realized by: label syntax normalization through `uv_target_labels_ext`, whose expansion of an
   omitted target name supplies the unit name a label leaves implicit, and graph node referencing
   through `dag_storage`.

### Scenario 4 — Extracting the node directory of a canonical node

Given: the caller holds the canonical node addressing the widget unit of the parts package and the
canonical node addressing the gadget unit of the parts package.

1. The caller asks for the node directory of the widget node.
   Observed: the workspace path `parts/widget`, the package directory the workspace root
   `/repo/alpha_scope_a` contains the widget unit in.
   Realized by: package filesystem directory resolution through `uv_target_labels_ext` and workspace
   path representation through `file_paths`.

2. The caller asks for the node directory of the gadget node. Observed: the workspace path
`parts/gadget`, a different package directory from the one of step 1. Realized by: package
filesystem directory resolution through `uv_target_labels_ext` over the gadget unit's canonical
coordinates.

### Scenario 5 — A target label that is malformed

Given: the workspace root `/repo/alpha_scope_a` holds the package `parts`, and the caller holds no
canonical node.

1. The caller normalizes the raw target label `//parts:widget gadget`, whose unit name holds a space
character. Observed: the normalization fails explicitly, naming the malformed label, and no
canonical node is returned. Realized by: target syntax validation through `uv_target_labels_ext`,
whose character set rules reject the label, and the component's own propagation of that rejection.

2. The caller normalizes the empty raw target label.
   Observed: the normalization fails explicitly, and no canonical node is returned.
   Realized by: target syntax validation through `uv_target_labels_ext`, which rejects an empty
   label, and the component's own propagation of that rejection.

### Scenario 6 — A node whose package directory the workspace does not contain

Given: the workspace root `/repo/alpha_scope_a` holds no package directory for the unit sprocket,
and the caller holds no canonical node for it.

1. The caller normalizes the raw target label `//parts:sprocket`.
   Observed: a canonical node addressing the unit sprocket in the parts package.
   Realized by: label syntax normalization through `uv_target_labels_ext` and graph node referencing
   through `dag_storage`, neither of which consults disk contents.

2. The caller asks for the node directory of that canonical node.
   Observed: the request fails explicitly, naming the package directory `parts/sprocket` that the
   workspace root `/repo/alpha_scope_a` does not contain, rather than reporting a directory that
   holds no unit.
   Realized by: package filesystem directory resolution through `uv_target_labels_ext` against the
   workspace root represented through `file_paths`, and the component's own refusal, which names the
   package directory.

### Scenario 7 — An absolute path for a file at the filesystem root

Given: the caller holds no path representation for the file /repo/alpha/widget.py.

1. The caller asks for the absolute path of the string /repo/alpha/widget.py.
   Observed: an absolute path record naming /repo/alpha/widget.py from the filesystem root.
   Realized by: workspace path representation through `file_paths` for the file path a normalized
   target label contributes, whose absolute path record names the location from the filesystem
   root.

### Scenario 8 — A workspace path naming a location inside a workspace

Given: the caller holds no path representation for alpha/scope_a/widget.py.

1. The caller asks for the workspace path of the string alpha/scope_a/widget.py.
   Observed: a workspace path record naming alpha/scope_a/widget.py relative to a workspace root,
   with no leading separator.
   Realized by: workspace path representation through `file_paths` for the path string a normalized
   target label contributes.

### Scenario 9 — Telling an absolute path apart from its workspace twin

Given: the caller holds no path representation for either /repo/alpha/widget.py or
alpha/widget.py.

1. The caller asks for the absolute path of the string /repo/alpha/widget.py.
   Observed: an absolute path whose leading separator makes it a location from the filesystem
   root.
   Realized by: workspace path representation through `file_paths`, whose absolute kind requires the
   leading separator.

2. The caller asks for the workspace path of the string alpha/widget.py.
   Observed: a workspace path that is a different kind of location from the absolute path of step
   1, with no leading separator.
   Realized by: workspace path representation through `file_paths`, whose workspace kind rejects a
   leading separator.

### Scenario 10 — A workspace path asked for as an absolute path

Given: the caller holds no path representation for alpha/widget.py.

1. The caller asks for the absolute path of the string alpha/widget.py.
   Observed: the request is refused, because the string names a location relative to the current
   working directory rather than a location from the filesystem root.
   Realized by: workspace path representation through `file_paths`, which validates a supplied path
   string against the path kind being created, and the component's own propagation of that refusal.

### Scenario 11 — An absolute path asked for as a workspace path

Given: the caller holds no path representation for /repo/alpha/widget.py.

1. The caller asks for the workspace path of the string /repo/alpha/widget.py.
   Observed: the request is refused, because the string names a location from the filesystem root
   rather than a location within a workspace.
   Realized by: workspace path representation through `file_paths`, whose workspace kind requires a
   host relative location without a leading separator.

### Scenario 12 — Resolving a workspace path against a workspace root

Given: the caller holds the absolute path of the workspace root /repo/alpha_scope_a and the
workspace path scope_a/widget.py.

1. The caller resolves the workspace path scope_a/widget.py against the absolute root path
   /repo/alpha_scope_a.
   Observed: the absolute path /repo/alpha_scope_a/scope_a/widget.py, being the workspace root
   path joined with the workspace path.
   Realized by: workspace path representation through `file_paths`, which resolves a workspace path
   into an absolute path given the absolute path of a workspace root.

### Scenario 13 — Resolving against a root that is not absolute

Given: the caller holds the workspace path scope_a/widget.py and a relative string
alpha_scope_a held in place of an absolute workspace root.

1. The caller resolves the workspace path scope_a/widget.py against the relative string
   alpha_scope_a.
   Observed: the resolution is refused, because the supplied root does not name a location from
   the filesystem root.
   Realized by: workspace path representation through `file_paths`, which requires the root to name
   a host absolute location, and the component's own propagation of that refusal.

### Scenario 14 — Reading a node's dependencies across the silent partition

Given: the alpha-role node for sprocket depends on the beta-role node for widget and on the
beta-role node for gadget; the beta-role node for widget is silent and the beta-role node for gadget
is not silent; the alpha-role node for widget declares no dependencies.

1. The caller reads the dependencies of the alpha-role node for sprocket.
   Observed: two dependencies, the beta-role node for widget reported silent and the beta-role node
   for gadget reported not silent.
   Realized by: dag dependency access through `dag_storage`, whose node identity the component's own
   canonical node coordinates address.

2. The caller reads the dependencies of the alpha-role node for widget.
   Observed: an empty dependency sequence.
   Realized by: dag dependency access through `dag_storage`, whose node identity the component's own
   canonical node coordinates address.

### Scenario 15 — Reading a node's messages and marking the node clean

Given: the beta-role node for gadget was marked dirty with the reason "the upstream contract
changed", its source artifact exists on disk, and it holds the unacted feedback message "the
beta-role output omits the required field".

1. The caller reads the messages recorded for the beta-role node for gadget.
   Observed: one message, the text "the beta-role output omits the required field" recorded as
   unacted feedback.
   Realized by: dag dependency access through `dag_storage`, whose node identity the component's own
   canonical node coordinates address.

2. The caller marks the beta-role node for gadget clean.
   Observed: the messages recorded for the node are cleared, its in-band metadata carries a clean
   timestamp, and the node's unacted feedback and dirty tag are cleared, so the node reports as not
   dirty.
   Realized by: graph node referencing and clean marking through `dag_storage`, whose node identity
   the component's own canonical node coordinates address.

### Scenario 16 — Marking a node clean with a change message

Given: the alpha-role node for widget's source artifact exists on disk, the node is dirty, and the
caller supplies the change message "the beta-role contract for gadget gained a required field".

1. The caller marks the alpha-role node for widget clean with that change message.
   Observed: the node's in-band metadata carries a clean timestamp, the change summary "the
   beta-role contract for gadget gained a required field" and a change timestamp, and the node
   reports as not dirty.
   Realized by: graph node referencing and clean marking through `dag_storage`, whose node identity
   the component's own canonical node coordinates address.

### Scenario 17 — Marking a node clean whose source artifact is missing

Given: the gamma-role node for sprocket's source artifact is missing on disk, the node holds the
unacted feedback message "the sprocket gamma-role output is stale", and the node is dirty.

1. The caller marks the gamma-role node for sprocket clean.
   Observed: the messages recorded for the node are cleared, but no clean timestamp is written to
   its in-band metadata because its source artifact does not exist, so the node still reports as
   dirty.
   Realized by: graph node referencing and clean marking through `dag_storage`, whose node identity
   the component's own canonical node coordinates address.

2. The caller marks the gamma-role node for sprocket clean with the change message "the beta-role
   contract for gadget gained a required field".
   Observed: neither a clean timestamp nor the change summary "the beta-role contract for gadget
   gained a required field" is written to the node's in-band metadata, and the node still reports
   as dirty.
   Realized by: graph node referencing and clean marking through `dag_storage`, whose node identity
   the component's own canonical node coordinates address.

### Scenario 18 — Reporting dirtiness across its causes

Given: the beta-role node for widget is clean; the alpha-role node for gadget's source artifact is
missing on disk; the alpha-role node for sprocket carries in-band metadata that is invalid; the
alpha-role node for widget was marked dirty with the reason "the upstream contract changed"; the
delta-role node for widget's source artifact exists on disk with no in-band metadata at all.

1. The caller asks whether the beta-role node for widget is dirty.
   Observed: not dirty.
   Realized by: graph node referencing and dirty evaluation through `dag_storage`, whose node
   identity the component's own canonical node coordinates address.

2. The caller asks whether the alpha-role node for gadget is dirty.
   Observed: dirty, because its source artifact is missing on disk.
   Realized by: graph node referencing and dirty evaluation through `dag_storage`, whose node
   identity the component's own canonical node coordinates address.

3. The caller asks whether the alpha-role node for sprocket is dirty.
   Observed: dirty, because its in-band metadata is invalid.
   Realized by: graph node referencing and dirty evaluation through `dag_storage`, whose node
   identity the component's own canonical node coordinates address.

4. The caller asks whether the alpha-role node for widget is dirty.
   Observed: dirty, because it carries a dirty tag.
   Realized by: graph node referencing and dirty evaluation through `dag_storage`, whose node
   identity the component's own canonical node coordinates address.

5. The caller asks whether the delta-role node for widget is dirty.
   Observed: dirty, because its in-band metadata is missing.
   Realized by: graph node referencing and dirty evaluation through `dag_storage`, whose node
   identity the component's own canonical node coordinates address.

### Scenario 19 — Reporting dirtiness from dependency changes

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
   Realized by: graph node referencing through `dag_storage` and the dependency edges recorded in
   node storage against the component's own canonical node coordinates.

2. The caller asks whether the alpha-role node for sprocket is dirty.
   Observed: not dirty, because its dependency is silent and precludes change message propagation.
   Realized by: graph node referencing through `dag_storage` and the non-propagating silent edges
   recorded in node storage against the component's own canonical node coordinates.

3. The caller asks whether the alpha-role node for gadget is dirty.
   Observed: not dirty, because its non-silent dependency was changed before the node was last
   cleaned.
   Realized by: graph node referencing and dirty evaluation through `dag_storage`, whose node
   identity the component's own canonical node coordinates address.

### Scenario 20 — Adding a feedback message that blames a dependency target

Given: the alpha-role node for sprocket depends non-silently on the beta-role node for widget; the
beta-role node for widget is clean and holds no messages.

1. The caller adds the feedback message "the widget beta-role output omits the required field",
blaming the beta-role node for widget. Observed: that text is recorded as unacted feedback in the
beta-role node for widget's in-band metadata, the messages recorded for that node now hold it, and
the node reports as dirty. Realized by: graph node referencing through `dag_storage`, whose node
identity the component's own canonical node coordinates address.

### Scenario 21 — Materializing a template for a node whose source artifact is missing

Given: the beta-role node for gadget's source artifact is missing on disk, and the initial content
of the beta-role template is "# gadget beta: describe the beta-role work here".

1. The caller materializes the template for the beta-role node for gadget.
   Observed: the node's source artifact now exists on disk holding "# gadget beta: describe the
   beta-role work here".
   Realized by: graph node referencing through `dag_storage`, whose node identity the component's
   own canonical node coordinates and node directory address.

### Scenario 22 — Preserving an existing source artifact when materializing a template

Given: the alpha-role node for widget's source artifact exists on disk holding "# widget alpha:
edited by the caller", and the initial content of the alpha-role template is "# widget alpha:
describe the alpha-role work here".

1. The caller materializes the template for the alpha-role node for widget.
   Observed: the source artifact is preserved and still holds "# widget alpha: edited by the
   caller", rather than the template's initial content.
   Realized by: graph node referencing through `dag_storage`, whose node identity the component's
   own canonical node coordinates and node directory address.

### Scenario 23 — Marking a node dirty with a reason

Given: the beta-role node for widget was marked clean at 2026-01-02T03:04:05Z, and the caller
supplies the reason "the upstream contract changed".

1. The caller marks the beta-role node for widget dirty with that reason. Observed: the node's clean
status is removed, the reason "the upstream contract changed" is recorded in its in-band metadata,
and the node reports as dirty. Realized by: graph node referencing through `dag_storage`, whose node
identity the component's own canonical node coordinates address.

### Scenario 24 — Marking a subgraph clean over a chain of dependencies

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
   Realized by: graph node referencing, reachability, and clean marking through `dag_storage`, whose
   node identities the component's own canonical node coordinates address.

### Scenario 25 — Marking a subgraph clean at a node that depends on itself

Given: the alpha-role node for widget declares itself as one of its own dag dependencies and is
dirty; the alpha-role node for gadget is dirty and lies on no path from the alpha-role node for
widget.

1. The caller marks the subgraph clean at the alpha-role node for widget.
   Observed: the alpha-role node for widget is marked clean, the reachable subgraph being that node
   alone, and the alpha-role node for gadget is still dirty.
   Realized by: graph node referencing and clean marking through `dag_storage`, whose node identity
   the component's own canonical node coordinates address.

### Scenario 26 — Marking a subgraph clean across a cycle of dependencies

Given: the alpha-role node for widget depends on the beta-role node for widget and the beta-role
node for widget depends on the alpha-role node for widget; both nodes are dirty; the alpha-role node
for gadget is dirty and lies on no path from either node.

1. The caller marks the subgraph clean at the alpha-role node for widget. Observed: both the
alpha-role node for widget and the beta-role node for widget are marked clean, each being reachable
from the other, and the alpha-role node for gadget is still dirty. Realized by: graph node
referencing and clean marking through `dag_storage`, whose node identities the component's own
canonical node coordinates address.

## Implementation-only

### Scenario 27 — Repository qualifiers that name no repository

Given: the caller holds no canonical node for the widget unit or the gadget unit of the parts
package, which the workspace root `/repo/alpha_scope_a` contains.

1. The caller normalizes the raw target label `//parts:widget` and the raw target label
   `//repository_x/parts:widget`.
   Observed: one canonical node for both labels, because the repository qualifier `repository_x` is
   stripped and carries no package or unit information.
   Realized by: label syntax normalization through `uv_target_labels_ext`, which strips the leading
   repository qualifier, and graph node referencing through `dag_storage`.

2. The caller normalizes the raw target labels `//parts:widget`, `widget`, and `//parts:gadget`.
   Observed: exactly two canonical nodes, one addressing the unit widget in the role alpha for the
   first two labels and one addressing the unit gadget in the role alpha for the third.
   Realized by: label syntax normalization through `uv_target_labels_ext`, whose canonical
   package-and-unit coordinates are reused for one node, and graph node referencing through
   `dag_storage`.

### Scenario 28 — A shorthand target label naming a unit alone

Given: the caller holds no canonical node for the widget unit of the parts package, which the
workspace root `/repo/alpha_scope_a` contains.

1. The caller normalizes the raw target label `widget` and the raw target label `//parts:widget`.
   Observed: one canonical node for both labels, because the shorthand label is expanded with the
   package the workspace resolves the widget unit in.
   Realized by: label syntax normalization through `uv_target_labels_ext`, whose expansion of an
   implicit target identifier supplies the omitted package and unit coordinates, and graph node
   referencing through `dag_storage`.

### Scenario 29 — The workspace root package target

Given: the caller holds no canonical node for the unit widget declared in the workspace root
package, which the workspace root `/repo/alpha_scope_a` addresses directly.

1. The caller normalizes the raw target label `//:widget`.
   Observed: a canonical node addressing the unit widget of the workspace root package.
   Realized by: label syntax normalization through `uv_target_labels_ext` and graph node referencing
   through `dag_storage`.

2. The caller asks for the node directory of that canonical node.
   Observed: the empty workspace path, being the workspace root itself rather than a nested package
   directory.
   Realized by: package filesystem directory resolution through `uv_target_labels_ext`, which
   handles a workspace root package target, and workspace path representation through `file_paths`.

### Scenario 30 — A target label annotated with a role

Given: the caller holds no canonical node for the widget unit of the parts package in the role beta,
and the workspace root `/repo/alpha_scope_a` contains the unit.

1. The caller normalizes the raw target label `//parts:widget` under the role annotation beta.
   Observed: a canonical node addressing the unit widget in the role beta, distinct from the
   canonical node for the same unit under the role alpha.
   Realized by: label syntax normalization through `uv_target_labels_ext`, which attaches role
   addresses when supplied, and graph node referencing through `dag_storage`.

### Scenario 31 — A label whose unit name holds a path separator

Given: the caller holds no canonical node, and the workspace root `/repo/alpha_scope_a` holds the
package `parts`.

1. The caller normalizes the raw target label `//parts:widget/gadget`, whose unit name holds a path
   separator.
   Observed: the normalization fails explicitly, naming the malformed label, and no canonical node
   is returned.
   Realized by: target syntax validation through `uv_target_labels_ext`, whose package path segment
   and unit name rules reject the label, and the component's own propagation of that rejection.
