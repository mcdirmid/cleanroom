<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:17:15Z
CHANGE: Author control control_work_scheduler_impl concrete scenarios
CODE_HASH: ec936d4d43f8
-->

# Concrete scenarios for `control_work_scheduler_impl` (implementation)

Scenarios 1 through 7 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 8 through
14 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Discovering one ready task inside a target subgraph

Given: the target subgraph rooted at the alpha-role node for unit widget holds that node, the
beta-role node for unit widget and the beta-role node for unit gadget; the alpha-role node for unit
widget depends on the beta-role node for unit widget and on the beta-role node for unit gadget; the
alpha-role node for unit widget is dirty, and both beta-role nodes are clean; role alpha declares no
role dependency.

1. The agent asks for work in the target subgraph.
   Observed: a work schedule holding one scheduled task, for the alpha-role node for unit widget,
   and the two beta-role nodes in the subgraph are not scheduled.
   Realized by: the ready dirty candidate query through `dag_subgraph` over the provided execution
   subgraph, using the dynamic role order computed by the component, and the component's own task
   synthesis for each returned candidate.

### Scenario 2 — Ordering ready tasks by role tier depth

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
   Realized by: the component's own dynamic role precedence, which inspects the declared role
   dependencies of the role configuration obtained through `agent_node_config` and assigns each role
   a rank equal to its maximum topological depth from the root roles, together with the
   dependency-first candidate ordering through `dag_subgraph`.

### Scenario 3 — A task that carries its dependency paths and unaddressed feedback

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
   Realized by: the configured role prompt template and the role definitions obtained through
   `agent_node_config`; dag dependency queries through `dag_storage` and the component's own
   rendering of the target unit paths and component names into the template; and the collection of
   the open feedback messages recorded on the node through `dag_storage` into the feedback review
   section.

### Scenario 4 — A candidate held back by a dirty non-silent dependency

Given: the target subgraph rooted at the alpha-role node for unit widget holds that node, the
beta-role node for unit gadget and the beta-role node for unit sprocket marked silent under the
alpha-role node; the alpha-role node for unit widget is dirty and depends on both beta-role nodes;
the beta-role node for unit gadget is dirty and the silent beta-role node for unit sprocket is dirty
as well.

1. The agent asks for work in the target subgraph.
   Observed: the alpha-role node for unit widget is not scheduled, because its non-silent beta-role
   dependency for unit gadget is dirty, and the dirty silent beta-role dependency for unit sprocket
   does not hold it back.
   Realized by: the ready candidate filtering through `dag_subgraph`, which validates a candidate
   against its dependencies in clean status through `dag_storage` and treats a silent dependency as
   precluding change propagation rather than blocking readiness.

### Scenario 5 — Discovering work across a directory scope

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
   Realized by: the component's own scan of the nodes held in `dag_storage` that match the directory
   path, filtered for dirty status and for direct non-silent upstream dependencies that are clean in
   graph storage, and the component's own task synthesis for the surviving nodes.

### Scenario 6 — Scopes that hold no ready work

Given: the target subgraph rooted at the alpha-role node for unit widget holds that node and the
alpha-role node for unit gadget; the alpha-role node for unit widget is clean, and the alpha-role
node for unit gadget is dirty although it is reachable from no dependency path of the alpha-role
node for unit widget; the directory scope `/ws/alpha_scope_a/parts/zeta` holds no target node.

1. The agent asks for work in the target subgraph.
   Observed: an empty work schedule, because the dirty alpha-role node for unit gadget does not
   belong to the target subgraph.
   Realized by: the candidate query through `dag_subgraph`, which returns no ready dirty node
   because the alpha-role node for unit widget is clean and the dirty alpha-role node for unit
   gadget is not reachable from the target node.

2. The agent asks for work in the directory scope `/ws/alpha_scope_a/parts/zeta`.
   Observed: an empty work schedule.
   Realized by: the component's own scan of the nodes held in `dag_storage` matching the directory
   path, which matches no node.

### Scenario 7 — A scope whose dirty nodes all depend on one another

Given: the target subgraph rooted at the alpha-role node for unit gadget holds that node, the
beta-role node for unit widget and the beta-role node for unit sprocket; the alpha-role node for
unit gadget is dirty and depends on the beta-role node for unit widget; the beta-role node for unit
widget is dirty and depends on the alpha-role node for unit gadget; the beta-role node for unit
sprocket is dirty and depends on the alpha-role node for unit gadget.

1. The agent asks for work in the target subgraph.
   Observed: an empty work schedule, because no dirty node in the target subgraph has every
   dependency in the target subgraph clean.
   Realized by: the ready candidate filtering through `dag_subgraph`, which requires each candidate's
   dependencies in the target subgraph to be clean in `dag_storage` or present in the same batch,
   and rejects every candidate here because the dependency status reported through `dag_storage` is
   dirty for all of them.

