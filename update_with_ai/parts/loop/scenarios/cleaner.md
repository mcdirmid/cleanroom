# Concrete scenarios for `loop_cleaner` (interface)

## Scenario 1 — A subgraph that is already clean

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are clean
with last cleaned timestamp 2026-01-02T03:04:05Z; and the supplied alpha node cleaner cleans the
dirty nodes that share role alpha.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: cleaning concludes, no node is cleaned, and both nodes keep the last cleaned timestamp
   2026-01-02T03:04:05Z.

## Scenario 2 — A dirty dependency is cleaned before the node that depends on it

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are dirty,
the beta-role target for gadget because its in-band source metadata is missing, and the alpha-role
target for widget because the beta-role target for gadget changed at 2026-01-03T04:05:06Z.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked to clean the beta-role target for gadget, which is
   clean afterwards, before it is asked to clean the alpha-role target for widget; then cleaning
   concludes with both nodes clean.

## Scenario 3 — A chain of three dirty nodes cleaned in dependency order

Given: the alpha-role target for widget depends on the beta-role target for gadget, which depends on
the gamma-role target for sprocket, and all three nodes are dirty.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked for the gamma-role target for sprocket, then for the
   beta-role target for gadget, then for the alpha-role target for widget; and cleaning concludes
   with all three nodes clean.

## Scenario 4 — A dirty node outside the target subgraph is not cleaned

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are dirty;
and the gamma-role target for sprocket is dirty but neither it nor anything it reaches is a
dependency of the alpha-role target for widget.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the beta-role target for gadget and the alpha-role target for widget are clean; the
   gamma-role target for sprocket is still dirty and was never asked of the supplied node cleaner;
   and cleaning concludes.

## Scenario 5 — A dependency between two roles of the same unit

Given: the alpha-role target for widget depends on the beta-role target for widget, and both are
dirty.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked to clean the beta-role target for widget before the
   alpha-role target for widget, and cleaning concludes with both nodes clean.

## Scenario 6 — Halting when the supplied node cleaner cannot continue

Given: the alpha-role target for widget depends on the beta-role target for gadget; both are dirty;
and the supplied alpha node cleaner communicates that processing cannot continue when it is asked to
clean the beta-role target for gadget.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: cleaning halts immediately; the beta-role target for gadget is still dirty; and the
   alpha-role target for widget was never asked of the supplied node cleaner and is still dirty.

## Scenario 7 — A dirty node whose dependency an earlier run already cleaned

Given: the alpha-role target for widget depends on the beta-role target for gadget; the beta-role
target for gadget is clean with last cleaned timestamp 2026-01-02T03:04:05Z; and the alpha-role
target for widget is dirty because the beta-role target for gadget changed at 2026-01-03T04:05:06Z.

1. The caller cleans the alpha-role target for widget using the supplied alpha node cleaner.
   Observed: the supplied node cleaner is asked only for the alpha-role target for widget, which is
   clean afterwards, and cleaning concludes without asking for the beta-role target for gadget.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:45Z
CHANGE: Author loop cleaner concrete scenarios
-->
