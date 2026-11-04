# Concrete scenarios for vault interface

## Scenario 1 — Deposit and withdraw funds in active vault

Given: A newly initialized active vault.

1. Inspect vault balance and status.
Observed: Balance is 0 and is_active is True.

2. Deposit 50 units into the vault.
Observed: Balance becomes 50.

3. Withdraw 20 units from the vault.
Observed: Balance becomes 30.

## Scenario 2 — Reject non-positive amounts and excessive withdrawals

Given: An active vault with balance 30.

1. Deposit 0 units into the vault.
Observed: An insufficient funds error is raised.

2. Withdraw 50 units from the vault.
Observed: An insufficient funds error is raised.

## Scenario 3 — Inactive vault rejects transactions

Given: A vault with balance 30 configured as inactive.

1. Deposit 10 units into the vault.
Observed: A vault inactive exception is raised.

2. Withdraw 10 units from the vault.
Observed: A vault inactive exception is raised.

## Scenario 4 — Seeding deposits and availability

Given: A vault state machine or fake.

1. Seed deposit of 100 units and seed active to True.
Observed: Balance becomes 100 and is_active is True.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-03T23:55:00Z
LAST_CHANGED: 2026-11-03T23:55:00Z
CHANGE: Initial creation of vault scenarios
-->
