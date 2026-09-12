# Guide: Converting Grounding Specifications to Python Library Code

## Summary

The module `<name>.py` implements `<name>.pyi`. The lib node has write access only to its library implementation file (`<name>.py`); test files (`<target_impl>_test.py`) are strictly read-only. The grounding specification and its dependency closure are the module's only contract. External boundary specifications (`<name>_ext.pyi`) have no library implementation file; their documented external mechanics, build dependencies, and usage snippets guide implementation modules that import external libraries directly. A file that is a template is filled in. If the pre-existing file already satisfies all contracts and constraints, no edits are made. The files and specifications provided in context at session start are the complete and only source of truth required to implement the module.

The module defines clean Python runtime types and implementations realizing the grounding specification's contracts: dataclasses declare fields as typed class-level attributes without stub constructors (`__init__`) or property getters (`@property`), interface protocols declare operation signatures, and specification framework decorators (`@data_type`, `@operation`, `@singleton_type`) and specification docstrings (`PURPOSE:`, `FRESH_REQUIREMENTS:`, `GROUNDING_ARGUMENT:`, `INHERITED_REQUIREMENTS:`, `INHERITED_ASSUMPTIONS:`) are omitted; copying specification docstrings into implementation files is prohibited. Implementation classes share the exact class name declared in the grounding specification (subclassing the interface Protocol and Singleton: `class Alpha(alpha.Alpha, Singleton):`), with zero-argument `__init__`, and are registered in `__initialize__`. Operations implement their contracts, invariants hold, comments cite exact requirements verbatim (`# Requirement: <exact text>`), unexpected failures raise unhandled exceptions, and inventing unmandated behavior, stubs, or retaining dead code is prohibited. Implementation editing is incremental and targeted, using `update_lines` for multi-line blocks or classes (`replace` is restricted to short single-line changes < 200 characters), never rewriting unchanged files or replacing clean dataclass attributes with specification stubs. The search tool is never installed.

> META: "Library implementation files realize grounding specifications directly; contracts and requirement docstrings are never copied into the implementation."

## Verification failure

- [ ] Diagnostics from a failed verification are addressed surgically in the writable library file without whole-file rewrites or modifying unreferenced code
- [ ] If verification failure reports test failures or type errors, edits target only the specific failing functions or classes cited in the diagnostic output
- [ ] Calling the fail tool is restricted to defects that cannot be resolved within the writable library file (e.g. invalid specification requirements); the fail tool is never called for fixable local syntax, typing, or logic errors
- [ ] Calling advance without modifying workspace files repeats the previous failure; files must be updated before calling advance again

## Module layout

- [ ] One module per grounding specification file: `widget.pyi` → `widget.py`; `widget_impl.pyi` → `widget_impl.py`; `widget_asm.pyi` → `widget_asm.py`
- [ ] External boundary specifications (`<name>_ext.pyi`) define no library implementation module (no `<name>_ext.py` file exists)
- [ ] Interface specifications defining only data types or variants without singleton services define no implementation module (no `<name>_impl.py` exists)
- [ ] An interface module (`<name>.py` for a specification with no `_impl.pyi`) defines runtime Protocol classes, standard dataclasses, and type aliases only; no concrete implementation class, specification framework decorator, or specification docstring appears in an interface module
- [ ] An implementation class appears only in the module of an implementation specification (`<name>_impl.py`), sharing the exact class name from the specification and subclassing the interface Protocol and Singleton: `class Alpha(alpha.Alpha, Singleton):`
- [ ] Every singleton implementation class subclasses `Singleton`, declares a zero-argument constructor `def __init__(self) -> None:`, initializes its lifecycle tier (`tier = "system"` or `tier = "agent_session"`), and optionally implements `def initialize(self) -> None:` if post-construction initialization is required
- [ ] Every implementation module defines a top-level `__initialize__(registry: Optional[LifecycleRegistry] = None) -> None:` method that registers each singleton class under all inherited singleton types and the implementation class itself (`keys=[Alpha, alpha.Alpha, ...]`), with its lifecycle tier (`system` or `agent_session`)
- [ ] An implementation module implements (closes) interface components by implementing all of their declared singleton types, listing implemented interface components in `implements` and used non-implemented components in `imports`
- [ ] An assembly module (`<name>_asm.py`) defines `CONSTITUENTS` and a top-level `__initialize__(registry: Optional[LifecycleRegistry] = None) -> None:` method that recursively calls `__initialize__` on all its constituent `_impl` and `_asm` modules
- [ ] An assembly module's implemented components equal the union of its constituents' implemented components; its imported components equal the union of its constituents' imports excluding its implemented components
- [ ] A root assembly module (`<name>_asm.py`) ready for execution implements all singleton interface components and imports only external boundary (`_ext`) components and passive data types
- [ ] External specifications (`<name>_ext.pyi`) and assembly modules (`<name>_asm.py`) are never tested directly (no test module exists for them)

