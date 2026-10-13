<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-11T03:11:44Z
CHANGE: Author loop loop_node_cleaner concrete scenarios
CODE_HASH: 7d91ae4a3984
-->

# Concrete scenarios for `loop_node_cleaner` (interface)

## Scenario 1 — No dirty node shares the role

Given: no node in graph storage is dirty in role alpha, and the beta-role target for gadget is clean
with last cleaned timestamp 2026-01-02T03:04:05Z.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, and the beta-role target for gadget still carries the last cleaned
   timestamp 2026-01-02T03:04:05Z.

## Scenario 2 — One dirty node in the role, and a dirty node of another role left alone

Given: the alpha-role target for widget is dirty because its in-band source metadata is missing, the
beta-role target for gadget is dirty, and neither node depends on the other.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, the alpha-role target for widget is clean in graph storage, and
   the beta-role target for gadget is still dirty.

## Scenario 3 — Several dirty nodes sharing the role

Given: the alpha-role targets for widget, gadget, and sprocket are dirty, and none of them depends on
another.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, and all three nodes are clean in graph storage.

## Scenario 4 — A failure that another node cleaning addresses

Given: the alpha-role target for widget is dirty, cleaning it fails on the widget source file, and
the beta node cleaning also addresses the alpha-role target for widget.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing continues, and the alpha-role target for widget is still dirty.

2. The beta node cleaner cleans the dirty nodes it addresses.
   Observed: processing continues, and the alpha-role target for widget is clean in graph storage.

## Scenario 5 — A failure that no other node cleaning addresses

Given: the alpha-role target for widget is dirty, cleaning it fails on the widget source file, and no
other node cleaning addresses the widget source file.

1. The alpha node cleaner cleans the dirty nodes that share role alpha.
   Observed: processing cannot continue, and the alpha-role target for widget is still dirty.
