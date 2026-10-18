<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:40:00Z
CHANGE: Define pending interface scenarios
CODE_HASH: 8c6a84025634
-->

# Concrete scenarios for `pending` (interface)

## Scenario 1 — Tracking and clearing pending work

Given: an active role workspace with an empty pending work buffer.

1. The caller records assigned targets `["parts/agent/lib/foo.py"]` into the pending work buffer.
   Observed: `get_pending_work` returns `["parts/agent/lib/foo.py"]`.

2. The caller removes `parts/agent/lib/foo.py` upon submission.
   Observed: `get_pending_work` returns an empty sequence.

3. The caller clears the pending work buffer.
   Observed: the pending buffer file is deleted from disk.

## Scenario 2 — Evaluating pending target dirtiness

Given: an active role workspace with a pending target whose source file does not exist on disk.

1. The caller checks `is_pending_target_dirty` for the missing target.
   Observed: the method returns true, and materializes the starter template on disk.

2. The caller marks the target clean.
   Observed: `is_pending_target_dirty` returns false.

## Scenario 3 — Evaluating pending target dirtiness with projected workspace metadata

Given: an assigned pending target in a role workspace whose local header lacks `LAST_CLEANED`, while its canonical file in the main repository is clean.

1. The caller checks `is_pending_target_dirty`.
   Observed: resolves the canonical file from the main repository and returns `False`.

