<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T05:04:27Z
LAST_CHANGED: 2026-10-04T02:03:40Z
CHANGE: new file
CODE_HASH: d4743c454043
-->

# Guide: Low-Level Specification to Library Implementation Alignment

## Summary

The artifact is a Python library module (`lib/<name>.py` or `lib/<name>_impl.py`) that formalizes `low/<name>.pyi` (and `low/<name>_impl.pyi`), submitted via `submit(target="<target_file>", change_summary="...")`. In multi-node sessions, multiple library modules are processed together by package-relative alias path. Library modules categorize into interface modules (`lib/<name>.py`) and implementation modules (`lib/<name>_impl.py` or concrete service modules). Interface modules define abstract protocol types, structural stubs, passive data types, and type aliases; service protocols in interface modules remain abstract `Protocol` classes containing strictly `...` stubs without `Singleton` subclassing, without private backing state, and without `__initialize__`. Interface protocols are implemented by concrete implementation components (`_impl`) that may reside in other components or parts. As an edge case, `@data_type` classes extending a `@poly_type` protocol must be concretely implemented in whatever component defines them (including interface modules); these data types are the only types implemented in an interface module.

Implementation modules (`lib/<name>_impl.py` or concrete service modules) translate the structural stubs and behavioral contracts in `low/<name>.pyi` and `low/<name>_impl.pyi` into a complete runtime implementation incorporating real control flow, input validation, iteration sweeps, exception handling, and error response branching. Implementation singletons subclass `Singleton` from `support.lib.lifecycle`, specify their declared `tier`, provide concrete private backing state, and define `__initialize__(registry=None)`. Postconditions (`POSTCONDITIONS:`) specifying unconditional guarantees (`MUST <outcome>.`) and conditional outcomes (`WHEN <condition>, MUST <outcome>.`) are realized as concrete runtime branching (`if/else`), error handling (`try/except`), and exact quoted diagnostic string formatting. Caller assumptions (`ASSUMPTIONS:`) are accepted axiomatically without defensive checks or error branches. Subtypes fulfill the full transitive contract of their supertypes even when low-level specification stubs omit redundant docstring boilerplate. Collaborator singletons are resolved on demand via `get_singleton(...)` respecting lifecycle tier boundaries. Target classes share the exact class names specified in the interface, and obsolete legacy members or uncontracted surplus types are pruned. When low-level specifications reference cross-package types omitted from read-only build dependencies, interface modules isolate them in private fallback containers (e.g. `class _Types: Foo = NewType("Foo", str); pkg = _Types`) and paired implementation modules alias the exact interface container (`pkg = interface_module.pkg`) to preserve nominal identity.

> META: "Library modules translate low-level interface stubs and contracts into abstract protocols for interface components and full runtime execution for implementation components."

## Lint checks

- [ ] Every class and member declared in `low/<name>.pyi` is represented in `lib/<name>.py` with identical names and compatible signatures
- [ ] In interface modules, service protocols subclass `Protocol`, contain strictly ellipsis `...` member stubs, never subclass `Singleton`, never declare private state storage, and never define `__initialize__`
- [ ] In implementation modules, service classes subclass `Singleton` from `support.lib.lifecycle` when implementing `@singleton_type` services
- [ ] In implementation modules, every singleton class specifies its `tier` attribute matching its declared lifecycle tier
- [ ] Implementation modules define `__initialize__(registry=None)` registering concrete singleton classes; interface modules omit `__initialize__`
- [ ] Data types (`@data_type`) extending a poly type (`@poly_type`) are concretely implemented in whatever component defines them; these are the only types implemented in an interface module
- [ ] Leaf `@data_type` and `@variant` classes are frozen dataclasses (`@dataclass(frozen=True)`) defining fields matching `low/<name>.pyi`
- [ ] External libraries are imported only as documented in `low/<name>_ext.pyi`
- [ ] Pyright type checking passes cleanly with zero errors across all classes
- [ ] Obsolete public types, type aliases, and class properties not declared in `low/<name>.pyi` or `low/<name>_impl.pyi` are pruned to maintain strict contract alignment and avoid public API pollution
- [ ] In assembly modules (`lib/<name>_asm.py`), `CONSTITUENTS` is defined as a non-empty tuple containing all constituent modules declared under `CONSTITUENTS:` in `low/<name>_asm.pyi`
- [ ] In assembly modules (`lib/<name>_asm.py`), `__initialize__(registry=None)` is defined and iterates through `CONSTITUENTS` to invoke each constituent module's initialization routine

## Document layout and imports

