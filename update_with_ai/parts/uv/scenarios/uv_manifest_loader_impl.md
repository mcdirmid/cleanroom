<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T03:23:51Z
CHANGE: Restrict reused scenarios to the declared imports closure
CODE_HASH: 4c0d15db21ff
-->

# Concrete scenarios for `uv_manifest_loader_impl` (implementation)

Scenarios 1 through 13 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 14 through
18 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

The scenarios of the `uv_manifest_loader` interface the component implements come first, then the
scenarios of the interface specification of its imports closure that it realizes: `agent_storage`.

### Scenario 1 — Retrieving the manifest of one declared target

Given: role alpha is defined in the workspace directory /ws/alpha_scope_a and declares the widget
unit of the parts package with the source file `parts/widget/widget.md` and the task prompt
`rework the widget source so it reads the sprocket table`, and no target has been loaded from that
definition yet.

1. The caller asks the uv manifest loader for the manifest of the alpha-role target for widget.
   Observed: one target node, the alpha-role target for widget of the workspace at
   /ws/alpha_scope_a, and its manifest carries the task prompt `rework the widget source so it reads
   the sprocket table` and the declared source file `parts/widget/widget.md`.
   Realized by: role definition parsing and layout conventions through `uv_manifest_ext`; workspace
   root path resolution through `file_paths`; target label normalization and package directory
   resolution through `uv_target`; and node definition and task prompt storage through
   `agent_storage`.

### Scenario 2 — Resolving declared direct dependencies into graph edges

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and that unit declares direct dependencies on the gadget unit and on the
sprocket unit of the same package.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records exactly two edges, to
   the alpha-role target for gadget and to the alpha-role target for sprocket; the alpha-role target
   for gadget carries a task prompt and an edge to the alpha-role target for sprocket; and the
   alpha-role target for sprocket carries a task prompt and no edge.
   Realized by: unit specification and role definition decoding through `uv_manifest_ext`;
   dependency registration through `dag_storage`; node definition and task prompt storage through
   `agent_storage`; and the component's own walk of the declared dependency closure.

### Scenario 3 — A dependency declared neither direct nor propagating

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md` and its direct dependency on the sprocket unit of the same package, and the
widget unit separately marks that sprocket dependency as one the role alpha target does not
propagate.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records the sprocket dependency
   once, marked non-propagating, and the alpha-role target for sprocket carries a task prompt while
   the edge carries no prompt of its own.
   Realized by: silent role dependency lists through `uv_manifest_ext`; non-propagating dependency
   registration through `dag_storage`; and the component's own synthesis of a promptless
   pass-through node definition.

### Scenario 4 — A declared dependency with no manifest of its own

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and that unit declares the direct dependency on the gadget unit of the
same package, which no role definition declares.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records the edge to the
   alpha-role target for gadget, and the alpha-role target for gadget is present in graph storage
   with no task prompt and no source file.
   Realized by: dependency registration through `dag_storage`; node definition storage through
   `agent_storage`; and the component's own synthesis of an empty node definition for a referenced
   dependency target that lacks a manifest.

### Scenario 5 — A unit whose component type is not active for the role

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, that unit declares the direct dependency on the gadget unit of the same
package, the gadget unit holds the constituent unit widget, and role alpha marks the component type
of the gadget unit as not active.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: one node definition for the alpha-role target for gadget carrying no task prompt, and
   it forwards the dependencies of the gadget unit as edges to the alpha-role targets of its
   constituent units rather than edges to implementations of the gadget unit itself.
   Realized by: active component type lists through `uv_manifest_ext`; dependency registration
   through `dag_storage`; and the component's own synthesis of a promptless pass-through node
   definition that forwards dependency edges to constituent units and role dependencies.

### Scenario 6 — A target that declares no dependency at all

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and that unit declares neither a direct dependency nor a dependency the
role alpha target does not propagate.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records no edge, and no other
   node definition is synthesized.
   Realized by: unit specification decoding through `uv_manifest_ext`; node definition storage
   through `agent_storage`; and the component's own dependency walk, which finds no declared
   dependency and registers no edge through `dag_storage`.

### Scenario 7 — A manifest declaring no targets

Given: the workspace target manifest holds the JSON text `{}`, and it declares no target.

1. The caller asks the agent storage for the declared nodes.
   Observed: nothing is returned, and no node definition is provided.
   Realized by: node definition and task prompt storage through `agent_storage`, which the
   component's own synthesized manifests populate.

2. The caller asks for the dependencies of the widget target.
   Observed: the query fails explicitly, because the manifest declares no widget target.
   Realized by: dependency registration through `dag_storage`, whose nodes the component's own
   synthesized manifests populate.

### Scenario 8 — One declared target

Given: the workspace target manifest declares the target `//widget`, whose task prompt is
`clean the widget source`, and declares no dependency.

