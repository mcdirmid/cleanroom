# Guide: Converting an LLS to Tests (without reading the implementation)

---

## Overview

Tests are written from the LLS alone. The implementation Python file is **deliberately not consulted**: the LLS is the contract, and tests written independently of the implementation catch implementation drift. If a test written from the LLS fails, the implementation is wrong — unless the test misread the LLS.

The authoritative reference for the LLS side is `low_level_spec.md`. This guide is the conversion procedure from an implementation LLS (plus the interface LLS and dependency LLSs listed in its dependency comment) to a test module in `tests/` and its BUILD entry. For the implementation side of the same contract, see `low_to_impl.md`; both sides are written from the same LLS and pass when both conform.

**Test only what the LLS requires.** The LLS requires: postconditions, invariants, and expected failures (the failure signals it names). It does not require internal mechanisms, exact message wording, unspecified ordering, or behavior outside the contract. Testing anything the LLS does not require tests the implementation rather than the contract — it couples the tests to code the LLS leaves free. When in doubt, do not test it. Non-concerns and unexpected failures that are not explicitly listed as concerns are **extremely discouraged** and require an explicit, documented reason.

## Reading the LLS

Read the implementation LLS and the full **transitive closure of its dependencies**: every LLS in its dependency comment, every LLS in *their* dependency comments, and so on until no new LLS files remain. The closure matters because dependency mocks must implement the dependency interfaces exactly (signatures, defaults, failure signals) from their own LLSs, and those dependencies may themselves depend on further interfaces.

Extract the testable claims:

| LLS section | What to test |
|---|---|
| Data Types | Construction, field names/types/order, defaults, `Literal` discriminators |
| Config | Field presence, defaults, wiring of dependency mocks |
| Behavioral Description | Each bullet → one or more outcome tests |
| Failure Handling | Each **expected** failure signal → a test |
| Invariants | Sequence-of-operations tests |
| Non-Concerns | Pinned choices (test the pin); open choices (do not test — extremely discouraged) |
| Preconditions | Not tested directly — verified through the mocks, which enforce them (see Mocks) |

Do not read the implementation Python file. Do not read the HLS: the LLS is self-contained and is the only contract tests need.

## Test Module Layout

One test module per implementation LLS, named `<name>_test.py` in `tests/`:

- `specs/csv_inventory_impl-low.md` → `tests/csv_inventory_impl_test.py`

Use `unittest` with `if __name__ == "__main__": unittest.main()` at the end. Group tests into classes by concern (success routing, failure handling, invariants, config).

## What to Test, Section by Section

### Data Types

- Construct each dataclass with the LLS's fields; assert field values, types, and defaults.
- Assert `Literal` discriminators where the LLS declares them — they are part of the interface.
- Exercise values through the interface's Protocol type, not through implementation-only attributes.

### Config

- Construct the implementation with the LLS's Config dataclass; assert the documented defaults.
- Wire dependency mocks through Config and assert they are actually used (see Mocks).

### Behavioral Description

Convert each bullet into assertions:

| LLS outcome statement | Test assertion |
|---|---|
| "Provides the current stock level (zero if none)" | Call with a missing/empty SKU; assert the return value |
| "Adds the given quantity and persists" | Call; assert the return and the observable state (re-read through a fresh instance) |
| "A write that fails before the replacement leaves the previous file unchanged" | Force the failure (read-only directory, or a patched replace step); assert the previous state is intact |
| "Is atomic" | Make one step fail; assert no partial state |

For stateful behavior, prefer asserting through the public operations (or a fresh instance) over poking internals.

### Failure Handling

Test only the **expected failures** — the failure signals the LLS names. Each named signal gets a test that triggers its condition and asserts the signal:

- Expected failures (policy violations, validation failures) → assert the return signal (`None`, `False`, a failure result).
- Unexpected failures (precondition violations, filesystem errors, state corruption) are **not listed as concerns and are not tested**. If the implementation LLS documents a violation response (e.g., "unknown SKUs raise an error"), asserting it is permitted — but it is documentation of a violation, not a requirement; do not go looking for more.
- Error-message wording: assert wording only when the LLS pins the string for testing (concrete strings live in implementation LLSs); otherwise assert only the signal type.

### Invariants

Test invariants as properties across sequences of operations:

- "No state persists between runs" → a fresh instance behaves freshly.
- "Errors leave the filesystem unchanged" → snapshot state before a failing operation; assert it is unchanged after.
- "All operations use resolved paths" → assert the observable effect of the resolution (a file created at the mapped location, not the virtual name).

### Non-Concerns

- Pinned non-concerns (e.g., "the fallback text is pinned to ...") → assert the pin; it is now part of the contract.
- Open non-concerns → **do not test, extremely discouraged.** No assertions about unspecified ordering, algorithm choice, representation, format, or mechanism — the LLS explicitly leaves these free, and a test that pins one rewrites the contract. If a test for an open non-concern seems necessary, the resolution is to pin the aspect in the LLS first, not to test it silently.

## Mocks

Implement the **dependency interfaces** as mocks, from their LLSs (the transitive closure read above) — never mock the system under test. The implementation LLS's dependency comment lists the interfaces it uses; each becomes a small stub that records calls, returns scripted results, and **enforces the interface's preconditions**:

