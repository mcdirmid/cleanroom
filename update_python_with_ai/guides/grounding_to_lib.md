# Guide: Converting Grounding Specifications to Python Library Code

## Summary

The module `<component-name>.py` implements `grounding/<component-name>.pyi` (an implementation grounding specification is implemented by `<component-name>_impl.py`). The lib node has write access only to its library implementation file (`<name>.py`); test files (`<name>_test.py`) are strictly read-only. The grounding specification and its dependency closure are the module's only contract. External boundary specifications (`grounding/<name>_ext.pyi`) have no library implementation file; their documented external mechanics, build dependencies, and usage snippets guide implementation modules that import external libraries directly. A file that is a template is filled in. The files and specifications provided in context at session start are the complete and only source of truth required to implement the module.

The module's types mirror the grounding specification's dataclasses and protocols; every operation implements its contract, invariants hold, comments identify which requirements and invariants the code covers, and unexpected failures raise unhandled exceptions. Implementation editing is incremental and targeted, using `update_lines` for multi-line blocks, functions, or classes (`replace` is restricted to short single-line changes < 200 characters), never rewriting the entire file in one edit. When calling `advance(change_summary="...")`, the summary is at most 200 characters (one short sentence).

## Module layout

- [ ] One module per grounding specification file: `grounding/widget.pyi` → `widget.py`; `grounding/widget_impl.pyi` → `widget_impl.py`; `grounding/widget_asm.pyi` → `widget_asm.py`
- [ ] External boundary specifications (`grounding/<name>_ext.pyi`) define no library implementation module (no `<name>_ext.py` file exists)
- [ ] Interface specifications defining only data types or variants without singleton services define no implementation module (no `<name>_impl.py` exists)
- [ ] An interface module (`<name>.py` for a specification with no `_impl.pyi`) defines runtime Protocol classes, dataclasses, and type aliases only; no concrete implementation class appears in an interface module
- [ ] An implementation class appears only in the module of an implementation specification (`<name>_impl.py`), sharing the exact class name from the specification and subclassing the interface Protocol and Singleton without an `Impl` suffix: `class Alpha(alpha.Alpha, Singleton):`
- [ ] Every singleton implementation class subclasses `Singleton`, declares a zero-argument constructor `def __init__(self) -> None:`, initializes its lifecycle tier (`tier = "system"` or `tier = "agent_session"`), and optionally implements `def initialize(self) -> None:` if post-construction initialization is required
- [ ] Every implementation module defines a top-level `__initialize__(registry: Optional[LifecycleRegistry] = None) -> None:` method that registers each singleton class under all inherited singleton types and the implementation class itself (`keys=[Alpha, alpha.Alpha, ...]`), with its lifecycle tier (`system` or `agent_session`)
- [ ] An implementation module implements (closes) interface components by implementing all of their declared singleton types, listing implemented interface components in `implements` and used non-implemented components in `imports`
- [ ] An assembly module (`<name>_asm.py`) defines `CONSTITUENTS` and a top-level `__initialize__(registry: Optional[LifecycleRegistry] = None) -> None:` method that recursively calls `__initialize__` on all its constituent `_impl` and `_asm` modules
- [ ] An assembly module's implemented components equal the union of its constituents' implemented components; its imported components equal the union of its constituents' imports excluding its implemented components
- [ ] A root assembly module (`<name>_asm.py`) ready for execution implements all singleton interface components and imports only external boundary (`_ext`) components and passive data types
- [ ] External specifications (`grounding/<name>_ext.pyi`) and assembly modules (`<name>_asm.py`) are never tested directly (no test module exists for them)

## Imports

- [ ] Sibling-module imports within the library package use relative form (`from .widget import Widget, WidgetConfig`)
- [ ] Every imported module and symbol is referenced in the module's AST; unused imports are prohibited
- [ ] The types the module uses are imported from their owning interface modules, never redefined
- [ ] An implementation module (`<name>_impl.py`) or interface module (`<name>.py`) must not import any implementation module (`*_impl.py`) or assembly module (`*_asm.py`); foreign collaborator singletons are accessed on demand via `get_singleton(ProtocolClass)`, while collaborator singletons defined in the same module are accessed via `get_singleton(ImplementationClass)`
- [ ] An assembly module imports only the constituent implementation and assembly modules it assembles (`from . import widget_impl, helper_asm`)
- [ ] When an implementation depends on an external boundary specification (`grounding/<name>_ext.pyi`), the third-party package documented in the external spec's docstring is imported directly

