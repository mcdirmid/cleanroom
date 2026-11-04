# Guide: Low-Level Specification to Library Implementation Alignment

## Summary

The artifact is a Python library module (`lib/<name>.py` or `lib/<name>_impl.py`) that formalizes `low/<name>.pyi` and `low/<name>_impl.pyi`, submitted via `submit(target="<target_file>", change_summary="...")`. Metadata blocks under `# --- CLEANROOM METADATA ---` are managed automatically by Cleanroom tooling upon `submit`; direct edits are prohibited. Interface modules (`lib/<name>.py`) define abstract protocol types, structural stubs with `...`, data types, and type aliases; service protocols inherit `Singleton[TierType]` without backing state or `__initialize__`. Classes decorated with `@poly_type` are purely abstract and cannot be instantiated. Implementation modules realize services as concrete `@singleton_type` classes declaring class-level `tier`. Data types extending polytypes are concretely implemented in whatever component defines them.

Implementation modules translate stubs and contracts into runtime execution with real control flow, input validation, iteration sweeps, and exact error responses. Operational postconditions (`MUST`, `WHEN/MUST`) are realized as runtime assertions, transformations, and conditionals; caller assumptions (`ASSUMPTIONS:`) are accepted axiomatically without defensive branches; retained caller-precondition guards are annotated with `# pragma: no cover (assumption: precondition_guard)`. Modules register singletons via auto-generated `__initialize__(registry=None)` maintained under `# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---`. Singletons initialize private backing state in `__init__` or optional inherited `initialize(self) -> None:`; ad-hoc configuration methods (`configure()`, `setup()`) are prohibited. Collaborator singletons are resolved via `get_singleton(...)`. When addressing downstream feedback, sibling methods and branches across the module are audited for the same defect pattern before submitting. Unreachable code is pruned, or annotated with `# pragma: no cover (assumption: <reason>)` if required by static typing or internal invariant assertions. Ad-hoc runtime test scripts and inline execution (`python3 -c`) are strictly prohibited; verification relies exclusively on static checking.

> META: "Library modules translate low-level interface stubs and contracts into abstract protocols for interface components and full runtime execution for implementation components."

## Lint checks

- [ ] Every class and member declared in `low/<name>.pyi` is represented in `lib/<name>.py` with identical names and compatible signatures
- [ ] In interface modules, service protocols subclass `Protocol` and inherit `Singleton[TierType]` matching `low/<name>.pyi`, containing strictly `...` stubs without private backing state or `__initialize__`
- [ ] In implementation modules, service classes implement interface protocols matching `low/<name>_impl.pyi`, declare class-level `tier`, and never append bare `Singleton` or duplicate `Singleton[TierType]`
- [ ] In implementation modules, every singleton class specifies its `tier` attribute matching its declared lifecycle tier
- [ ] In implementation modules, lifecycle registration (`__initialize__`) is maintained under `# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---`; interface modules omit `__initialize__`
- [ ] Classes decorated with `@poly_type` are purely abstract and never directly instantiated in library code
- [ ] Leaf `@data_type` and `@variant` classes are frozen dataclasses (`@dataclass(frozen=True)`) defining fields matching `low/<name>.pyi`; data types extending a `@poly_type` are concretely implemented in whatever component defines them
- [ ] Subclassed `@data_type` and `@variant` records preserve dataclass field ordering, ensuring non-default fields never follow inherited fields with default values; default formatting belongs in `__post_init__`
- [ ] External libraries are imported only as documented in `low/<name>_ext.pyi`
- [ ] Imports use package-qualified paths (e.g. `from <package_scope>.parts.<unit>.lib.<module> import ...`) or sibling imports (`from .<sibling> import ...`); bare 'parts' imports and parent relative imports (`from ..`) are prohibited
- [ ] Pyright type checking passes cleanly with zero errors across all classes
- [ ] Obsolete public types, type aliases, and uncontracted public methods (such as ad-hoc `configure()` or `setup()`) not declared in `low/<name>.pyi` or `low/<name>_impl.pyi` are pruned
- [ ] In assembly modules (`lib/<name>_asm.py`), `CONSTITUENTS` is defined as a non-empty tuple matching `low/<name>_asm.pyi`, and `__initialize__(registry=None)` iterates through `CONSTITUENTS` to invoke each constituent module's initialization routine

## Document layout and imports

