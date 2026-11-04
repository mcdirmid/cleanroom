# Concrete scenarios for vault_impl implementation

## Reused from the interface

### Scenario 1 — Deposit and withdraw funds in active vault

Given: A newly initialized active vault.

1. Inspect vault balance and status.
Observed: Balance is 0 and is_active is True.
Realized by: Querying underlying balance and active state fields.

2. Deposit 50 units into the vault.
Observed: Balance becomes 50.
Realized by: Adding deposit amount to the internal balance counter.

3. Withdraw 20 units from the vault.
Observed: Balance becomes 30.
Realized by: Subtracting withdrawal amount from the internal balance counter.

### Scenario 2 — Reject non-positive amounts and excessive withdrawals

Given: An active vault with balance 30.

1. Deposit 0 units into the vault.
Observed: An insufficient funds error is raised.
Realized by: Checking amount positive precondition and raising insufficient funds error.

2. Withdraw 50 units from the vault.
Observed: An insufficient funds error is raised.
Realized by: Checking amount against balance and raising insufficient funds error.

### Scenario 3 — Inactive vault rejects transactions

Given: A vault with balance 30 configured as inactive.

1. Deposit 10 units into the vault.
Observed: A vault inactive exception is raised.
Realized by: Checking active state flag and raising vault inactive exception.

2. Withdraw 10 units from the vault.
Observed: A vault inactive exception is raised.
Realized by: Checking active state flag and raising vault inactive exception.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:55:00Z
LAST_CHANGED: 2026-11-03T23:55:00Z
CHANGE: Initial creation of vault_impl scenarios
-->