1. The caller asks for the nodes the manifest declares.
   Observed: exactly one node, addressing the unit widget under the role named by `//widget`.
   Realized by: node definition storage through `agent_storage`, populated by the component's own
   synthesized target manifest records.

2. The caller asks for the task prompt of the widget target.
   Observed: `clean the widget source`.
   Realized by: task prompt storage through `agent_storage`, whose prompt the component's own
   evaluation of the role prompt template supplies.

3. The caller asks for the node definition of the widget target.
   Observed: a definition identifying the widget target, carrying `clean the widget source`, and
   reporting no dependencies.
   Realized by: node definition storage through `agent_storage` and dependency registration through
   `dag_storage`.

### Scenario 9 — A manifest declaring a dependency structure

Given: the workspace target manifest declares `//widget` whose task prompt is
`clean the widget source` with a dependency on `//gadget`, `//gadget` whose task prompt is
`refresh the gadget index` with a dependency on `//sprocket`, and `//sprocket` whose task prompt is
`verify the sprocket table` with no dependency; `//sprocket` is declared silent under `//widget`.

1. The caller asks for the node definitions of the widget, gadget, and sprocket targets.
   Observed: three definitions, mapping those task prompts to those targets, and no others.
   Realized by: node definition storage through `agent_storage`, populated by the component's own
   synthesized target manifest records.

2. The caller asks for the dependencies of the widget target.
   Observed: the gadget and sprocket targets, of which the sprocket target is silent and the gadget
   target is not.
   Realized by: dependency registration through `dag_storage`, whose silent partition the
   component's own reading of the silent role dependency lists supplies.

3. The caller asks for the dependencies of the gadget target.
   Observed: the sprocket target, declared there as a non-silent dependency.
   Realized by: dependency registration through `dag_storage`, whose propagating edges the
   component's own reading of the declared direct dependencies supplies.

### Scenario 10 — The dirty state of a node over time

Given: the workspace target manifest declares `//widget`, whose task prompt is
`clean the widget source` with a dependency on the non-silent `//gadget`, the widget source
artifact is not present on disk, and the gadget source artifact carries in-band metadata whose clean
timestamp is `2026-02-03T04:05:06Z`.

1. The caller asks whether the widget node is dirty.
   Observed: dirty, because its source artifact is missing on disk.
   Realized by: dirty evaluation through `agent_storage`, whose node identity the component's own
   synthesized target manifest records establish.

2. The widget source artifact is materialized and carries in-band metadata whose clean timestamp is
   `2026-02-05T06:07:08Z`, and the caller asks whether the widget node is dirty.
   Observed: not dirty, because its in-band metadata is present, names a clean timestamp, and names
   no dependency cleaned after `2026-02-05T06:07:08Z`.
   Realized by: dirty evaluation through `agent_storage`, whose dependency edges the component's own
   registration through `dag_storage` supplies.

3. The caller brings the gadget node clean at `2026-02-06T07:08:09Z` and then asks whether the
   widget node is dirty.
   Observed: dirty, because its non-silent gadget dependency was cleaned after the widget node was
   last cleaned.
   Realized by: dirty evaluation through `agent_storage` and the non-propagating partition of the
   edges the component's own registration through `dag_storage` supplies.

4. The caller brings the widget node clean at `2026-02-07T08:09:10Z` and asks whether it is dirty.
   Observed: not dirty, because the widget node's clean timestamp is later than the gadget node's.
   Realized by: dirty evaluation through `agent_storage` and the edges the component's own
   registration through `dag_storage` supplies.

### Scenario 11 — A manifest declaring a self-dependency

Given: the workspace target manifest declares the target `//widget`, whose task prompt is
`clean the widget source` with a dependency on `//widget`.

1. The caller asks for the nodes the manifest declares.
   Observed: exactly one node, for the widget target.
   Realized by: node definition storage through `agent_storage`, populated by the component's own
   synthesized target manifest records.

2. The caller asks for the dependencies of the widget target.
   Observed: the widget target itself, reported as the dependency the manifest declares, and not
   rejected as a self-dependency.
   Realized by: dependency registration through `dag_storage`, which records the declared edge
   without rejecting it.

### Scenario 12 — A manifest declaring a cycle and a disconnected target

Given: the workspace target manifest declares `//widget` whose task prompt is
`clean the widget source` with a dependency on `//gadget`, `//gadget` whose task prompt is
`refresh the gadget index` with a dependency on `//widget`, and `//sprocket` whose task prompt is
`verify the sprocket table` with no dependency.