- [ ] Implementation modules import standard library collections and typing utilities (`Any`, `Callable`, `Dict`, `List`, `Mapping`, `Optional`, `Sequence`, `Set`, `Tuple`)
- [ ] Implementation modules import lifecycle infrastructure (`Singleton`, `LifecycleRegistry`, `get_default_registry`, `get_singleton`) from `support.lib.lifecycle`; interface modules import only typing and data type dependencies
- [ ] Domain data types and error classes are imported from interface modules or defined with exact structural parity
- [ ] Collaborator interfaces are imported directly using package-relative imports
- [ ] Implementation classes are separated by two blank lines, and class members are separated by one blank line
- [ ] Cross-package types omitted from read-only build dependencies are isolated in private dummy containers in interface modules (e.g. `class _Types: Foo = NewType("Foo", str); pkg = _Types`), and paired implementation modules alias the exact container from the interface module (`pkg = interface_module.pkg`) to preserve nominal identity
- [ ] Assembly modules (`*_asm.py`) import all constituent modules declared under `CONSTITUENTS:` in `low/<name>_asm.pyi`, using relative imports for sibling constituents and full package paths (e.g. `from parts.<pkg>.lib import ...`) for cross-package constituents

## Contract realization and control flow

- [ ] In implementation modules, the library realization fulfills the operation sequencing and dataflow dependencies specified in `low/<name>.pyi`
- [ ] In implementation modules, contractual postconditions (`WHEN <condition>, MUST <consequent>`) in `low/<name>.pyi` are realized as concrete runtime conditionals (`if/else`)
- [ ] In implementation modules, unconditional postconditions (`MUST <outcome>.`) in `low/<name>.pyi` are realized as runtime assertions, state transformations, or return values
- [ ] Caller assumptions under `ASSUMPTIONS:` in `low/<name>.pyi` are accepted axiomatically without defensive validation, exception branching, or error returns
- [ ] Implementation classes fulfill all inherited supertype contracts and postconditions transitively across the inheritance hierarchy, even when low-level specification stubs omit redundant docstring copy-down
- [ ] Top-level unbound postconditions declared under `__orphan__()` in `low/<name>.pyi` are realized by the appropriate module service logic
- [ ] Iterative sweeps and comprehensions process collections, dictionaries, and sequences according to contract requirements
- [ ] Happy-path outputs construct and return concrete response records or values matching declared return types in `low/<name>.pyi`
- [ ] Return values, dataclass parameters, and collaborator method arguments typed as domain NewTypes are explicitly wrapped (e.g. `MyNewType(val)`) rather than passed as bare primitives (`str`, `int`, `float`)
- [ ] Wire-format type aliases using Python 3.12 syntax (`type WireType = ...`) declared in `low/<name>.pyi` are preserved and re-exported
- [ ] In interface modules, service protocols retain `...` stubs and dynamic control flow logic is omitted, except for data types extending polytypes which are concretely implemented

## Validation and error branching

- [ ] Missing required parameter checks are implemented where contracts specify missing parameter postconditions in implementation modules
- [ ] Default value fallbacks are applied where contracts specify default value postconditions in implementation modules
- [ ] Missing message diagnostic functions are called where contracts specify missing note postconditions in implementation modules
- [ ] Wire conversions are wrapped in `try/except ParameterConversionError` blocks where contracts specify parameter conversion postconditions in implementation modules
- [ ] Diagnostic failure responses are formatted using the exact error templates specified in `low/<name>.pyi` postconditions in implementation modules
- [ ] When contracts specify domain error exceptions (e.g. classes extending `ValueError` or `RuntimeError`), operations raise them with exact quoted messages, and coordinating services catch them to format responses
- [ ] Collaborator response failures are checked and propagated where contracts specify failure propagation postconditions in implementation modules

## State management and lifecycle integration

- [ ] Stateful singletons in implementation modules declare private instance attributes (`self._tools`, `self._storage`) providing concrete backing storage
- [ ] In interface modules, service protocols remain purely abstract without instance attributes, backing storage, or mutators
- [ ] Mutator operations in implementation singletons update internal state collections while enforcing contracted type-level invariants (`INVARIANTS:`)
- [ ] Getter properties in implementation singletons expose defensive copies or read-only views (`dict(self._tools)`) of internal state
- [ ] Services in implementation modules resolve peer or ancestor singletons via `get_singleton(...)` on demand rather than caching stale instances in global variables
- [ ] Initialization routines in `__initialize__` belong strictly to implementation modules and assembly modules, registering implementations and their realized interface protocol keys; interface modules omit `__initialize__`
- [ ] Assembly modules (`*_asm.py`) aggregate and initialize all constituent modules via `CONSTITUENTS` in `__initialize__(registry=None)`, delegating initialization to each constituent module
