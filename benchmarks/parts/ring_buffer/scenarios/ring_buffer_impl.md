# Concrete scenarios for ring_buffer_impl implementation

## Reused from the interface

### Scenario 1 — Push and pop FIFO ordering

Given: A newly initialized ring buffer with default capacity 10.

1. Inspect buffer properties.
Observed: Buffer size is 0, is_empty is True, and is_full is False.
Realized by: Querying underlying double-ended queue length against capacity.

2. Push item `alpha` and item `beta`.
Observed: Both push operations return None, size is 2, and is_empty is False.
Realized by: Appending items to double-ended queue tail.

3. Pop from the buffer.
Observed: The returned item is `alpha`, and size is 1.
Realized by: Popping the leftmost head item from the double-ended queue.

4. Pop from the buffer again.
Observed: The returned item is `beta`, size is 0, and is_empty is True.
Realized by: Popping the remaining leftmost head item from the double-ended queue.

### Scenario 2 — Overwrite eviction on capacity exhaustion

Given: A newly initialized ring buffer with default capacity 10.

1. Push 10 distinct items from `item_0` through `item_9`.
Observed: Size is 10, is_full is True, and each push returns None.
Realized by: Appending 10 items filling the double-ended queue to maxlen.

2. Push item `item_10` into the full buffer.
Observed: The returned evicted item is `item_0`, size remains 10, and is_full is True.
Realized by: Reading the head item `item_0` as the evicted item before queue overwrite.

3. Pop from the buffer.
Observed: The returned item is `item_1` (the oldest surviving item).
Realized by: Popping the current leftmost head item from the double-ended queue.

### Scenario 3 — Popping empty buffer raises buffer empty error

Given: A newly initialized ring buffer.

1. Pop an item from the empty buffer.
Observed: A buffer empty error is raised.
Realized by: Checking if double-ended queue is empty and raising buffer empty error.

### Scenario 4 — Clearing buffer

Given: A ring buffer containing 3 items.

1. Clear the buffer.
Observed: Size becomes 0, is_empty is True, and is_full is False.
Realized by: Invoking clear on the internal double-ended queue.

2. Pop from the buffer.
Observed: A buffer empty error is raised.
Realized by: Detecting empty queue state and raising buffer empty error.

## Implementation-only

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:25:00Z
LAST_CHANGED: 2026-10-30T19:25:00Z
CHANGE: Author ring_buffer_impl implementation concrete scenarios
-->
