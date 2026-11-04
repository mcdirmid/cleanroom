# Concrete scenarios for multi_interface_impl implementation

## Reused from the interface

### Scenario 1 — Inspect and read items from populated stream

Given: A stream buffer containing two buffered items "alpha" and "beta".

1. Inspect unread count and has data.
Observed: Unread count is 2 and has_data is True.
Realized by: Checking length of internal buffered items list.

2. Read an item.
Observed: Returned item is "alpha", unread count becomes 1, and has_data is True.
Realized by: Popping the head element from internal buffered items list.

3. Read an item.
Observed: Returned item is "beta", unread count becomes 0, and has_data is False.
Realized by: Popping the remaining element from internal buffered items list.

### Scenario 2 — Read from empty stream

Given: An empty stream buffer with unread count 0.

1. Inspect unread count and has data.
Observed: Unread count is 0 and has_data is False.
Realized by: Checking length of empty internal buffered items list.

2. Read an item.
Observed: Returned item is None.
Realized by: Returning None when internal buffered items list is empty.

### Scenario 3 — Write payloads and track written count

Given: A newly initialized stream buffer.

1. Inspect initial written count.
Observed: Written count is 0.
Realized by: Querying underlying written count field.

2. Write payload "msg1".
Observed: Written count becomes 1 and unread count becomes 1.
Realized by: Appending payload to internal list and incrementing written counter.

3. Write payload "msg2".
Observed: Written count becomes 2 and unread count becomes 2.
Realized by: Appending payload to internal list and incrementing written counter.

### Scenario 4 — Reject empty payload

Given: A stream buffer with written count 2.

1. Write empty payload "".
Observed: A payload empty error is raised.
Realized by: Checking payload non-empty precondition and raising payload empty error.

### Scenario 5 — Clearing stream resets written count

Given: A stream buffer with written count 2 and 2 buffered payloads.

1. Clear stream.
Observed: Written count becomes 0 and unread count becomes 0.
Realized by: Clearing internal buffered items list and resetting written counter to zero.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:55:00Z
LAST_CHANGED: 2026-11-03T23:55:00Z
CHANGE: Initial creation of multi_interface_impl scenarios
-->