## Implementation-only

### Scenario 8 — Recomputing role precedence when the declared role dependencies change

Given: role alpha declares no role dependency, so it has a precedence rank of zero, and role beta
depends on role alpha, so it has a precedence rank of one; the alpha-role node for unit widget and
the beta-role node for unit gadget are both dirty and declare no dependency in the target subgraph
rooted at the alpha-role node for unit widget.

1. The agent asks for work in the target subgraph.
   Observed: the alpha-role node for unit widget is scheduled before the beta-role node for unit
   gadget.
   Realized by: the component's own role precedence computation over the declared role dependencies
   read from the role configuration through `agent_node_config`, which derives the rank at each
   query rather than from a stored table.

2. Role beta is redeclared to depend on no role while role alpha is redeclared to depend on role
   beta, and the agent asks for work in the target subgraph again.
   Observed: the beta-role node for unit gadget is scheduled before the alpha-role node for unit
   widget.
   Realized by: the same computation over the redeclared role dependencies, which assigns role beta
   rank zero and role alpha rank one.

### Scenario 9 — The longest path decides a shared role's precedence rank

Given: role alpha declares no role dependency, role gamma depends on role alpha, role delta depends
on role alpha, and role epsilon depends on role gamma and on role delta, so role epsilon's maximum
topological depth is two; the epsilon-role node for unit widget, the gamma-role node for unit gadget
and the alpha-role node for unit sprocket are dirty and declare no dependency in the target subgraph
rooted at the epsilon-role node for unit widget.

1. The agent asks for work in the target subgraph.
   Observed: the alpha-role node for unit sprocket is scheduled first, then the gamma-role node for
   unit gadget, then the epsilon-role node for unit widget.
   Realized by: the component's own role precedence computation, which takes a role's rank to be its
   maximum topological depth from the root roles rather than the depth of whichever dependency path
   it encounters first.

### Scenario 10 — A role dependency cycle

Given: role alpha declares role beta as the role it depends on and role beta declares role alpha as
the role it depends on; the alpha-role node for unit widget and the beta-role node for unit gadget
are dirty and declare no dependency in the target subgraph rooted at the alpha-role node for unit
widget.

1. The agent asks for work in the target subgraph.
   Observed: the work schedule is produced without the precedence computation looping, and the
   alpha-role node for unit widget and the beta-role node for unit gadget are each scheduled.
   Realized by: the component's own role precedence computation, which bounds the maximum
   topological depth walk so that a cycle among declared role dependencies yields a defined rank
   rather than an unbounded traversal.

### Scenario 11 — A batch that stops at the requested limit

Given: the target subgraph rooted at the alpha-role node for unit widget holds the alpha-role nodes
for the units widget, gadget and sprocket, all dirty and declaring no dependency, and the requested
batch limit is two.

1. The agent asks for work in the target subgraph with the batch limit of two.
   Observed: a work schedule holding two scheduled tasks, and the third dirty alpha-role node is
   left for a later request.
   Realized by: the component's own formatting of the ready candidates up to the requested batch
   limit, which stops the task synthesis after the limit is reached.

### Scenario 12 — The feedback review of a node whose feedback was already addressed

Given: the alpha-role node for unit widget is dirty in the target subgraph rooted at that node and
declares no dependency; the node records no unaddressed feedback message because the feedback
recorded on it was addressed by a previous cleaning pass.

1. The agent asks for work in the target subgraph.
   Observed: a work schedule holding one scheduled task for the alpha-role node for unit widget
   whose task prompt carries no feedback review section.
   Realized by: the component's own collection of the messages recorded on the node through
   `dag_storage`, which yields no open feedback message and therefore omits the section from the
   formatted prompt.

### Scenario 13 — Formatting an auditor session task prompt

Given: the candidate node being scheduled is the qa-role node for unit widget; the node configuration
configures the blame target `parts/widget/lib/widget.py` for that node and the grounding file is
`parts/widget/low/widget.pyi`.

1. The work scheduler formats the task prompt for the qa-role candidate node.
   Observed: the prompt contains `parts/widget/lib/widget.py against parts/widget/low/widget.pyi`,
   states that all files in this workspace are strictly read-only, instructs to run check_files to
   verify, submit to certify, and blame specifying the culprit file and critique when checks fail.
   Realized by: the component's own task prompt synthesis for auditor nodes, which resolves blame
   targets against grounding files and injects read-only auditor execution directives.

### Scenario 14 — Formatting multi-node task prompt target instructions

Given: the candidate nodes being scheduled are the alpha-role node for unit widget and the alpha-role
node for unit gadget; neither node is an auditor role.

1. The work scheduler formats the task prompt for the multi-node batch.
   Observed: the prompt contains `When submitting or failing completed units, specify target as the file path.`
   Realized by: the component's own multi-node task prompt synthesis, which instructs file path
   target specification rather than exposing raw unit addresses.
