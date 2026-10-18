<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:15:00Z
CHANGE: Define dirtiness interface scenarios
CODE_HASH: 76ef5e0369ab
-->

# Concrete scenarios for `dirtiness` (interface)

## Scenario 1 — Evaluating producer unit dirtiness across implicit and star dependencies

Given: a part directory containing a producer target cleaned at timestamp T1, and an upstream specification contract modified at timestamp T2 > T1.

1. The caller evaluates unit dirtiness via `evaluate_unit_dirty`.
   Observed: returns dirty status `True` with reasons identifying the newer upstream specification modification.

2. The caller resolves companion specification contracts via `resolve_contract_files`.
   Observed: returns the upstream specification contracts while suppressing peer implementation files and silent cross-role dependencies.

## Scenario 2 — Evaluating auditor unit dirtiness across feedback targets

Given: an auditor role unit whose audited target is missing an in-band audit certification.

1. The caller evaluates unit dirtiness via `evaluate_unit_dirty`.
   Observed: returns dirty status `True` with reasons indicating uncertified target status.

## Scenario 3 — Companion interface pairing and multi-tier role ancestry inheritance

Given: an implementation unit ending in `_impl` whose immediate upstream role lacks active component type mapping, but whose ancestor role does.

1. The caller evaluates unit dirtiness via `evaluate_unit_dirty`.
   Observed: traverses upstream role ancestry to inspect the ancestor contract, pairs the companion interface contract, and reports dirtiness accordingly.

2. The caller resolves companion specification contracts via `resolve_contract_files`.
   Observed: returns the companion interface contract without the `_impl` suffix.

## Scenario 4 — Evaluating unit dirtiness with projected role workspace metadata

Given: a role workspace containing a projected target file whose metadata header omits `LAST_CLEANED`, and whose canonical file in the main repository has a valid `LAST_CLEANED` timestamp and unchanged dependencies.

1. The caller evaluates unit dirtiness via `evaluate_unit_dirty`.
   Observed: inspects canonical lifecycle metadata from the main repository, determines the unit is not dirty, and reports dirty status `False`.

