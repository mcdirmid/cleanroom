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

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:40:00Z
CHANGE: Define pending_impl concrete scenarios
-->