1. The caller asks for the dependency structure the manifest declares.
   Observed: three nodes, with the widget target depending on the gadget target and the gadget
   target depending on the widget target, and the sprocket target is reachable from the widget
   target through no chain of declared dependencies.
   Realized by: dependency registration through `dag_storage`, which records the declared edges
   without rejecting the cycle, and node definition storage through `agent_storage`.

2. The caller asks for the dependencies of the widget target.
   Observed: the gadget target only, reported exactly as the manifest declares it, and not rejected
   because the gadget target depends on the widget target in turn.
   Realized by: dependency registration through `dag_storage`, whose recorded edges the component's
   own target manifest records supply.

### Scenario 13 — A manifest that is missing, empty, or malformed

Given: no file named `parts/widget/targets.json` exists in the workspace.

1. The caller asks the agent storage for the nodes declared by `parts/widget/targets.json`.
   Observed: the request fails explicitly, naming `parts/widget/targets.json`, and no node or task
   prompt is provided.
   Realized by: node definition storage through `agent_storage`, whose target manifest the
   component's own discovery of workspace directories fails to supply.

2. The file `parts/widget/targets.json` is created holding zero bytes, and the caller asks again.
   Observed: the request fails explicitly rather than reporting a manifest that declares no target.
   Realized by: node definition storage through `agent_storage`, whose target manifest the
   component's own decoding of the empty file fails to supply.

3. The file `parts/widget/targets.json` is rewritten to hold the JSON text
   `"//widget": {"prompt": "clean the widget source"`, which is missing its opening brace, and the
   caller asks again.
   Observed: the request fails explicitly, naming the malformed manifest text, and no node
   definition is provided.
   Realized by: unit specification and role definition decoding through `uv_manifest_ext`, whose
   failure the component's own propagation reports without substituting a synthesized record.

### Scenario 14 — A dependency reference that names no package

Given: the workspace holds the parts package with the widget unit and a second package `extras` with
the gadget unit; role alpha declares the widget unit with the source file
`parts/widget/widget.md` and marks its dependency on the gadget unit with a bare unit reference that
names no package.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records the edge to the
   alpha-role target for gadget of the extras package, and no node definition is synthesized for a
   gadget unit of the parts package.
   Realized by: package directory conventions through `uv_manifest_ext` and target label
   normalization through `uv_target`, and the component's own resolution of bare cross-package unit
   dependency references within the parts workspace.

### Scenario 15 — Normalizing repository-relative source paths

Given: role alpha is defined in the workspace directory /ws/alpha_scope_a and declares the widget
unit of the parts package with the source file `parts/widget/widget.md` and the silent source file
`parts/widget/widget_notes.md`, and the workspace root path is /ws/alpha_scope_a.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records the source file
   `parts/widget/widget.md` and the silent source file `parts/widget/widget_notes.md` once each,
   with no repeated `parts` path segment.
   Realized by: workspace root path resolution through `file_paths`, package directory resolution
   through `uv_target`, and the component's own normalization of repository-relative paths across
   package directories and workspace roots.

### Scenario 16 — Locating the role definitions across a package hierarchy

Given: the workspace root is /ws/alpha_scope_a, the scope configuration file declaring role alpha
sits at the workspace root, a nested package directory `/ws/alpha_scope_a/parts` holds the widget
and gadget units, and no target has been loaded yet.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the alpha-role target for widget and the alpha-role target for gadget are both present
   with their task prompts, so the role definition the scope configuration file at the workspace
   root declares was found from the nested package directory.
   Realized by: the component's own upward search of package directories for scope configuration
   files, role definition parsing through `uv_manifest_ext`, and workspace root path resolution
   through `file_paths`.

### Scenario 17 — Fixed role node dependencies become declared direct dependencies

Given: role alpha declares role beta as the role it depends on, so every alpha-role target also
depends on the beta-role target of the same unit, and role alpha declares the widget unit of the
parts package with the source file `parts/widget/widget.md` and no dependency the widget unit
declares.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records the edge to the
   beta-role target for widget, although the widget unit declares no dependency.
   Realized by: role dependency lists through `uv_manifest_ext`, dependency registration through
   `dag_storage`, and the component's own incorporation of fixed role node dependencies as declared
   direct dependencies.

### Scenario 18 — A unit specification that names a dependency it cannot decode

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and the unit specification for widget carries a direct dependency clause
whose text `parts::` holds an empty package path segment.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the resolution fails explicitly, naming the unit specification of widget, and neither
   the alpha-role target for widget nor any dependency node definition is populated.
   Realized by: unit component type classification and role definition deserialization through
   `uv_manifest_ext`, whose failure the component's own propagation reports, and dependency
   registration through `dag_storage`, which records no edge.
