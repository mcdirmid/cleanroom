# Guide: Low-Level Specification to Library Implementation Alignment

## Summary

The artifact is a Python library module (`lib/<name>.py` or `lib/<name>_impl.py`) that formalizes `low/<name>.pyi` (and `low/<name>_impl.pyi`), submitted via `submit(target="<target_file>", change_summary="...")`. In multi-node sessions, multiple library modules are processed together by package-relative alias path. Cleanroom metadata blocks at the bottom of the file (under `# --- CLEANROOM METADATA ---` and `# --- END CLEANROOM METADATA ---`) are managed automatically by Cleanroom tooling upon `submit(change_summary=...)`; direct edits to metadata blocks are prohibited and rejected by editing tools. Library modules categorize into interface modules (`lib/<name>.py`) and implementation modules (`lib/<name>_impl.py` or concrete service modules). Interface modules define abstract protocol types, structural stubs, passive data types, and type aliases; service protocols in interface modules subclass `Protocol` and inherit `Singleton[TierType]` matching `low/<name>.pyi`, containing strictly `...` stubs without private backing state, and without `__initialize__`. Interface protocols are implemented by concrete implementation components (`_impl`) that may reside in other components or parts. Classes decorated with `@poly_type` are purely abstract and cannot be refined by a poly type with the same short name (though they may be extended by other poly types to create new abstract object types); only singletons and data types can be instantiated. An `_impl` component with no singletons has nothing to test; implementation components realize active service specifications as concrete `@singleton_type` classes implementing the interface protocol with their declared class-level `tier`. As an edge case, `@data_type` classes extending a `@poly_type` protocol must be concretely implemented in whatever component defines them (including interface modules); these data types are the only types implemented in an interface module.

Implementation modules (`lib/<name>_impl.py` or concrete service modules) translate the structural stubs and behavioral contracts in `low/<name>.pyi` and `low/<name>_impl.pyi` into a complete runtime implementation incorporating real control flow, input validation, iteration sweeps, exception handling, and error response branching. Implementation classes implement their companion interface protocol directly (which already inherits `Singleton[TierType]`), faithfully matching the base class hierarchy in `low/<name>_impl.pyi` without redundantly subclassing `Singleton` or duplicating erased type parameters. Implementation classes define their declared class-level `tier` attribute matching their lifecycle tier and provide concrete private backing state. Modules register singletons into the lifecycle registry via auto-generated module-level `__initialize__(registry=None) -> None`; classes never define `__initialize__`. Singleton instances initialize their private backing state (e.g. locks, collections, caches) in standard `__init__(self) -> None` or the optional inherited lifecycle post-creation hook `def initialize(self) -> None:`. Ad-hoc multi-phase configuration methods (`configure()`, `setup()`) not declared in specifications are prohibited, and implementation classes declare only contracted public members, standard dunder methods, and the optional inherited hook `def initialize(self) -> None:`. Lifecycle registration (`__initialize__`) in implementation modules is auto-generated and maintained by Cleanroom tooling under the `# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---` delimiter; manual modification of auto-generated blocks is prohibited. Postconditions (`POSTCONDITIONS:`) specifying unconditional guarantees (`MUST <outcome>.`) and conditional outcomes (`WHEN <condition>, MUST <outcome>.`) are realized as concrete runtime branching (`if/else`), error handling (`try/except`), and exact quoted diagnostic string formatting. Caller assumptions (`ASSUMPTIONS:`) are accepted axiomatically without defensive checks or error branches. Implementation methods and key control-flow branches include brief inline comments indicating how they correspond to the contractual postconditions, invariants, or sequencing specified in `low/<name>.pyi`. Subtypes fulfill the full transitive contract of their supertypes even when low-level specification stubs omit redundant docstring boilerplate. Collaborator singletons are resolved on demand via `get_singleton(...)` respecting lifecycle tier boundaries. Target classes share the exact class names specified in the interface, and obsolete legacy members or uncontracted surplus types are pruned. When low-level specifications reference cross-package types omitted from read-only build dependencies, interface modules isolate them in private fallback containers (e.g. `class _Types: Foo = NewType("Foo", str); pkg = _Types`) and paired implementation modules alias the exact interface container (`pkg = interface_module.pkg`) to preserve nominal identity.

