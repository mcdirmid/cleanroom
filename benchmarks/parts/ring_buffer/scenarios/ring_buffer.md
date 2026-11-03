# Concrete scenarios for ring_buffer interface

## Scenario 1 — Push and pop FIFO ordering

Given: A newly initialized ring buffer with default capacity 10.

1. Inspect buffer properties.
Observed: Buffer size is 0, is_empty is True, and is_full is False.

2. Push item `alpha` and item `beta`.
Observed: Both push operations return None, size is 2, and is_empty is False.

3. Pop from the buffer.
Observed: The returned item is `alpha`, and size is 1.

4. Pop from the buffer again.
Observed: The returned item is `beta`, size is 0, and is_empty is True.

## Scenario 2 — Overwrite eviction on capacity exhaustion

Given: A newly initialized ring buffer with default capacity 10.

1. Push 10 distinct items from `item_0` through `item_9`.
Observed: Size is 10, is_full is True, and each push returns None.

2. Push item `item_10` into the full buffer.
Observed: The returned evicted item is `item_0`, size remains 10, and is_full is True.

3. Pop from the buffer.
Observed: The returned item is `item_1` (the oldest surviving item).

## Scenario 3 — Popping empty buffer raises buffer empty error

Given: A newly initialized ring buffer.

1. Pop an item from the empty buffer.
Observed: A buffer empty error is raised.

## Scenario 4 — Clearing buffer

Given: A ring buffer containing 3 items.

1. Clear the buffer.
Observed: Size becomes 0, is_empty is True, and is_full is False.

2. Pop from the buffer.
Observed: A buffer empty error is raised.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:25:00Z
LAST_CHANGED: 2026-10-30T19:25:00Z
CHANGE: Author ring_buffer interface concrete scenarios
-->
