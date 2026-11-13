# Guide: Low-Level Specification to Library Implementation Alignment

## Summary

The artifact is a Python library module (`lib/<name>.py` or `lib/<name>_impl.py`) that formalizes `low/<name>.pyi` and `low/<name>_impl.pyi`, submitted via `submit(target="<target_file>", change_summary="...")` when code is modified, or contested via `reject(target="<target_file>", reason="...")` strictly on unmodified files when asserting existing code is already compliant with the specification. Metadata blocks under `# --- CLEANROOM METADATA ---` are managed automatically by Cleanroom tooling upon `submit` or `reject`; direct edits are prohibited. Interface modules (`lib/<name>.py`) define abstract protocol types, structural stubs with `...`, data types, and type aliases; service protocols inherit `Singleton[TierType]` without backing state. Classes decorated with `@poly_type` are purely abstract and cannot be instantiated. Implementation modules realize services as concrete classes decorated with `@singleton` (from `support.lib.lifecycle`), declaring class-level `tier` matching `low/<name>_impl.pyi`. Data types extending polytypes are concretely implemented in whatever component defines them.

Implementation modules translate stubs and contracts into runtime execution with real control flow, input validation, iteration sweeps, and exact error responses. Operational postconditions (`MUST`, `WHEN/MUST`) and checked preconditions (`PRECONDITIONS: - WHEN ... MUST raise ...Error`) are realized as runtime assertions, transformations, conditionals, and defensive guards; preconditions without errors are accepted axiomatically without defensive branches. Implementation classes declare their lifecycle role using the `@singleton` decorator; registration into the lifecycle registry is completely automatic and handled reflectively by Cleanroom lifecycle harnesses; implementation modules NEVER define `__initialize__` or `_initialize_`. Collaborator singletons are resolved on demand via `get_singleton(...)`. Singletons initialize private backing state in `__init__` or optional inherited `initialize(self) -> None:`; ad-hoc configuration methods (`configure()`, `setup()`) are prohibited. When addressing coverage blame for unreachable code, wrap the block in `with unreachable:` (or `unreachable()`) rather than deleting code; when downstream QA reports that an unreachable block was executed, remove `with unreachable:` and restore the implementation logic. When addressing downstream feedback, audit sibling methods and branches across the module for the same defect pattern before submitting. Ad-hoc runtime test scripts and inline execution (`python3 -c`) are strictly prohibited; verification relies exclusively on static checking.

> META: "Library modules translate low-level interface stubs and contracts into abstract protocols for interface components and full runtime execution for implementation components."

## Lint checks