- [ ] Implementation modules import standard library collections and typing utilities (`Any`, `Callable`, `Dict`, `List`, `Mapping`, `Optional`, `Sequence`, `Set`, `Tuple`)
- [ ] Modules import specification framework decorators (`singleton_type`, `poly_type`, `data_type`, `variant`, `operation`, `override`) from `support.lib.framework`
- [ ] Implementation modules import lifecycle infrastructure (`LifecycleRegistry`, `get_default_registry`, `get_singleton`) from `support.lib.lifecycle` (and `Singleton` only when declared in `low/<name>_impl.pyi`); interface modules import `Singleton` and tier types matching `low/<name>.pyi`
- [ ] Domain data types and error classes are imported from interface modules or defined with exact structural parity
- [ ] Collaborator interfaces are imported directly using package-relative imports
- [ ] Implementation classes are separated by two blank lines, and class members are separated by one blank line
- [ ] Cross-package types omitted from read-only build dependencies are isolated in private dummy containers in interface modules (`class _Types: Foo = NewType("Foo", str); pkg = _Types`), and paired implementation modules alias the exact container (`pkg = interface_module.pkg`)

## Contract realization and control flow

- [ ] In implementation modules, execution fulfills operation sequencing and dataflow dependencies specified in `low/<name>.pyi`
- [ ] In implementation modules, contractual postconditions (`WHEN <condition>, MUST <consequent>`) are realized as concrete runtime conditionals (`if/else`)
- [ ] In implementation modules, unconditional postconditions (`MUST <outcome>.`) are realized as runtime assertions, state transformations, or return values
- [ ] Implementation methods and key conditional branches contain brief comments indicating how they correspond to postconditions, invariants, or sequencing in `low/<name>.pyi`
- [ ] When addressing feedback from downstream verification, implementation code fulfills behavioral contracts and resolves the runtime defect cited; sibling methods and branches across the module are audited for the same defect pattern before submitting
- [ ] Caller assumptions under `ASSUMPTIONS:` in `low/<name>.pyi` are accepted axiomatically without defensive validation, exception branching, or error returns
- [ ] Defensive caller-precondition guards: branches enforcing caller preconditions (e.g. state checks or argument bounds) are annotated with `# pragma: no cover (assumption: precondition_guard)` during initial implementation
- [ ] Unreachable code is pruned or restructured to eliminate dead logic; unreachable code is ignored for test coverage using `# pragma: no cover (assumption: <reason>)` only if required by static type checking or internal invariant assertions
- [ ] Implementation classes fulfill all inherited supertype contracts transitively across the inheritance hierarchy, even when low-level specification stubs omit redundant docstring copy-down
- [ ] Top-level unbound postconditions declared under `__orphan__()` in `low/<name>.pyi` are realized by the appropriate module service logic
- [ ] Iterative sweeps and sorting process collections per contracts; deterministic tie-breaking uses explicit stable keys (such as ascending alphabetical or lexicographical order)
- [ ] Return values and parameters typed as domain `NewType`s are explicitly wrapped (e.g. `MyNewType(val)`) rather than passed as bare primitives
- [ ] Wire-format type aliases using Python 3.12 syntax (`type WireType = ...`) declared in `low/<name>.pyi` are preserved and re-exported
- [ ] In interface modules, service protocols retain `...` stubs and dynamic control flow logic is omitted, except for data types extending polytypes which are concretely implemented

## Validation and error branching

- [ ] Missing required parameters, default value fallbacks, and missing message diagnostics are implemented where contracts specify corresponding postconditions
- [ ] Wire conversions are wrapped in `try/except ParameterConversionError` blocks where contracts specify parameter conversion postconditions
- [ ] Diagnostic failure responses and domain exceptions are formatted using exact error templates quoted in `low/<name>.pyi` postconditions
- [ ] Custom exception classes realized with dataclass semantics implement `def __str__(self) -> str: return self.message` (or call `Exception.__init__(self, message)`)
- [ ] Value objects realized with dataclass semantics implement `def __str__(self) -> str` delegating directly to their canonical string representation or `format()` method
- [ ] Catching broad exceptions (`except Exception:`) without re-raising is prohibited, unless reifying caught exceptions into result records or marked with `# cleanroom: allow-broad-exception`
- [ ] Collaborator response failures are checked and propagated where contracts specify failure propagation postconditions

## State management and lifecycle integration

- [ ] Stateful singletons in implementation modules declare private instance attributes (`self._tools`, `self._storage`) providing concrete backing storage
- [ ] Modules register singletons via module-level `__initialize__(registry=None) -> None`; classes never define `__initialize__`; singleton instances initialize backing state via standard `__init__` or optional inherited `initialize(self) -> None:`
- [ ] Phase configuration is performed through `enter_phase(phase, setup=...)` using contracted operations; inventing uncontracted configuration methods (`configure()`, `setup()`) on classes is prohibited
- [ ] Dependencies required across singleton operations are resolved on demand via `get_singleton(...)` or passed as contracted method arguments
- [ ] Mutator operations enforce contracted invariants (`INVARIANTS:`) and dynamically synchronize dependent internal tracking state upon structural mutations
- [ ] Getter properties in implementation singletons expose defensive copies or read-only views (`dict(self._tools)`) of internal state
- [ ] In implementation modules, `__initialize__` is maintained under the auto-generated block delimiter (`# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---`) and left untouched; interface modules omit `__initialize__`
