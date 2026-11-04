# Concrete scenarios for inter_interface_impl implementation

## Reused from the interface

### Scenario 1 — Allocate and release funds coordinating with collaborator vault

Given: An allocator with an active collaborator vault having balance 100.

1. Inspect initial allocated funds.
Observed: Allocated funds is 0.
Realized by: Querying underlying allocated field.

2. Allocate 40 units of funds.
Observed: Allocated funds becomes 40, and collaborator vault balance becomes 60.
Realized by: Delegating withdrawal to the collaborator vault and adding amount to allocated counter.

3. Release 15 units of funds.
Observed: Allocated funds becomes 25, and collaborator vault balance becomes 75.
Realized by: Delegating deposit to the collaborator vault and subtracting amount from allocated counter.

### Scenario 2 — Reject non-positive amounts and excessive release

Given: An allocator with allocated funds 25 and active collaborator vault.

1. Allocate 0 units of funds.
Observed: An allocation limit error is raised.
Realized by: Checking positive amount precondition and raising allocation limit error.

2. Release 50 units of funds.
Observed: An allocation limit error is raised.
Realized by: Checking amount against allocated counter and raising allocation limit error.

### Scenario 3 — Inactive collaborator vault raises vault inactive exception

Given: An allocator with collaborator vault configured as inactive.

1. Allocate 10 units of funds.
Observed: A vault inactive exception is raised.
Realized by: Catching or propagating vault inactive exception from collaborator vault.

2. Release 10 units of funds.
Observed: A vault inactive exception is raised.
Realized by: Catching or propagating vault inactive exception from collaborator vault.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:55:00Z
LAST_CHANGED: 2026-11-03T23:55:00Z
CHANGE: Initial creation of inter_interface_impl scenarios
-->
