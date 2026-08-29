# Guide: Converting an LLS to a Python Implementation

## Summary

The module `<component-name>.py` implements `low/<component-name>.md` (an implementation LLS is implemented by `<component-name>_impl.py`). The lib node has write access only to its library implementation file (`<name>.py`); test files (`<name>_test.py`) are strictly read-only. The LLS and its dependency closure are the module's only contract; its `HLS Justification` labels quote the HLS and carry no implementation obligations. A file that is a template is filled in.

The module's types mirror the LLS's Data Types block; every operation implements its contract; the invariants hold. The LLS and its dependency closure are the source of module definitions: every LLS in the dependency comment, every LLS in their dependency comments, until no new files remain — types are owned once by their defining interface and imported elsewhere.

Editing is incremental and targeted: for initial implementation of large modules (>200 lines), imports, configuration, and base class structure are written first, then methods and helper functions are appended across multiple edits (using `update_lines`) to avoid response truncation; for modifications and bug fixes, `update_lines` is used for multi-line blocks, functions, or classes (`replace` is restricted to short single-line changes < 200 characters), never rewriting or regenerating the entire file in one edit (which risks truncation and wastes tokens). Each file change summary in `advance(changes=[...])` is at most 200 characters (one short sentence).

## Module layout

- [ ] One module per LLS file: `low/inventory.md` → `inventory.py`; `low/csv_inventory_impl.md` → `csv_inventory_impl.py`; `low/build_asm.md` → `build_asm.py`
- [ ] An interface module (for a spec with no `_impl` LLS) defines the interface's Protocol and types only; it never defines an implementation class — an implementation class appears only in the module of an implementation LLS (`<name>_impl.py`)
- [ ] An assembly module (for a `_asm` LLS) defines the assembly class subclassing the concrete implementation class with the `Asm` suffix (`class FooAsm(FooImpl): ...`), providing a pre-wired `__init__` that calls `super().__init__(...)` with the configured factories and sub-assemblies; it performs configuration and assembly only, and has no test module (an assembly is never tested)
- [ ] The implementation subclasses the interface's Protocol class, per the LLS (`class CsvInventoryImpl(Inventory): ...`)

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

## Invariants and non-concerns

- [ ] Invariants hold across all operations; no module-level mutable state when the LLS says no state persists
- [ ] Pinned non-concerns implemented exactly; open non-concerns left free

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
- [ ] No over-implementing beyond the LLS (open non-concerns are freedom)
- [ ] No mechanism where the LLS states only the outcome