```python
class FakeInventory(Inventory):
    def __init__(self) -> None:
        self._stock: Dict[Sku, Quantity] = {}
        self.calls: List[tuple] = []

    def get_stock(self, sku: Sku) -> Quantity:
        self.calls.append(("get", sku))
        if sku not in self._stock:
            raise ValueError(f"precondition violated: unknown SKU {sku}")
        return self._stock[sku]

    def add_stock(self, sku: Sku, quantity: Quantity) -> None:
        self.calls.append(("add", sku, quantity))
        self._stock[sku] = self._stock.get(sku, 0) + quantity

    def remove_stock(self, sku: Sku) -> None:
        self.calls.append(("del", sku))
        self._stock.pop(sku, None)
```

**Preconditions are enforced by the mocks, not tested directly.** A mock implements its interface's preconditions from the interface LLS and raises when the component under test violates one. A test that drives the component through a valid scenario then fails if the component ever calls a dependency with invalid input — the raise surfaces the misuse. This verifies the component uses its dependencies correctly without writing a separate precondition test (precondition violations are unexpected failures and are themselves not to be tested directly).

Use the mocks to assert both outcomes **and** interaction: which dependency operations were called, in what order, with what arguments. Recording calls is how ordering and routing guarantees get tested.

For external systems (e.g., a payment gateway), mock the boundary with realistic fixtures — patch the client constructor the implementation uses, and script responses whose shapes match the types the interface LLS declares (charges, receipts, settlement records). Enforce the boundary's preconditions the same way: raise when the component sends input the interface contract does not allow.

## The Bias Rule

Tests verify that the implementation satisfies the LLS — they are not written to accommodate the implementation:

- If a test fails, first re-read the LLS to confirm the assertion is correct. If the LLS supports it, the implementation is wrong: fix the implementation (per `low_to_impl.md`), not the test.
- Do not weaken assertions to match observed behavior; that silently rewrites the contract.
- Do not write tests by reading the implementation and transcribing its behavior; write from the LLS and let the implementation conform.
- The only legitimate test-side fixes are misreadings of the LLS: wrong signal, wrong precondition, or testing something the LLS does not require (an open non-concern or an unexpected failure).

## The BUILD File for Tests

Each test module gets a `pyright_test` target in `tests/BUILD.bazel` (macro from `//bin:pyright_library.bzl`) — the same shape as the `pyright_library` example in `low_to_impl.md`:

```python
load("//bin:pyright_library.bzl", "pyright_test")

pyright_test(
    name = "csv_inventory_impl_test",
    srcs = ["csv_inventory_impl_test.py"],
    pyright_deps = [
        "//lib:inventory",
        "//lib:csv_inventory_impl",
        "//lib:pricing",
    ],
)
```

- `pyright_deps` — every package module the test imports: the implementation under test, its interface, and any dependency interfaces the mocks implement. Each entry must be a declared `pyright_library` / `pyright_test` target.
- The macro generates `{name}_type_check` and `{name}_type_check_all` in addition to the runtime test. Missing `pyright_deps` entries appear as unresolved-import errors in the type check.

## Verification Order

1. **Type-check first**: `bazel test --test_timeout=120 //tests:<name>_type_check` — fix all pyright errors (missing imports usually mean a missing `pyright_deps` entry).
2. **Run the test**: `bazel test --test_timeout=120 //tests:<name>_test` — fix failures per the Bias Rule.
3. **Run the full suite**: `bazel test --test_timeout=120 //...` to catch cross-component regressions.

## What NOT to Test

- **Open non-concerns** — anything the LLS explicitly leaves unspecified: ordering, algorithm choice, representation, log/text format, message wording, chunk boundaries. Extremely discouraged.
- **Unexpected failures** not explicitly listed as concerns — precondition violations, filesystem errors, state corruption. The LLS names the failures it handles; everything else is outside the contract.
- **Internal mechanisms** the LLS does not state (cache internals, temporary-file write steps) — unless pinned in a Non-Concern.
- **Exact error-message wording** — unless the LLS pins the string for testing.
- **The HLS** — the LLS is the contract; the HLS carries no testable detail the LLS omits.

When a test appears to need one of these, the LLS-first response is to pin the behavior in the implementation LLS (making it a concern) or to drop the assertion — never to test unrequited behavior.

## Validation Checklist

- [ ] Test module per implementation LLS; named `<name>_test.py` in `tests/`
- [ ] Full transitive dependency closure read (no LLS dependency skipped)
- [ ] Written from the LLS only; the implementation Python file was not read
- [ ] Dataclass construction plus field/default/`Literal`-discriminator assertions from Data Types
- [ ] Every Behavioral Description bullet has a test
- [ ] Every expected failure signal (named in the LLS) has a test
- [ ] Invariants tested across operation sequences
- [ ] Pinned non-concerns asserted; open non-concerns not tested
- [ ] No tests for unexpected failures the LLS does not list as concerns
- [ ] Dependency interfaces mocked from their LLS; mocks enforce their preconditions (raise on violation) and record calls
- [ ] External boundaries mocked with fixtures aligned to the interface types, preconditions enforced
- [ ] No tests for internal mechanisms, formats, or message wording not pinned in the LLS
- [ ] Type check passes before running; all tests pass
- [ ] Failures resolved by fixing the implementation (or the LLS if it is wrong), never by weakening the tests
