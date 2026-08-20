# Guide: Converting an LLS to a Python Implementation

## Overview

An LLS is written to be implemented: it declares the exact types, signatures, preconditions, postconditions, failure signals, invariants, and non-concern pins the implementation must satisfy. This guide is the conversion procedure from an LLS (`specs/*-low.md`) to a Python module (`lib/`) plus its BUILD entry. The authoritative reference is `low_level_spec.md`.

The LLS is the contract: an implementation conforms when every operation satisfies its preconditions, postconditions, and failure handling, and every invariant holds. Tests are written from the same LLS (see `low_to_test.md`) **without reading the implementation**, so implementation and tests agree exactly when both conform.

## Reading the LLS

Read the LLS file and the full **transitive closure of its dependencies**: every LLS in its dependency comment, every LLS in *their* dependency comments, until no new files remain. The closure matters because types are owned once by the defining interface and imported elsewhere; honoring a dependency's preconditions and failure signals requires reading the interface that owns the types you use.

Do not read the HLS: all HLS constraints are inlined in the LLS, which is self-contained; nothing in the HLS overrides it.

Extract, per LLS section:

- **Data Types** — the exact types to declare: aliases, dataclasses, `Protocol` classes, type variables.
- **Component-Provided Operations** — signatures and the full behavioral contract per operation.
- **Invariants** — properties that must hold across all operations.
- **Implementation Config** — the constructor contract (capability bundling).
- **Behavioral Description** — how the implementation fulfills the interface.
- **Implementation Invariants** — implementation-wide guarantees.
- **Non-Concerns** — where the implementation is free to choose.

## Module Layout

One Python module per LLS file: `specs/inventory-low.md` → `lib/inventory.py` (interface); `specs/csv_inventory_impl-low.md` → `lib/csv_inventory_impl.py` (implementation); `specs/inventory_impl-low.md` → `lib/inventory_impl.py` (single-implementation interface). Implementation modules import the interface they implement and any other interface types they use, with relative imports:

```python
from .inventory import Inventory, Sku, Quantity
from .graph import Graph
```

## Translating Data Types

- **Type aliases** — mirror exactly (`Sku = str`). `typing` spellings (`List[str]`, `Optional[X]`) are equivalent to built-in spellings (`list[str]`, `X | None`) under type checking; match the LLS's meaning, not its casing.
- **Protocol classes** — the interface's operations become the Protocol's methods; the implementation subclasses it: `class CsvInventoryImpl(Inventory): ...`.
- **Dataclasses** — mirror field names, types, order, and defaults exactly, including `Literal` discriminators: they are part of the interface and tests may assert them.
- **Type variables** — the interface declares `T`; the implementation resolves it where the implementation LLS says so (e.g., "resolves `T` to `str`"), annotating concrete signatures accordingly (`LedgerError[str]`); never leave a bare unresolved `T` in the implementation.
- **Imports** — import owned types from their owning interface; never redefine a type the interface owns.

## Translating Config

Config is a constructor contract. Interface-owned config is typed in the interface's Data Types (`InventoryConfig`); the implementation takes it directly, with no local Config type. Implementation-owned config is declared as a dataclass with exactly the LLS's listed fields, types, and defaults. An implementation that bundles no capabilities declares no Config.

## Translating Operations

For each operation in the interface LLS:

1. **Signature** — copy it exactly: parameter names, types, defaults, return type. The Protocol method signature is the contract; tests call it by these names.
2. **Preconditions** — caller obligations. The implementation need not check them and is not required to define the violation behavior — unless the implementation LLS documents a response (e.g., "unknown SKUs raise an error"); implement that, otherwise leave the behavior free.
3. **Postconditions** — the guarantees to satisfy: return values, state changes, ordering, atomicity. These are the assertions tests will make.
4. **Failure handling** — expected failures (validation failures, policy violations) are return-value signals; implement exactly the signal the LLS names (`None`, a failure result, `False`). Unexpected failures (filesystem errors, state corruption) are not contracted; let them propagate as exceptions unless the implementation LLS pins a response.
5. **Ordering and routing rules** in the postconditions — implement them exactly (e.g., "delete occurs only after successful processing").