## Imports

- [ ] Sibling-module imports within the library package use relative form (`from .widget import Widget, WidgetConfig`)
- [ ] Every imported module and symbol is referenced in the module's AST; unused imports are prohibited
- [ ] The types the module uses are imported from their owning interface modules, never redefined
- [ ] Library modules must not import from `framework`
- [ ] An implementation module (`<name>_impl.py`) or interface module (`<name>.py`) must not import any implementation module (`*_impl.py`) or assembly module (`*_asm.py`); foreign collaborator singletons are accessed on demand via `get_singleton(ProtocolClass)`, while collaborator singletons defined in the same module are accessed via `get_singleton(ImplementationClass)`
- [ ] An assembly module imports only the constituent implementation and assembly modules it assembles (`from . import widget_impl, helper_asm`)
- [ ] When an implementation depends on an external boundary specification (`<name>_ext.pyi`), the third-party package documented in the external spec's docstring is imported directly

## Data types and protocols

- [ ] Passive record types are decorated with `@dataclass(frozen=True)` matching the grounding specification
- [ ] Data types specifying `init=False` in the grounding specification are decorated with `@dataclass(frozen=True, init=False)` without a public constructor, and are instantiated inside authorized library operations using `object.__new__(cls)` and `object.__setattr__(inst, field, value)`
- [ ] Dataclass field names, types, order, and default values match the grounding specification exactly; fields are declared as class-level attributes, not stub methods (`__init__` or properties)
- [ ] Specification framework decorators (`@data_type`, `@variant`, `@singleton_type`, `@poly_type`, `@operation`) and specification docstrings (`PURPOSE:`, `FRESH_REQUIREMENTS:`) are omitted from library modules
- [ ] Interface types are declared as `class Name(Protocol):` matching the grounding specification
- [ ] Type aliases match the grounding specification in name, generic parameters, and aliased target type
- [ ] `Literal` discriminator values match the grounding specification exactly
- [ ] Interface type variables are resolved to concrete types where the implementation specification requires, never left bare in concrete implementations

## Operation contracts

- [ ] Operation signatures match the grounding specification exactly in method name, parameter names, type annotations, defaults, and return type
- [ ] The operation implementation satisfies all postconditions documented under `FRESH_REQUIREMENTS:` and `INHERITED_REQUIREMENTS:`
- [ ] Comments in the code cite exact requirements from `FRESH_REQUIREMENTS:` and `INHERITED_REQUIREMENTS:` using `# Requirement: <text>` verbatim matching the specification string; fabricating requirement comments is strictly prohibited
- [ ] The operation implementation relies on caller fulfillment of preconditions documented under `FRESH_ASSUMPTIONS:`; callee operations do not add redundant defensive validation unless explicit failure return signals are specified
- [ ] Collaborator wiring and dependencies follow the derivation instructions in `GROUNDING_ARGUMENT:` docstrings
- [ ] Expected failures return the exact signal specified in the contract (`None`, `False`, or an explicit failure record)
- [ ] Relational and identity-sensitive requirements (such as operations acting when an entity matches or for the same resource) evaluate the exact entity identity or resource discriminator; substituting a broad category, tool name, or coarse heuristic in place of specific entity identity is prohibited
- [ ] Requirements restricting actions to specific matching conditions preserve non-matching entities and unrelated resources without unintended modification or destruction
- [ ] No unmandated behavior, synthetic outcome, or artificial termination is invented beyond the contract; no stated requirement is omitted

