# Guide: Converting an LLS to a Python Implementation

## Summary

The module `<component-name>.py` implements `low/<component-name>.md` (an implementation LLS is implemented by `<component-name>_impl.py`). The lib node has write access only to its library implementation file (`<name>.py`); test files (`<name>_test.py`) are strictly read-only. The LLS and its dependency closure are the module's only contract; its `HLS Justification` labels quote the HLS and carry no implementation obligations. A file that is a template is filled in. The files and specifications provided in context at session start are the complete and only source of truth required to implement the module.

The module's types mirror the LLS Data Types block; every operation implements its contract and invariants hold. Implementation editing is incremental and targeted, using `update_lines` for multi-line blocks, functions, or classes (`replace` is restricted to short single-line changes < 200 characters), never rewriting the entire file in one edit. When calling `advance(change_summary="...")`, the summary is at most 200 characters (one short sentence).

## Module layout

- [ ] One module per LLS file: `low/inventory.md` → `inventory.py`; `low/csv_inventory_impl.md` → `csv_inventory_impl.py`; `low/build_asm.md` → `build_asm.py`; `low/bazel_target_labels_ext.md` → `bazel_target_labels_ext.py`
- [ ] An interface module (for a spec with no `_impl` LLS) defines the interface's Protocol and types only; an external module (`<name>_ext.py`) defines shared type aliases, constants, classes, and methods to anchor external third-party dependencies; an implementation class appears only in the module of an implementation LLS (`<name>_impl.py`)
- [ ] An assembly module (for a `_asm` LLS) defines the assembly class subclassing the concrete implementation class with the `Asm` suffix (`class FooAsm(FooImpl): ...`), providing an `__init__` that takes only domain configuration parameters and directly instantiates all component `_impl` classes inside `__init__` before calling `super().__init__(...)`; concrete `_impl` classes must be instantiated inside an `_asm` class and can never be used as arguments to a constructor; it performs configuration and assembly only, and has no test module (an assembly is never tested)
- [ ] External modules (`<name>_ext.py`) and assembly modules (`<name>_asm.py`) are never tested directly (no test module exists for them)
- [ ] The implementation subclasses the interface's Protocol class, per the LLS (`class CsvInventoryImpl(Inventory): ...`); when implementing a factory protocol, the factory method instantiates an internal implementation of the created protocol (e.g. `_SandboxImpl(Sandbox)`), capturing per-invocation arguments and keeping the internal class private to the module

## Imports

- [ ] The types the module uses are imported from the LLS's Data Types block, from their owning interface, never redefined
- [ ] An implementation module (`<name>_impl.py`) or interface module must not import any implementation class (`*Impl`) or import from any implementation module (`*_impl.py`); concrete implementations are injected via constructors or protocols
- [ ] The one exception: an assembly module imports from the implementation and assembly modules it assembles (`from .build_graph_storage_impl import ...`) — the only module kind permitted to import implementation or assembly modules
- [ ] Imports use relative form for package modules (`.inventory import ...`)

## Data types

- [ ] Type aliases match the LLS's Data Types block in name and meaning; built-in spellings (`list[str]`) and `typing` spellings (`List[str]`, `TypeAlias`) are equivalent under type checking
- [ ] Dataclass field names, types, order, and defaults match the LLS exactly
- [ ] `Literal` discriminators match the LLS exactly
- [ ] The interface's type variables are resolved where the implementation LLS says so (e.g., to `str`), never left bare in the implementation

## Config

- [ ] Interface-owned config is taken directly as a single `config` parameter (no local Config type); implementation-owned config is a dataclass with exactly the LLS's fields, types, and defaults
- [ ] No Config is declared when the implementation bundles no capabilities

## Operation contracts

- [ ] Operation signatures match the LLS exactly (parameter names, types, defaults, return types)
- [ ] Expected failures use the LLS's return signals exactly (`None`, a failure result, `False`); unexpected failures propagate as exceptions unless the implementation LLS pins a response
- [ ] Ordering and routing rules in the postconditions are implemented exactly
- [ ] No behavior invented beyond the LLS; no stated behavior skipped

## Invariants

- [ ] Invariants hold across all operations; no module-level mutable state when the LLS says no state persists
- [ ] Unexpected failures propagate as unhandled exceptions; they are never masked by invented fallbacks or default values
- [ ] No unstated behavior or mechanism is invented beyond the LLS contract

## Lint checks

- [ ] Sibling-module imports use relative form within the package (`.inventory import ...`)
- [ ] Non-assembly library modules must not import any implementation class (`*Impl`) or import from any implementation module (`*_impl.py`)
- [ ] Library modules must not call `unittest.main()` (test runners belong in test modules only)
- [ ] All module imports and transitive closure are resolvable
- [ ] The package BUILD file contains the `pyright_library` target with required dependencies

## Common pitfalls

- [ ] No renamed parameters or reordered defaults (signatures copied verbatim)
- [ ] No redefined types that the LLS imports from its closure
- [ ] No raising where the LLS names a return signal
- [ ] No invented fallback for unexpected failures (unexpected failures can only raise exceptions; never swallow them into default values)
- [ ] No over-implementing beyond the LLS
- [ ] No mechanism where the LLS states only the outcome

