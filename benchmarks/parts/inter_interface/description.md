# inter_interface

The `inter_interface` benchmark evaluates Pretense state machine synthesis and verification for inter-interface requirements, cross-interface state queries, and outcome assertions across collaborator components with dynamic seeding, virtually contracted operational exceptions (`require_env`), and collaborator state binding (`self.bind`).

## Architecture

The benchmark contains two interface components and two concrete implementation components:

1. **`vault`**: Defines the abstract `Vault` protocol and operational error models (`VaultError`, `InsufficientFundsError`, `VaultInactiveException`) for managing bounded funds and service availability.
2. **`vault_impl`**: Realizes the concrete vault service maintaining balance and active state.
3. **`inter_interface`**: Defines the abstract `Allocator` protocol and error hierarchy (`AllocatorError`, `AllocationLimitError`), coordinating with `vault` to allocate and release funds based on collaborator state models.
4. **`inter_interface_impl`**: Realizes the concrete allocator service delegating balance adjustments to the collaborator vault singleton.

## Inter-Interface State Contracts & Exception Verification

The benchmark exercises core Pretense inter-interface capabilities:
- Interface state machines expressing requirements against collaborator state models (`sut_state(VaultState).is_active`, `sut_state(VaultState).balance >= amount`).
- Virtually contracted operational exceptions via `require_env` in `vault`:
  - `require_env(self.state.is_active, VaultInactiveException, "vault is inactive")`
  - In `FakeVault`, raising `VaultInactiveException` when inactive.
  - In `VaultImplPseudoStateMachine`, verifying real `Vault` raises `VaultInactiveException` when inactive.
- Cross-component exception propagation and collaborator state binding (`self.bind`) in `inter_interface`:
  - `AllocatorStateMachine` defines virtual environmental state `vault_is_inactive: bool = False` with `require_env(not self.state.vault_is_inactive, vault.VaultInactiveException, "vault is inactive")`.
  - `AllocatorImplPseudoStateMachine` binds virtual state dynamically: `self.bind("vault_is_inactive", lambda: not sut_state(VaultState).is_active)`.
  - During implementation verification, collaborator seeding transitions (`FakeVault.seed_inactive`) induce collaborator faults that propagate through `self.bind` to verify SUT exception handling.
- Collaborator seeding transitions (`seed_deposit`, `seed_inactive`) dynamically populating blank collaborator state during fuzz testing without static pre-seeding.