- [ ] Every class and member declared in `low/<name>.pyi` is represented in `lib/<name>.py` with identical names and compatible signatures
- [ ] In interface modules, service protocols subclass `Protocol` and inherit `Singleton[TierType]` matching `low/<name>.pyi`, containing strictly `...` stubs without private backing state or `__initialize__`
- [ ] In implementation modules, service classes implement interface protocols matching `low/<name>_impl.pyi`, are decorated with `@singleton`, declare class-level `tier` matching their lifecycle tier, and never append bare `Singleton` or duplicate `Singleton[TierType]`
- [ ] Implementation modules never define `__initialize__` or `_initialize_`; defining `__initialize__` is prohibited; interface modules omit lifecycle decorators
- [ ] Collaborator singletons are resolved on demand via `get_singleton(...)`; manual singleton registration calls and foreign imports for registration are absent from library modules
- [ ] Classes decorated with `@poly_type` are purely abstract and never directly instantiated in library code
- [ ] Leaf `@data_type` and `@variant` classes are frozen dataclasses (`@dataclass(frozen=True)`) defining fields matching `low/<name>.pyi`; data types extending a `@poly_type` are concretely implemented in whatever component defines them
- [ ] Subclassed `@data_type` and `@variant` records preserve dataclass field ordering, ensuring non-default fields never follow inherited fields with default values; default formatting belongs in `__post_init__`
- [ ] External libraries are imported only as documented in `low/<name>_ext.pyi`
- [ ] Imports use package-qualified paths (e.g. `from <package_scope>.parts.<unit>.lib.<module> import ...`) or sibling imports (`from .<sibling> import ...`); bare 'parts' imports and parent relative imports (`from ..`) are prohibited
- [ ] Pyright type checking passes cleanly with zero errors across all classes
- [ ] Obsolete public types, type aliases, and uncontracted public methods (such as ad-hoc `configure()` or `setup()`) not declared in `low/<name>.pyi` or `low/<name>_impl.pyi` are pruned
- [ ] In assembly modules (`lib/<name>_asm.py`), `CONSTITUENTS` is defined as a non-empty tuple matching `low/<name>_asm.pyi`
- [ ] Library code contains zero `# pragma: no cover` or `# no cover` directives (use `with unreachable:` or `unreachable()` only when instructed by coverage)
- [ ] Library code contains zero `# cleanroom: allow-broad-exception` or exception suppression pragma comments; pragma escape hatches suppressing exceptions are strictly prohibited in library code
- [ ] Code comments and docstrings never cite specification contract slugs (e.g. `[slug:...]` or slug identifiers); operational behavior is described in plain semantic prose
- [ ] Exception classes never use `@dataclass(frozen=True)` (Python runtime assigns `__traceback__` on raised instances; exception classes are standard classes or non-frozen dataclasses)
- [ ] Comments and docstrings never cite declared specification contract slugs or bracketed slug tags (`[slug:...]` or `<unit>.<contract>.<facet>`); citing specification slugs in code artifacts is strictly prohibited (`NO_SLUG_REFERENCES`)

## Document layout and imports

- [ ] Implementation modules import standard library collections and typing utilities (`Any`, `Callable`, `Dict`, `List`, `Mapping`, `Optional`, `Sequence`, `Set`, `Tuple`)
- [ ] Modules import specification framework decorators (`singleton_type`, `poly_type`, `data_type`, `variant`, `operation`, `override`) from `support.lib.framework`
- [ ] Implementation modules import lifecycle infrastructure (`singleton`, `get_singleton`) from `support.lib.lifecycle` (and `Singleton` only when declared in `low/<name>_impl.pyi`); interface modules import `Singleton` and tier types matching `low/<name>.pyi`
- [ ] Domain data types and error classes are imported from interface modules or defined with exact structural parity
- [ ] Collaborator interfaces are imported directly using package-relative imports
- [ ] Implementation classes are separated by two blank lines, and class members are separated by one blank line
- [ ] Cross-package types omitted from read-only build dependencies are isolated in private dummy containers in interface modules (`class _Types: Foo = NewType("Foo", str); pkg = _Types`), and paired implementation modules alias the exact container (`pkg = interface_module.pkg`)

## Contract realization and control flow