## Data types and protocols

- [ ] Passive record types are decorated with `@dataclass(frozen=True)` matching the grounding specification
- [ ] Dataclass constructor signatures (`def __init__(self, ...): ...`) match the grounding specification's parameter names, types, order, and default values exactly
- [ ] Dataclass field names, types, order, and default values match the grounding specification exactly
- [ ] Interface types are declared as `class Name(Protocol):` matching the grounding specification
- [ ] Type aliases match the grounding specification in name, generic parameters, and aliased target type
- [ ] `Literal` discriminator values match the grounding specification exactly
- [ ] Interface type variables are resolved to concrete types where the implementation specification requires, never left bare in concrete implementations

## Operation contracts

- [ ] Operation signatures match the grounding specification exactly in method name, parameter names, type annotations, defaults, and return type
- [ ] The operation implementation satisfies all postconditions documented under `FRESH_REQUIREMENTS:` and `INHERITED_REQUIREMENTS:`
- [ ] Comments in the code identify which requirements or postconditions from `FRESH_REQUIREMENTS:` and `INHERITED_REQUIREMENTS:` each code block covers, without explaining how they are covered
- [ ] The operation implementation relies on caller fulfillment of preconditions documented under `FRESH_ASSUMPTIONS:`; callee operations do not add redundant defensive validation unless explicit failure return signals are specified
- [ ] Collaborator wiring and dependencies follow the derivation instructions in `GROUNDING_ARGUMENT:` docstrings
- [ ] Expected failures return the exact signal specified in the contract (`None`, `False`, or an explicit failure record)
- [ ] No unmandated behavior is invented beyond the contract; no stated requirement is omitted

## Invariants and error handling

- [ ] Invariants hold across all operations, preserving consistency across sequential calls
- [ ] Comments in the code identify which invariants from the contract the code preserves, without explaining how they are covered
- [ ] No module-level mutable state exists when the specification states no persistent state is maintained
- [ ] Unexpected failures propagate as unhandled exceptions; they are never masked by invented fallback values, empty defaults, or suppressed errors
- [ ] External boundary calls handle documented library exceptions in accordance with the contract, converting them to specified return signals or letting them propagate

## Lint checks

- [ ] Sibling-module imports use relative form within the package (`from .widget import ...`)
- [ ] Non-assembly library modules must not import from any implementation module (`*_impl.py`) or assembly module (`*_asm.py`)
- [ ] Library modules must not call `unittest.main()` (test runners belong in test modules only)
- [ ] Library modules must not catch broad exceptions (bare 'except:', 'except Exception:', 'except BaseException:') without re-raising
- [ ] All module imports and transitive closure are resolvable
- [ ] All imported modules and symbols are referenced in the module's AST (zero unused imports)
- [ ] The package BUILD file contains the `pyright_library` target with required dependencies

## Common pitfalls

- [ ] Creating a library file for an external boundary specification (`grounding/<name>_ext.pyi` has no corresponding `.py` file)
- [ ] Creating an implementation module for a data-type-only interface specification that defines no singletons
- [ ] Unused imports — importing modules or symbols that are never referenced in the implementation's AST
- [ ] Constructor injection of collaborator singletons instead of zero-argument `__init__` and on-demand `get_singleton`
- [ ] Renaming parameters, changing parameter order, or modifying default values from the grounding signature
- [ ] Redefining types instead of importing them from their owning interface module
- [ ] Swallowing unexpected failures into default fallback values instead of allowing exceptions to propagate
- [ ] Importing implementation modules (`*_impl.py`) in non-assembly library code
- [ ] Adding unmandated defensive validation for preconditions that `FRESH_ASSUMPTIONS:` assigns to callers
- [ ] Inventing behavior, heuristics, or side effects not specified in the grounding contracts
- [ ] Omitting the singleton implementation class itself from the registered keys in `__initialize__`
- [ ] Querying a local singleton defined in the same module by interface protocol and downcasting with `isinstance` instead of querying by implementation class directly
- [ ] Omitting comments identifying which requirements or invariants are covered by code blocks
- [ ] Explaining code execution mechanics in comments rather than identifying what requirements or invariants are covered
