<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:17:15Z
CHANGE: Author control control_work_scheduler concrete scenarios
CODE_HASH: d0681d268f5a
-->

# Concrete scenarios for `control_work_scheduler` (interface)

## Scenario 1 — Discovering one ready task inside a target subgraph

Given: the target subgraph rooted at the alpha-role node for unit widget holds that node, the
beta-role node for unit widget and the beta-role node for unit gadget; the alpha-role node for unit
widget depends on the beta-role node for unit widget and on the beta-role node for unit gadget; the
alpha-role node for unit widget is dirty, and both beta-role nodes are clean; role alpha declares no
role dependency.

1. The agent asks for work in the target subgraph.
   Observed: a work schedule holding one scheduled task, for the alpha-role node for unit widget,
   and the two beta-role nodes in the subgraph are not scheduled.

## Scenario 2 — Ordering ready tasks by role tier depth

Given: roles alpha and gamma declare no role dependency, so each has tier depth zero, and role delta
depends on role gamma, so it has tier depth one; the target subgraph rooted at the delta-role node
for unit sprocket holds that node, the gamma-role node for unit widget, the alpha-role node for unit
gadget and the alpha-role node for unit widget; the alpha-role node for unit widget and the
gamma-role node for unit widget are dirty and declare no dependency, the alpha-role node for unit
gadget is dirty and depends on the gamma-role node for unit widget, and the delta-role node for unit
sprocket is dirty and depends on the alpha-role node for unit gadget.

1. The agent asks for work in the target subgraph.
   Observed: a work schedule holding three scheduled tasks in the order of the alpha-role node for
   unit widget, then the gamma-role node for unit widget, then the delta-role node for unit
   sprocket, so that the lower-depth roles are scheduled before the deeper role.

## Scenario 3 — A task that carries its dependency paths and unaddressed feedback

Given: the role prompt template for role alpha is `clean the [[component]] unit of [[path]]`; the
alpha-role node for unit widget is dirty in the target subgraph rooted at that node and depends on
the beta-role node for unit gadget at the path `parts/gadget/gadget_spec.md` and on the beta-role
node for unit sprocket at the path `parts/sprocket/sprocket_spec.md`; both beta-role nodes are
clean; the alpha-role node for unit widget records the unaddressed feedback message `the gadget
contract declares the widget field twice`.

1. The agent asks for work in the target subgraph.
   Observed: a work schedule holding one scheduled task for the alpha-role node for unit widget
   whose task prompt is `clean the widget unit of parts/widget/widget_spec.md`, whose declared
   upstream dependency paths are `parts/gadget/gadget_spec.md` and
   `parts/sprocket/sprocket_spec.md`, and which carries the unaddressed feedback message `the
   gadget contract declares the widget field twice`.

## Scenario 4 — A candidate held back by a dirty non-silent dependency

Given: the target subgraph rooted at the alpha-role node for unit widget holds that node, the
beta-role node for unit gadget and the beta-role node for unit sprocket marked silent under the
alpha-role node; the alpha-role node for unit widget is dirty and depends on both beta-role nodes;
the beta-role node for unit gadget is dirty and the silent beta-role node for unit sprocket is dirty
as well.

1. The agent asks for work in the target subgraph.
   Observed: the alpha-role node for unit widget is not scheduled, because its non-silent beta-role
   dependency for unit gadget is dirty, and the dirty silent beta-role dependency for unit sprocket
   does not hold it back.

## Scenario 5 — Discovering work across a directory scope

Given: the directory scope `/ws/alpha_scope_a/parts` holds the alpha-role node for unit widget, at
`parts/widget/widget_spec.md` and dirty with no dependency, the alpha-role node for unit gadget, at
`parts/gadget/gadget_spec.md` and dirty with a dependency on the beta-role node for unit sprocket at
`parts/sprocket/sprocket_spec.md`, and the alpha-role node for unit sprocket, at
`parts/sprocket/sprocket_spec.md` and clean; the beta-role node for unit sprocket at
`parts/sprocket/sprocket_spec.md` is dirty; the alpha-role node for unit zeta at
`/ws/alpha_scope_b/parts/zeta/zeta_spec.md` is dirty and lies outside the directory scope; the role
prompt template for role alpha is `clean the [[component]] unit of [[path]]`.

1. The agent asks for work in the directory scope `/ws/alpha_scope_a/parts`.
   Observed: a work schedule holding the task for the alpha-role node for unit widget only, because
   the alpha-role node for unit gadget has a dirty upstream beta-role dependency, the alpha-role
   node for unit sprocket is clean, and the alpha-role node for unit zeta lies outside the scope.

## Scenario 6 — Scopes that hold no ready work

Given: the target subgraph rooted at the alpha-role node for unit widget holds that node and the
alpha-role node for unit gadget; the alpha-role node for unit widget is clean, and the alpha-role
node for unit gadget is dirty although it is reachable from no dependency path of the alpha-role
node for unit widget; the directory scope `/ws/alpha_scope_a/parts/zeta` holds no target node.

1. The agent asks for work in the target subgraph.
   Observed: an empty work schedule, because the dirty alpha-role node for unit gadget does not
   belong to the target subgraph.

2. The agent asks for work in the directory scope `/ws/alpha_scope_a/parts/zeta`.
   Observed: an empty work schedule.

## Scenario 7 — A scope whose dirty nodes all depend on one another

Given: the target subgraph rooted at the alpha-role node for unit gadget holds that node, the
beta-role node for unit widget and the beta-role node for unit sprocket; the alpha-role node for
unit gadget is dirty and depends on the beta-role node for unit widget; the beta-role node for unit
widget is dirty and depends on the alpha-role node for unit gadget; the beta-role node for unit
sprocket is dirty and depends on the alpha-role node for unit gadget.

1. The agent asks for work in the target subgraph.
   Observed: an empty work schedule, because no dirty node in the target subgraph has every
   dependency in the target subgraph clean.
