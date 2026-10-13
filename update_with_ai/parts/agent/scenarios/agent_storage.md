<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-11T03:11:13Z
CHANGE: Author agent agent_storage interface scenarios
CODE_HASH: 79fe2cf4ceec
-->

# Concrete scenarios for `agent_storage` (interface)

## Scenario 1 — A manifest declaring no targets

Given: the workspace target manifest holds the JSON text `{}`, and it declares no target.

1. The caller asks the agent storage for the declared nodes.
   Observed: nothing is returned, and no node definition is provided.

2. The caller asks for the dependencies of the widget target.
   Observed: the query fails explicitly, because the manifest declares no widget target.

## Scenario 2 — One declared target

Given: the workspace target manifest declares the target `//widget`, whose task prompt is
`clean the widget source`, and declares no dependency.

1. The caller asks for the nodes the manifest declares.
   Observed: exactly one node, addressing the unit widget under the role named by `//widget`.

2. The caller asks for the task prompt of the widget target.
   Observed: `clean the widget source`.

3. The caller asks for the node definition of the widget target.
   Observed: a definition identifying the widget target, carrying `clean the widget source`, and
   reporting no dependencies.

## Scenario 3 — A manifest declaring a dependency structure

Given: the workspace target manifest declares `//widget` whose task prompt is
`clean the widget source` with a dependency on `//gadget`, `//gadget` whose task prompt is
`refresh the gadget index` with a dependency on `//sprocket`, and `//sprocket` whose task prompt is
`verify the sprocket table` with no dependency; `//sprocket` is declared silent under `//widget`.

1. The caller asks for the node definitions of the widget, gadget, and sprocket targets.
   Observed: three definitions, mapping those task prompts to those targets, and no others.

2. The caller asks for the dependencies of the widget target.
   Observed: the gadget and sprocket targets, of which the sprocket target is silent and the gadget
   target is not.

3. The caller asks for the dependencies of the gadget target.
   Observed: the sprocket target, declared there as a non-silent dependency.

## Scenario 4 — The dirty state of a node over time

Given: the workspace target manifest declares `//widget`, whose task prompt is
`clean the widget source` with a dependency on the non-silent `//gadget`, the widget source
artifact is not present on disk, and the gadget source artifact carries in-band metadata whose clean
timestamp is `2026-02-03T04:05:06Z`.

1. The caller asks whether the widget node is dirty.
   Observed: dirty, because its source artifact is missing on disk.

2. The widget source artifact is materialized and carries in-band metadata whose clean timestamp is
   `2026-02-05T06:07:08Z`, and the caller asks whether the widget node is dirty.
   Observed: not dirty, because its in-band metadata is present, names a clean timestamp, and names
   no dependency cleaned after `2026-02-05T06:07:08Z`.

3. The caller brings the gadget node clean at `2026-02-06T07:08:09Z` and then asks whether the
   widget node is dirty.
   Observed: dirty, because its non-silent gadget dependency was cleaned after the widget node was
   last cleaned.

4. The caller brings the widget node clean at `2026-02-07T08:09:10Z` and asks whether it is dirty.
   Observed: not dirty, because the widget node's clean timestamp is later than the gadget node's.

## Scenario 5 — A manifest declaring a self-dependency

Given: the workspace target manifest declares the target `//widget`, whose task prompt is
`clean the widget source` with a dependency on `//widget`.

1. The caller asks for the nodes the manifest declares.
   Observed: exactly one node, for the widget target.

2. The caller asks for the dependencies of the widget target.
   Observed: the widget target itself, reported as the dependency the manifest declares, and not
   rejected as a self-dependency.

## Scenario 6 — A manifest declaring a cycle and a disconnected target

Given: the workspace target manifest declares `//widget` whose task prompt is
`clean the widget source` with a dependency on `//gadget`, `//gadget` whose task prompt is
`refresh the gadget index` with a dependency on `//widget`, and `//sprocket` whose task prompt is
`verify the sprocket table` with no dependency.

1. The caller asks for the dependency structure the manifest declares.
   Observed: three nodes, with the widget target depending on the gadget target and the gadget
   target depending on the widget target, and the sprocket target is reachable from the widget
   target through no chain of declared dependencies.

2. The caller asks for the dependencies of the widget target.
   Observed: the gadget target only, reported exactly as the manifest declares it, and not rejected
   because the gadget target depends on the widget target in turn.

## Scenario 7 — A manifest that is missing, empty, or malformed

Given: no file named `parts/widget/targets.json` exists in the workspace.

1. The caller asks the agent storage for the nodes declared by `parts/widget/targets.json`.
   Observed: the request fails explicitly, naming `parts/widget/targets.json`, and no node or task
   prompt is provided.

2. The file `parts/widget/targets.json` is created holding zero bytes, and the caller asks again.
   Observed: the request fails explicitly rather than reporting a manifest that declares no target.

3. The file `parts/widget/targets.json` is rewritten to hold the JSON text
   `"//widget": {"prompt": "clean the widget source"`, which is missing its opening brace, and the
   caller asks again.
   Observed: the request fails explicitly, naming the malformed manifest text, and no node
   definition is provided.
