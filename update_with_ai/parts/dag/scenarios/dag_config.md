<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T03:05:55Z
CHANGE: Author dag_config interface scenarios
CODE_HASH: ef336986e5ab
-->

# Concrete scenarios for `dag_config` (interface)

## Scenario 1 — Reading the traversal limits

Given: the ambient configuration supplies a node visit limit of 3 and a batch size of 2 for the
dependency graph of the build named `nightly`.

1. The caller reads the node visit limit of the `nightly` build's dependency graph.
   Observed: 3.

2. The caller reads the batch size of that dependency graph.
   Observed: 2.

## Scenario 2 — Stable limits across repeated reads

Given: the ambient configuration supplies a node visit limit of 10 and a batch size of 4.

1. The caller reads the node visit limit and the batch size twice in succession.
   Observed: both reads report 10 and 4, with no read altering the limit or the size.

## Scenario 3 — Limits recovered from a fresh configuration

Given: the configuration is replayed from the same environment that supplied a node visit limit of
7 and a batch size of 1.

1. The caller reads the node visit limit of the fresh configuration.
   Observed: 7.

2. The caller reads the batch size of the fresh configuration.
   Observed: 1.

## Scenario 4 — A system with no ambient configuration

Given: no ambient configuration is active.

1. The caller reads the node visit limit.
   Observed: the read fails explicitly rather than reporting a silent fallback limit.

2. The caller reads the batch size.
   Observed: the read fails explicitly rather than reporting a silent fallback size.