- [ ] In implementation modules, execution fulfills operation sequencing and dataflow dependencies specified in `low/<name>.pyi`
- [ ] In implementation modules, contractual postconditions (`WHEN <condition>, MUST <consequent>`) are realized as concrete runtime conditionals (`if/else`)
- [ ] In implementation modules, unconditional postconditions (`MUST <outcome>.`) are realized as runtime assertions, state transformations, or return values
- [ ] Implementation methods, validation logic, and conditional branches contain brief comments in plain prose describing operational logic without citing specification contract slugs or slug IDs
- [ ] Contract violations with a contracted Error must be reachable: library authors must implement and throw the contracted error on invalid inputs or states specified under `PRECONDITIONS:` (`- WHEN ..., MUST raise <Error>.`) in `low/<name>.pyi` without pragma annotations
- [ ] When addressing feedback from downstream verification, modify code to satisfy contracts, verify with `check_files`, and submit via `submit`; if feedback is contested because existing code is already compliant, reject without code changes via `reject(target="<target_file>", reason="...")`; audit sibling methods across the module for the same defect pattern before submitting
- [ ] Caller preconditions without errors under `PRECONDITIONS:` in `low/<name>.pyi` define obligations where violation causes undefined behavior; implementations accept them axiomatically without defensive validation, exception branching, or error returns
- [ ] Quarantine unreachable code over destructive pruning: when blamed by coverage or pretense_coverage for unreachable code, import `unreachable` (`from support.lib.framework import unreachable`) and wrap the block in `with unreachable:` (or use `unreachable()`) rather than deleting code, preserving it as a tripwire; using `with unreachable:` proactively without coverage blame is prohibited
- [ ] When downstream verification (QA or Pretense QA) reports that an unreachable block or `unreachable()` was executed by a test, remove `with unreachable:` and restore the full implementation logic
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
- [ ] Custom exception classes never use `@dataclass(frozen=True)` (Python runtime assigns `__traceback__` when raised); classes realized with dataclass semantics use non-frozen dataclasses and implement `def __str__(self) -> str: return self.message` (or call `Exception.__init__(self, message)`)
- [ ] Value objects realized with dataclass semantics implement `def __str__(self) -> str` delegating directly to their canonical string representation or `format()` method
- [ ] Catching broad exceptions (`except Exception:`) without re-raising is strictly prohibited; all exception-suppression pragmas (such as `# cleanroom: allow-broad-exception`) are banned in library code; exceptions may only be caught when re-raising or when explicitly reifying failures into contracted result records (e.g. `NodeResult(..., error=exc)`); inventing uncontracted defensive `try/except` blocks around collaborator singletons or framework calls is prohibited
- [ ] Collaborator response failures are checked and propagated where contracts specify failure propagation postconditions

## State management and lifecycle integration

- [ ] Stateful singletons in implementation modules declare private instance attributes (`self._tools`, `self._storage`) providing concrete backing storage
- [ ] Concrete singletons are decorated with `@singleton`; classes and modules never define `__initialize__`; singleton instances initialize backing state via standard `__init__` or optional inherited `initialize(self) -> None:`
- [ ] Implementation modules define exclusively their own concrete singletons; registering foreign singletons is absent; collaborator singletons defined in foreign modules are resolved exclusively on demand via `get_singleton(...)` or accepted as arguments, never registered or initialized by the consuming module
- [ ] Foreign collaborator singletons from other modules are accessed strictly through their public contracted methods or properties; accessing private attributes (attributes with a leading underscore) on foreign collaborator instances is prohibited (classes defined within the same file belong to the same unit and may share internal state)
- [ ] Phase configuration is performed through `enter_phase(phase, setup=...)` using contracted operations; inventing uncontracted configuration methods (`configure()`, `setup()`) on classes is prohibited
- [ ] Mutator operations enforce contracted invariants (`INVARIANTS:`) and dynamically synchronize dependent internal tracking state upon structural mutations
- [ ] Multi-entity state transitions and batch sweeps ensure all registered domain entities are accounted for, never assuming private caches or internal dictionaries were populated by preceding calls
- [ ] Getter properties in implementation singletons expose defensive copies or read-only views (`dict(self._tools)`) of internal state

## Examples

- [ ] Concrete implementation singleton declaration:
```python
from __future__ import annotations

from support.lib.lifecycle import get_singleton, singleton
from .storage import StorageService
from .task_worker import TaskNotifier, TaskWorkerService


@singleton
class TaskWorkerServiceImpl(TaskWorkerService):
    tier = "system"

    def __init__(self) -> None:
        self._active_tasks: list[str] = []

    def execute_task(self, task_id: str) -> None:
        storage = get_singleton(StorageService)
        storage.save(task_id)
        notifier = get_singleton(TaskNotifier)
        notifier.notify_completion(task_id)
        self._active_tasks.append(task_id)


# PROHIBITED ANTI-PATTERN: Defining __initialize__ or manual registration
# def __initialize__(registry=None) -> None:  # PROHIBITED: Do not define __initialize__
#     ...
```