## Invariants and error handling

- [ ] Invariants hold across all operations, preserving consistency across sequential calls
- [ ] Comments in the code identify which invariants from the contract the code preserves, without explaining how they are covered
- [ ] No module-level mutable state exists when the specification states no persistent state is maintained
- [ ] Unexpected failures propagate as unhandled exceptions; they are never masked by invented fallback values, empty defaults, or suppressed errors
- [ ] External boundary calls handle documented library exceptions in accordance with the contract, converting them to specified return signals or letting them propagate

## Lint checks

- [ ] Sibling-module imports use relative form within the package (`from .widget import ...`)
- [ ] Non-assembly library modules must not import from any implementation module (`*_impl.py`) or assembly module (`*_asm.py`)
- [ ] Library modules must not import from `framework`
- [ ] Dataclasses in library modules must not declare `def __init__` or `@property` stubs
- [ ] Only public types declared in the grounding specification appear in the library module without a preceding underscore, and all declared types are defined
- [ ] Class names must match the exact type name declared in the grounding specification without an 'Impl' suffix
- [ ] Library modules must not call `unittest.main()` (test runners belong in test modules only)
- [ ] Library modules must not catch broad exceptions (bare 'except:', 'except Exception:', 'except BaseException:') without re-raising
- [ ] All module imports and transitive closure are resolvable
- [ ] All imported modules and symbols are referenced in the module's AST (zero unused imports)
- [ ] Private helper functions and classes defined in the library module are referenced in the module's AST (zero unused dead code)
- [ ] Library modules must not contain type suppression comments ('# type: ignore')
- [ ] The package BUILD file contains the `pyright_library` target with required dependencies

## Common pitfalls

- [ ] Creating a library file for an external boundary specification (`<name>_ext.pyi` has no corresponding `.py` file)
- [ ] Creating an implementation module for a data-type-only interface specification that defines no singletons
- [ ] Importing from `framework` or applying specification AST decorators (`@data_type`, `@operation`, `@singleton_type`, etc.) in library modules
- [ ] Defining dataclass fields as empty `def __init__` or `@property` stubs instead of class attribute annotations
- [ ] Copying specification docstring sections (`PURPOSE:`, `FRESH_REQUIREMENTS:`, `GROUNDING_ARGUMENT:`, `INHERITED_REQUIREMENTS:`, `INHERITED_ASSUMPTIONS:`) into library modules
- [ ] Unused imports — importing modules or symbols that are never referenced in the implementation's AST
- [ ] Suppressing type checker errors using '# type: ignore' instead of properly typing and resolving symbols
- [ ] Constructor injection of collaborator singletons instead of zero-argument `__init__` and on-demand `get_singleton`
- [ ] Renaming parameters, changing parameter order, or modifying default values from the grounding signature
- [ ] Redefining types instead of importing them from their owning interface module
- [ ] Swallowing unexpected failures into default fallback values instead of allowing exceptions to propagate
- [ ] Importing implementation modules (`*_impl.py`) in non-assembly library code
- [ ] Adding unmandated defensive validation for preconditions that `FRESH_ASSUMPTIONS:` assigns to callers
- [ ] Substituting broad categories or tool names for specific entity identity when evaluating relational requirements
- [ ] Inventing behavior, heuristics, synthetic outcomes, or termination side effects not specified in the grounding contracts
- [ ] Fabricating `# Requirement:` comments that do not exist in `FRESH_REQUIREMENTS:` or `INHERITED_REQUIREMENTS:` of the grounding specification
- [ ] Omitting the singleton implementation class itself from the registered keys in `__initialize__`
- [ ] Querying a local singleton defined in the same module by interface protocol and downcasting with `isinstance` instead of querying by implementation class directly
- [ ] Omitting comments identifying which requirements or invariants are covered by code blocks
- [ ] Explaining code execution mechanics in comments rather than identifying what requirements or invariants are covered
- [ ] Exposing file paths — using filesystem paths (e.g. `grounding/<name>.pyi`) instead of virtual file names (`<name>.pyi`)
