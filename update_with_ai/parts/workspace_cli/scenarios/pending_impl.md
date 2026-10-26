# Concrete scenarios for `pending_impl` (implementation)

## Scenario 1 — JSON buffer serialization and strictly targeted removal

Given: a workspace directory containing `.cleanroom_pending_work.json` with targets `["staging/parts/agent/lib/foo.py", "staging/parts/agent/lib/bar.py"]`.

1. The caller removes `staging/parts/agent/lib/foo.py`.
   Observed: `.cleanroom_pending_work.json` is updated on disk to contain only `["staging/parts/agent/lib/bar.py"]`.

2. The caller clears pending work.
   Observed: `.cleanroom_pending_work.json` is unlinked and absent from disk.

## Scenario 2 — Star role dependency dirty propagation for pending targets

Given: an assigned pending target `staging/parts/agent/lib/foo.py` which was cleaned at timestamp T1, and a configured star-role dependency on `high` which was modified at timestamp T2 > T1.

1. The caller checks `is_pending_target_dirty`.
   Observed: the target evaluates dirty due to the modified star-role dependency.

## Scenario 3 — Canonical lifecycle metadata inspection for pending targets

Given: an assigned pending target whose local workspace copy omits `LAST_CLEANED`, and whose canonical file in the main repository contains a valid `LAST_CLEANED` timestamp.

1. The caller checks `is_pending_target_dirty`.
   Observed: evaluates canonical lifecycle metadata from the main repository and returns `False`.

## Scenario 4 — Pending target removal across pretense, test, and impl stem variants

Given: a workspace directory containing `.cleanroom_pending_work.json` with targets `["parts/dag_engine_lite/lib/dag_engine_lite_impl.py", "parts/other/lib/other_impl.py"]`.

1. The caller removes `parts/dag_engine_lite/pretense/dag_engine_lite_impl_pretense.py`.
   Observed: `.cleanroom_pending_work.json` is updated on disk to contain only `["parts/other/lib/other_impl.py"]`.

2. The caller removes `parts/other/tests/other_impl_test.py`.
   Observed: `.cleanroom_pending_work.json` is cleared and unlinked from disk.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-25T22:36:00Z
CHANGE: Add scenario for stem normalization across pretense, test, and impl variants
-->
