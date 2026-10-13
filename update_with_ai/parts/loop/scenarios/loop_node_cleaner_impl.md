<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-11T03:11:44Z
CHANGE: Author loop loop_node_cleaner_impl concrete scenarios
CODE_HASH: 6bb3c13a5218
-->

# Concrete scenarios for `loop_node_cleaner_impl` (implementation)

Scenarios 1 through 5 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 6
through 10 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — No dirty node shares the role

Given: no node in graph storage is dirty in role alpha, and the beta-role target for gadget is clean
with last cleaned timestamp 2026-01-02T03:04:05Z.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, and the beta-role target for gadget still carries the last cleaned
   timestamp 2026-01-02T03:04:05Z.
   Realized by: role configuration lookups through `agent_node_config` for the active role alpha, and
   node status reads through `dag_storage`, which the clean marking of earlier cleaning runs writes
   and which report no dirty node in role alpha; the component's own selection of the dirty nodes
   that share the role, which selects none; and the component's own continuation, which reports that
   processing continues when no node is selected.

### Scenario 2 — One dirty node in the role, and a dirty node of another role left alone

Given: the alpha-role target for widget is dirty because its in-band source metadata is missing, the
beta-role target for gadget is dirty, and neither node depends on the other.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, the alpha-role target for widget is clean in graph storage, and
   the beta-role target for gadget is still dirty.
   Realized by: role configuration lookups through `agent_node_config`, which present role alpha to
   the session services; the node definition and task prompt of widget through `agent_storage`; the
   agent session phase, with turn loop execution through `loop_driver`, session services through
   `sandbox`, and conversation initialization through `loop_conversation` with the instruction
   directing the agent to call the get work tool; clean marking through `dag_storage`; and the
   component's own selection of the dirty nodes that share role alpha, which leaves the beta-role
   target for gadget untouched.

### Scenario 3 — Several dirty nodes sharing the role

Given: the alpha-role targets for widget, gadget, and sprocket are dirty, and none of them depends on
another.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, and all three nodes are clean in graph storage.
   Realized by: the component's own session phase over the three nodes that share role alpha, with
   the task prompt of each node supplied by `agent_storage`, turn loop execution through
   `loop_driver`, session services through `sandbox`, and clean marking of each resolved node through
   `dag_storage`.

### Scenario 4 — A failure that another node cleaning addresses

Given: the alpha-role target for widget is dirty, cleaning it fails on the widget source file, and
the beta node cleaning also addresses the alpha-role target for widget.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, and the alpha-role target for widget is still dirty.
   Realized by: the outcome of the turn loop executed through `loop_driver`; the failure recorded
   through `runner_logger`; and the component's own continuation, which reports that processing
   continues while another node cleaning still addresses the failing node.

2. The beta node cleaner cleans the dirty nodes it addresses.
   Observed: processing continues, and the alpha-role target for widget is clean in graph storage.
   Realized by: the same component running under the beta role configuration resolved through
   `agent_node_config`, with the resolved node marked clean through `dag_storage`.

### Scenario 5 — A failure that no other node cleaning addresses

Given: the alpha-role target for widget is dirty, cleaning it fails on the widget source file, and no
other node cleaning addresses the widget source file.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing cannot continue, and the alpha-role target for widget is still dirty.
   Realized by: the outcome of the turn loop executed through `loop_driver`; the failure recorded
   through `runner_logger`; and the component's own continuation, which reports that processing
   cannot continue and leaves the node dirty in `dag_storage`.

## Implementation-only

### Scenario 6 — Workspace file modifications decide the change summary and the change timestamp

Given: the alpha-role target for widget is dirty and carries the task prompt "rework widget to use
the new parser"; the alpha-role target for gadget is dirty and carries the task prompt "rework gadget
to read the new parser output"; and neither node depends on the other.

1. The alpha node cleaner cleans the dirty nodes that share role alpha, completing the widget session
   after a widget source file modification and the gadget session with no workspace file
   modification.
   Observed: processing continues; the alpha-role target for widget is clean with the change summary
   from the outcome and an advanced change timestamp; and the alpha-role target for gadget is clean
   with its change timestamp unchanged.
   Realized by: `agent_storage` for the task prompts; the workspace modification state exposed by
   `sandbox`; the outcome and its change summary from `loop_driver`; and the component's own clean
   marking through `dag_storage`, which advances the change timestamp only for the node that
   modified workspace files.

### Scenario 7 — Blame is recorded only against the declared feedback dependency that owns the blamed file

Given: the alpha-role target for widget is dirty and carries the task prompt "rework widget to use
the new parser"; its configured blame targets map the widget source file to the beta-role target for
widget; the beta-role target for widget is a declared feedback dependency of the alpha-role target
for widget; the alpha-role target for widget depends non-feedback on the gamma-role target for
sprocket; and the session blames the widget source file.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: the beta-role target for widget holds the feedback message with the blame explanation as
   unacted feedback and is therefore dirty, and the gamma-role target for sprocket holds no feedback
   message.
   Realized by: role configuration lookups through `agent_node_config` for the declared blame targets
   and feedback dependencies of the dirty nodes; the blame attribution in the outcome from
   `loop_driver`; and the component's own feedback delivery through `dag_storage`, addressed strictly
   to the declared feedback dependency node that owns the blamed file.

### Scenario 8 — A blamed file that matches no configured blame target leaves the node dirty

Given: the alpha-role target for widget is dirty and carries the task prompt "rework widget to use
the new parser"; its configured blame targets map the widget source file to the beta-role target for
widget; and the session blames the sprocket source file, which no configured blame target maps.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: no feedback message is recorded for any node, and the alpha-role target for widget is
   still dirty.
   Realized by: the blame target lookups through `agent_node_config`, which find no mapping for the
   sprocket source file; the blame attribution in the outcome from `loop_driver`; and the component's
   own refusal to record feedback, which leaves the node dirty in `dag_storage`.

### Scenario 9 — A dirty node that defines no task prompt resolves without a session phase

Given: the alpha-role target for widget is dirty and defines no task prompt; the gamma-role target
for sprocket changed at 2026-01-03T04:05:06Z and its change message "sprocket emits metric suffixes"
is an incoming pending message of the alpha-role target for widget; and the alpha-role target for
gadget is dirty, defines no task prompt, and has no incoming pending message.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: no agent session phase is established; the alpha-role target for widget is clean with
   the change summary "sprocket emits metric suffixes"; the alpha-role target for gadget is clean
   with no change summary; and processing continues.
   Realized by: `agent_storage` for the node definitions, whose task prompts are absent;
   `agent_node_config` for the session messages of each file; and the component's own prompt-less
   resolution, which marks both nodes clean through `dag_storage` without establishing a session
   phase.

### Scenario 10 — An unexpected execution failure is logged and retried once before it propagates

Given: the alpha-role target for widget is dirty and carries the task prompt "rework widget to use
the new parser", and the session phase fails unexpectedly on its first attempt and again on its
retry.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: the failure is logged through the runner logger on both attempts, the session phase is
   attempted exactly twice, an explicit error is propagated, and the alpha-role target for widget is
   still dirty.
   Realized by: `runner_logger` for the logged failure; the component's own retry of the session
   phase; and the component's own propagation of the second failure, which leaves the node dirty in
   `dag_storage`.
