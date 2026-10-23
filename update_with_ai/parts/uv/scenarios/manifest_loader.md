# Concrete scenarios for `uv_manifest_loader` (interface)

## Scenario 1 — Retrieving the manifest of one declared target

Given: role alpha is defined in the workspace directory /ws/alpha_scope_a and declares the widget
unit of the parts package with the source file `parts/widget/widget.md` and the task prompt
`rework the widget source so it reads the sprocket table`, and no target has been loaded from that
definition yet.

1. The caller asks the uv manifest loader for the manifest of the alpha-role target for widget.
   Observed: one target node, the alpha-role target for widget of the workspace at
   /ws/alpha_scope_a, and its manifest carries the task prompt `rework the widget source so it reads
   the sprocket table` and the declared source file `parts/widget/widget.md`.

## Scenario 2 — Resolving declared direct dependencies into graph edges

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and that unit declares direct dependencies on the gadget unit and on the
sprocket unit of the same package.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records exactly two edges, to
   the alpha-role target for gadget and to the alpha-role target for sprocket; the alpha-role target
   for gadget carries a task prompt and an edge to the alpha-role target for sprocket; and the
   alpha-role target for sprocket carries a task prompt and no edge.

## Scenario 3 — A dependency declared neither direct nor propagating

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md` and its direct dependency on the sprocket unit of the same package, and the
widget unit separately marks that sprocket dependency as one the role alpha target does not
propagate.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records the sprocket dependency
   once, marked non-propagating, and the alpha-role target for sprocket carries a task prompt while
   the edge carries no prompt of its own.

## Scenario 4 — A declared dependency with no manifest of its own

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and that unit declares the direct dependency on the gadget unit of the
same package, which no role definition declares.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records the edge to the
   alpha-role target for gadget, and the alpha-role target for gadget is present in graph storage
   with no task prompt and no source file.

## Scenario 5 — A unit whose component type is not active for the role

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, that unit declares the direct dependency on the gadget unit of the same
package, the gadget unit holds the constituent unit widget, and role alpha marks the component type
of the gadget unit as not active.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: one node definition for the alpha-role target for gadget carrying no task prompt, and
   it forwards the dependencies of the gadget unit as edges to the alpha-role targets of its
   constituent units rather than edges to implementations of the gadget unit itself.

## Scenario 6 — A target that declares no dependency at all

Given: role alpha declares the widget unit of the parts package with the source file
`parts/widget/widget.md`, and that unit declares neither a direct dependency nor a dependency the
role alpha target does not propagate.

1. The caller asks the uv manifest loader to resolve the alpha-role target for widget.
   Observed: the node definition of the alpha-role target for widget records no edge, and no other
   node definition is synthesized.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:20:02Z
CHANGE: Author uv manifest_loader interface scenarios
-->
