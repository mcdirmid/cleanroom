<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:20:03Z
CHANGE: Author uv uv_target interface scenarios
CODE_HASH: 46f2989e86d2
-->

# Concrete scenarios for `uv_target` (interface)

## Scenario 1 — Normalizing a package-qualified target label

Given: the workspace root `/repo/alpha_scope_a` holds the package `parts` and the unit widget, and
the caller holds no canonical node for either.

1. The caller normalizes the raw target label `//parts:widget`, which names the widget unit of the
   parts package.
   Observed: a canonical node addressing the unit widget in the role alpha of the workspace at
   `/repo/alpha_scope_a`.

## Scenario 2 — Two spellings of one target label

Given: the caller holds no canonical node for the widget unit of the parts package.

1. The caller normalizes the raw target labels `//parts:widget` and `parts:widget`, both naming the
   widget unit of the parts package.
   Observed: one canonical node, identical for both spellings, because the repository qualifier the
   second spelling omits carries no package or unit information.

## Scenario 3 — An omitted target name

Given: the caller holds no canonical node for the unit widget of the workspace root package and no
canonical node for the unit sprocket of the parts package.

1. The caller normalizes the raw target labels `//:widget` and `//parts:sprocket`.
   Observed: a canonical node addressing the unit widget of the workspace root package and a
   canonical node addressing the unit sprocket of the parts package, which are two different nodes.

## Scenario 4 — Extracting the node directory of a canonical node

Given: the caller holds the canonical node addressing the widget unit of the parts package and the
canonical node addressing the gadget unit of the parts package.

1. The caller asks for the node directory of the widget node.
   Observed: the workspace path `parts/widget`, the package directory the workspace root
   `/repo/alpha_scope_a` contains the widget unit in.

2. The caller asks for the node directory of the gadget node. Observed: the workspace path
`parts/gadget`, a different package directory from the one of step 1.

## Scenario 5 — A target label that is malformed

Given: the workspace root `/repo/alpha_scope_a` holds the package `parts`, and the caller holds no
canonical node.

1. The caller normalizes the raw target label `//parts:widget gadget`, whose unit name holds a space
character. Observed: the normalization fails explicitly, naming the malformed label, and no
canonical node is returned.

2. The caller normalizes the empty raw target label.
   Observed: the normalization fails explicitly, and no canonical node is returned.

## Scenario 6 — A node whose package directory the workspace does not contain

Given: the workspace root `/repo/alpha_scope_a` holds no package directory for the unit sprocket,
and the caller holds no canonical node for it.

1. The caller normalizes the raw target label `//parts:sprocket`.
   Observed: a canonical node addressing the unit sprocket in the parts package.

2. The caller asks for the node directory of that canonical node.
   Observed: the request fails explicitly, naming the package directory `parts/sprocket` that the
   workspace root `/repo/alpha_scope_a` does not contain, rather than reporting a directory that
   holds no unit.
