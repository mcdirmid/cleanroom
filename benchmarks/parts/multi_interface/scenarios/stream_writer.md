# Concrete scenarios for stream_writer interface

## Scenario 1 — Write payloads and track written count

Given: A newly initialized stream writer.

1. Inspect initial written count.
Observed: Written count is 0.

2. Write payload "msg1".
Observed: Written count becomes 1.

3. Write payload "msg2".
Observed: Written count becomes 2.

## Scenario 2 — Reject empty payload

Given: A stream writer with written count 2.

1. Write empty payload "".
Observed: A payload empty error is raised.

## Scenario 3 — Clearing stream resets written count

Given: A stream writer with written count 2.

1. Clear stream.
Observed: Written count becomes 0.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:55:00Z
LAST_CHANGED: 2026-11-03T23:55:00Z
CHANGE: Initial creation of stream_writer scenarios
-->