> META: "Library modules translate low-level interface stubs and contracts into abstract protocols for interface components and full runtime execution for implementation components."

## Lint checks

- [ ] Every class and member declared in `low/<name>.pyi` is represented in `lib/<name>.py` with identical names and compatible signatures
- [ ] In interface modules, service protocols subclass Protocol and inherit Singleton[TierType] matching low/<name>.pyi, contain strictly ellipsis ... member stubs, never declare private state storage, and never define __initialize__
- [ ] In implementation modules, service classes implement interface protocols faithfully matching the base class hierarchy in `low/<name>_impl.pyi`, define class-level `tier` matching their declared lifecycle tier, and never append bare `Singleton` or duplicate `Singleton[TierType]` base classes; classes decorated with `@poly_type` are purely abstract and can never be directly instantiated in library code
- [ ] In implementation modules, every singleton class specifies its `tier` attribute matching its declared lifecycle tier
- [ ] In implementation modules, lifecycle registration (`__initialize__`) is maintained under the `# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---` delimiter; interface modules omit `__initialize__`
- [ ] Data types (`@data_type`) extending a poly type (`@poly_type`) are concretely implemented in whatever component defines them; these are the only types implemented in an interface module
- [ ] Leaf `@data_type` and `@variant` classes are frozen dataclasses (`@dataclass(frozen=True)`) defining fields matching `low/<name>.pyi`
- [ ] Subclassed `@data_type` and `@variant` records follow Python dataclass field ordering constraints across inheritance hierarchies, ensuring non-default fields never follow inherited fields that specify default values; default diagnostic formatting belongs in `__post_init__` rather than conflicting field overrides
- [ ] External libraries are imported only as documented in `low/<name>_ext.pyi`
- [ ] Pyright type checking passes cleanly with zero errors across all classes
- [ ] Obsolete public types, type aliases, and class properties not declared in `low/<name>.pyi` or `low/<name>_impl.pyi` are pruned to maintain strict contract alignment and avoid public API pollution
- [ ] Implementation classes implementing specification protocols declare only contracted public members, standard dunder methods (`__init__`, `__len__`, etc.), and the optional inherited lifecycle hook `def initialize(self) -> None:`; uncontracted public methods (such as ad-hoc `configure()` or `setup()` methods) and class-level `__initialize__` methods are prohibited
- [ ] In assembly modules (`lib/<name>_asm.py`), `CONSTITUENTS` is defined as a non-empty tuple containing all constituent modules declared under `CONSTITUENTS:` in `low/<name>_asm.pyi`
- [ ] In assembly modules (`lib/<name>_asm.py`), `__initialize__(registry=None)` is defined and iterates through `CONSTITUENTS` to invoke each constituent module's initialization routine

## Document layout and imports

- [ ] Implementation modules import standard library collections and typing utilities (`Any`, `Callable`, `Dict`, `List`, `Mapping`, `Optional`, `Sequence`, `Set`, `Tuple`)
- [ ] Implementation and interface modules may import specification framework decorators and types (`singleton_type`, `poly_type`, `data_type`, `variant`, `operation`, `override`) from `support.lib.framework`
- [ ] Implementation modules import lifecycle infrastructure (`LifecycleRegistry`, `get_default_registry`, `get_singleton`) from `support.lib.lifecycle` (and `Singleton` only when explicitly declared in `low/<name>_impl.pyi`); interface modules import typing, data type dependencies, and `Singleton` / lifecycle tier types matching `low/<name>.pyi`
- [ ] Domain data types and error classes are imported from interface modules or defined with exact structural parity
- [ ] Collaborator interfaces are imported directly using package-relative imports
- [ ] Implementation classes are separated by two blank lines, and class members are separated by one blank line
- [ ] Cross-package types omitted from read-only build dependencies are isolated in private dummy containers in interface modules (e.g. `class _Types: Foo = NewType("Foo", str); pkg = _Types`), and paired implementation modules alias the exact container from the interface module (`pkg = interface_module.pkg`) to preserve nominal identity
- [ ] Assembly modules (`*_asm.py`) import all constituent modules declared under `CONSTITUENTS:` in `low/<name>_asm.pyi`, using relative imports for sibling constituents and full package paths (e.g. `from <package_scope>.parts.<pkg>.lib import ...`) for cross-package constituents; bare partial 'parts' imports are strictly disallowed

