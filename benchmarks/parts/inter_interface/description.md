# inter_interface

The `inter_interface` benchmark evaluates Pretense state machine synthesis and verification for inter-interface requirements, cross-interface state queries, and outcome assertions across collaborator components with dynamic seeding.

## Architecture

The benchmark contains two interface components and two concrete implementation components:

1. **`vault`**: Defines the abstract `Vault` protocol and operational error models (`VaultError`, `InsufficientFundsError`, `VaultInactiveException`) for managing bounded funds and service availability.
2. **`vault_impl`**: Realizes the concrete vault service maintaining balance and active state.
3. **`inter_interface`**: Defines the abstract `Allocator` protocol and error hierarchy (`AllocatorError`, `AllocationLimitError`), coordinating with `vault` to allocate and release funds based on collaborator state models.
4. **`inter_interface_impl`**: Realizes the concrete allocator service delegating balance adjustments to the collaborator vault singleton.

## Inter-Interface State Contracts

The benchmark exercises core Pretense inter-interface capabilities:
- Interface state machines expressing requirements against collaborator state models (`sut_state(VaultState).is_active`, `sut_state(VaultState).balance >= amount`).
- Interface state machines asserting outcomes on collaborator instances (`sut(Vault).balance == ...`).
- Collaborator seeding transitions (`seed_deposit`, `seed_active`) dynamically populating blank collaborator state during fuzz testing without static pre-seeding.