## Translating the Behavioral Description

The Behavioral Description states outcomes ("Provides the current stock levels...", "A write that fails before the replacement leaves the previous file unchanged"). Implement each bullet directly. Do not invent behavior the LLS does not state; do not skip stated behavior. When the description says an operation "is atomic," make the state change all-or-nothing.

## Translating Invariants

Invariants hold across all operations. Encode them as class-level guarantees (e.g., "no state persists between runs" → no module-level mutable state; construct all state in the instance).

## Translating Non-Concerns

Non-Concerns mark freedom: do not add constraints the LLS deliberately left open. A **pinned** non-concern (e.g., "the fallback text is pinned to ...") must be implemented exactly, because tests may assert the pin.

## The BUILD File

Each module gets one `pyright_library` target (from `//bin:pyright_library.bzl`) in the package's `BUILD.bazel`:

```python
load("//bin:pyright_library.bzl", "pyright_library")

pyright_library(
    name = "csv_inventory_impl",
    srcs = ["csv_inventory_impl.py"],
    pyright_deps = [":inventory", ":pricing"],
    visibility = ["//visibility:public"],
)
```

- `srcs` — the single Python file (one module per target).
- `pyright_deps` — every package module this file imports, including the interface it implements; each entry must itself be a `pyright_library` target. Transitive sources flow through the macro's `_all_srcs` filegroups, so listing direct imports suffices.
- `deps` — third-party runtime packages only (pip requirements macro). Package-internal modules belong in `pyright_deps`, which the macro adds to both runtime and type-check deps.
- `visibility` — `//visibility:public` so tests and assembler implementations can depend on it.

The macro generates `{name}_srcs`, `{name}_all_srcs`, `{name}` (runtime library), `{name}_type_check` (pyright test), and `{name}_type_check_all` (a suite that also runs every dependency's type check). A missing `pyright_deps` entry shows up as an unresolved-import error in the type check.

Type-check a module: `bazel test --test_timeout=120 //lib:<name>_type_check`.

## Verification

1. **Type-check first**: `bazel test --test_timeout=120 //lib:<name>_type_check` — fix all pyright errors before running anything.
2. **Then run the corresponding test** (see `low_to_test.md`): `bazel test --test_timeout=120 //tests:<name>_test`.
3. If a test fails, the LLS is the source of truth: fix the implementation. If the LLS is genuinely wrong, fix the LLS — never silently change the test.

## Common Pitfalls

Pitfall — Example — Fix.

- Resolving interface type variables — leaving `T` unresolved in the implementation — Resolve per the implementation LLS.
- Signature drift — renamed parameters or reordered defaults — Copy signatures verbatim; tests assert them.
- Inventing failure signals — raising where the LLS names a return signal — Use the LLS's signal exactly.
- Over-implementing — adding behavior the LLS does not state — Open non-concerns are freedom; the contract is the LLS.
- Missing BUILD deps — an imported module absent from `pyright_deps` — List every imported package module.
- Mechanism vs outcome — building a cache where the LLS states only the result — Implement the outcome; internals are free unless pinned.

## Validation Checklist

- [ ] One module per LLS file; module name matches the spec name
- [ ] Full transitive dependency closure read (no LLS dependency skipped)
- [ ] Implementation subclasses the interface's Protocol (`class CsvInventoryImpl(Inventory): ...`)
- [ ] Dataclass fields, types, order, defaults, and `Literal` discriminators match the LLS exactly
- [ ] Operation signatures match the LLS exactly (parameter names, types, defaults, return types)
- [ ] Type variables resolved per the implementation LLS
- [ ] Expected failures use the LLS's return signals; unexpected failures propagate
- [ ] Invariants hold across all operations
- [ ] Pinned non-concerns implemented exactly; open non-concerns left free
- [ ] Config declared per the implementation LLS (capability bundling) or the interface-owned type used directly
- [ ] BUILD: one `pyright_library` per module; `pyright_deps` lists every imported package module; `deps` only third-party runtime packages
- [ ] Type check passes; the corresponding LLS-written tests pass
- [ ] No HLS consulted; the LLS was sufficient
