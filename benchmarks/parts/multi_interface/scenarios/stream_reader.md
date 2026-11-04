# Concrete scenarios for stream_reader interface

## Scenario 1 — Inspect and read items from populated stream

Given: A stream reader containing two buffered items "alpha" and "beta".

1. Inspect unread count and has data.
Observed: Unread count is 2 and has_data is True.

2. Read an item.
Observed: Returned item is "alpha", unread count becomes 1, and has_data is True.

3. Read an item.
Observed: Returned item is "beta", unread count becomes 0, and has_data is False.

## Scenario 2 — Read from empty stream

Given: An empty stream reader with unread count 0.

1. Inspect unread count and has data.
Observed: Unread count is 0 and has_data is False.

2. Read an item.
Observed: Returned item is None.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:55:00Z
LAST_CHANGED: 2026-11-03T23:55:00Z
CHANGE: Initial creation of stream_reader scenarios
-->