## Contract realization and control flow

- [ ] In implementation modules, the library realization fulfills the operation sequencing and dataflow dependencies specified in `low/<name>.pyi`
- [ ] In implementation modules, contractual postconditions (`WHEN <condition>, MUST <consequent>`) in `low/<name>.pyi` are realized as concrete runtime conditionals (`if/else`)
- [ ] In implementation modules, unconditional postconditions (`MUST <outcome>.`) in `low/<name>.pyi` are realized as runtime assertions, state transformations, or return values
- [ ] Implementation methods and key conditional branches contain brief comments indicating how they correspond to the postconditions, invariants, or sequencing in `low/<name>.pyi`
- [ ] When addressing feedback from downstream verification, implementation code fulfills the behavioral contracts and resolves the runtime defect cited in the feedback rather than relying on static compilation alone
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
- [ ] Catching broad exceptions (such as `except Exception:`) without re-raising is prohibited; task runners, executors, and retry handlers that contractually reify caught exceptions into result records or error attributes (e.g. `_result.error = exc`, `NodeResult(error=exc)`) capture the exception instance, or mark boundary handlers with `# cleanroom: allow-broad-exception`
- [ ] Collaborator response failures are checked and propagated where contracts specify failure propagation postconditions in implementation modules

## State management and lifecycle integration

- [ ] Stateful singletons in implementation modules declare private instance attributes (`self._tools`, `self._storage`) providing concrete backing storage
- [ ] Modules register singletons via module-level `__initialize__(registry=None) -> None`; classes never define `__initialize__`; singleton instances initialize backing state via standard `__init__(self) -> None` or the optional inherited lifecycle post-instantiation hook `def initialize(self) -> None:` (invoked automatically by the lifecycle framework for self-registration with managers); uncontracted multi-phase initialization methods (such as ad-hoc `configure()` or `setup()` methods) on classes are prohibited
- [ ] Phase-level configuration (such as parameterizing session metadata before dependent singletons start) is performed through `enter_phase(phase, setup=...)` using contracted operations (e.g. `RoleConfig.set_role`); inventing uncontracted configuration methods to inject dependencies is prohibited
- [ ] Dependencies required across singleton operations are resolved on demand via `get_singleton(...)` or passed as contracted method arguments; inventing uncontracted configuration methods to inject dependencies is prohibited
- [ ] Unreachable defensive branches or assertions protecting internal implementation assumptions are annotated with `# pragma: no cover (assumption: <reason>)`
- [ ] In interface modules, service protocols remain purely abstract without instance attributes, backing storage, or mutators
- [ ] Mutator operations in implementation singletons update internal state collections while enforcing contracted type-level invariants (`INVARIANTS:`)
- [ ] Getter properties in implementation singletons expose defensive copies or read-only views (`dict(self._tools)`) of internal state
- [ ] Services in implementation modules resolve peer or ancestor singletons via `get_singleton(...)` on demand rather than caching stale instances in global variables
- [ ] In implementation modules, `__initialize__` is maintained under the auto-generated block delimiter (`# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---`) and left untouched; interface modules omit `__initialize__`
- [ ] Assembly modules (`*_asm.py`) aggregate and initialize all constituent modules via `CONSTITUENTS` in `__initialize__(registry=None)`, delegating initialization to each constituent module

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T05:04:27Z
LAST_CHANGED: 2026-10-04T02:03:40Z
CHANGE: Clarify that cleanroom metadata headers are managed automatically by submit
CODE_HASH: 17ba67fd84f1
-->
