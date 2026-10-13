<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T03:11:43Z
CHANGE: Author loop loop concrete scenarios
CODE_HASH: 5994d14ea6b8
-->

# Concrete scenarios for `loop` (interface)

## Scenario 1 — A cleaning pass over a subgraph that is already clean

Given: the alpha-role target for widget, the beta-role target for gadget, and the gamma-role target
for sprocket are clean in graph storage with last cleaned timestamps 2026-01-02T03:04:05Z,
2026-01-02T03:04:05Z, and 2026-01-03T04:05:06Z; and the alpha-role target for widget depends on the
beta-role target for gadget, which depends on the gamma-role target for sprocket.

1. The caller runs a cleaning pass rooted at the alpha-role target for widget.
   Observed: a build result reporting success and carrying a summary of the pass; and all three nodes
   keep the last cleaned timestamps 2026-01-02T03:04:05Z, 2026-01-02T03:04:05Z, and
   2026-01-03T04:05:06Z.

## Scenario 2 — A cleaning pass over a dirty dependency and the node that depends on it

Given: the beta-role target for gadget is dirty because its in-band source metadata is missing, the
alpha-role target for widget is dirty because the beta-role target for gadget changed at
2026-01-03T04:05:06Z, the alpha-role target for widget depends on the beta-role target for gadget,
and the cleaning pass runs at 2026-01-04T05:06:07Z.

1. The caller runs a cleaning pass rooted at the alpha-role target for widget.
   Observed: a build result reporting success; the beta-role target for gadget is clean with the last
   cleaned timestamp 2026-01-04T05:06:07Z; and the alpha-role target for widget is clean with the
   change message describing how the beta-role target for gadget changed.

## Scenario 3 — Marking a subgraph clean materializes a missing source file

Given: the alpha-role target for widget is dirty and holds the unacted feedback message "widget reads
sprocket output before it is flushed"; the beta-role target for sprocket has no source artifact on
disk and declares the starter template for a sprocket artifact; the gamma-role target for gadget is
clean with the change summary "gadget emits metric names"; and the alpha-role target for widget
depends on the beta-role target for sprocket and on the gamma-role target for gadget.

1. The caller marks the subgraph rooted at the alpha-role target for widget clean.
   Observed: the beta-role target for sprocket holds the source artifact materialized from its
   declared template and is clean with an initialized last cleaned timestamp and the default change
   description; the alpha-role target for widget is clean with no unacted feedback and no dirty tag;
   the gamma-role target for gadget keeps the change summary "gadget emits metric names"; and every
   node reachable from the alpha-role target for widget is clean.

## Scenario 4 — Marking a target node dirty

Given: the alpha-role target for widget is clean with last cleaned timestamp 2026-01-02T03:04:05Z and
change summary "widget uses the new parser"; and the gamma-role target for sprocket is clean with
last cleaned timestamp 2026-01-02T03:04:05Z and does not depend on the alpha-role target for widget.

1. The caller marks the alpha-role target for widget dirty with the reason "the beta-role contract
   changed".
   Observed: the alpha-role target for widget is dirty, its in-band source metadata carries no last
   cleaned timestamp and records the reason "the beta-role contract changed", and its change summary
   "widget uses the new parser" is unchanged; and the gamma-role target for sprocket is still clean.

## Scenario 5 — Recording a change message invalidates the non-silent dependents

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

## Scenario 6 — Injecting a feedback message and acting on it

Given: the beta-role target for sprocket is clean with last cleaned timestamp 2026-01-02T03:04:05Z,
and the alpha-role target for widget depends on it.

1. The caller injects the feedback message "widget reads sprocket output before it is flushed" into
   the beta-role target for sprocket.
   Observed: the beta-role target for sprocket is dirty and holds that feedback message as unacted
   feedback in its in-band source metadata.

2. The caller marks the subgraph rooted at the beta-role target for sprocket clean.
   Observed: the beta-role target for sprocket is clean with no unacted feedback.

## Scenario 7 — Injecting an empty feedback message

Given: the beta-role target for sprocket is clean with last cleaned timestamp 2026-01-02T03:04:05Z.

1. The caller injects an empty feedback message into the beta-role target for sprocket.
   Observed: the beta-role target for sprocket is dirty and holds an unacted feedback message.
