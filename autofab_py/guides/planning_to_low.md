# Guide: Planning to Low-Level Specification Alignment

## Summary

The artifact is a Low-Level Python stub specification (`low/<name>.pyi` or `low/<name>_impl.pyi`) that structurally formalizes `planning/<name>.md`, submitted via `submit(target="<target_file>", change_summary="...")`. Metadata blocks under `# --- CLEANROOM METADATA ---` are managed automatically by Cleanroom tooling upon `submit`; direct edits are prohibited. Authority hierarchy: when planning or high-level specifications and a low-level file disagree, the low-level file is wrong and must align with upstream specifications. External specifications (`low/<name>_ext.pyi`) formalize foreign API documentation and usage snippets into module docstrings without AST code. Assembly specifications (`low/<name>_asm.pyi`) directly mirror assembly instructions from `high/<name>_asm.md` without standalone planning canvases, defining `__initialize__()` with `CONSTITUENTS:` registering all constituent implementations into the lifecycle.

Classes, type parameters, properties, operations, and tier memberships materialize in the AST. Types, records, and variants use domain-qualified compound names. Planning contracts map to type invariants (`INVARIANTS:`), caller prerequisites (`PRECONDITIONS:`), and operational outcomes (`POSTCONDITIONS:`). Checked preconditions raising contract violation errors (`*Error`) cannot be tested and are specified under `PRECONDITIONS:`. Operational postcondition exceptions (`*Exception`) designate external failures (e.g. timeouts) and are specified under `POSTCONDITIONS:`. Classes decorated with `@poly_type` are purely abstract and cannot be instantiated in production code. Implementation stubs (`low/<name>_impl.pyi`) maintain 1:1 class parity and full member parity with their interfaces, declaring at least one `@singleton_type` service and synthesizing planning grounding into natural language arguments under `GROUNDING:` citing valid collaborator classes and methods. A specification names a concrete file literal only if that file is its own artifact; external host files and markers must go through an imported `_ext` specification.

> META: "Low-level specifications translate Planning Canvas specifications into formal Python interface stubs, type-level tier hierarchies, atomic contracts, and implementation grounding arguments under GROUNDING: without relational Datalog syntax."

## Lint checks

- [ ] Top-level statements consist strictly of imports, classes, type aliases, at most one `def __orphan__() -> None:` (non-assembly specs), at most one `def __initialize__() -> None:` (assembly specs `<name>_asm.pyi`), and optional module docstrings
- [ ] In implementation specifications (`<name>_impl.pyi`), top-level imports declare all non-external modules specified in front-matter `imports:` of `high/<name>_impl.md`
- [ ] In implementation specifications (`<name>_impl.pyi`), every imported module must be used in the AST or cited in at least one `GROUNDING:` docstring
- [ ] Non-external specifications must not contain hardcoded file names, configuration markers, or persistence files unless imported from an external boundary specification (e.g. `autofab_files_ext`)
- [ ] Implementation stubs maintain 1:1 member parity with their implemented interface: every `@property` and `@operation` declared on an interface class must have an `@override` member on the implementing class
- [ ] External specification stubs (`<name>_ext.pyi`) contain strictly a module docstring with `## External Mechanics & API Documentation`, `## Build Dependencies`, and `## Usage Snippets` sections without Python AST code
- [ ] Top-level `__orphan__()` and `__initialize__()` take no parameters, return `None`, have no decorators, and contain strictly a docstring followed by `...`
- [ ] Top-level `__orphan__()` docstrings contain strictly a summary and `POSTCONDITIONS:`; `__initialize__()` docstrings contain strictly a summary and `CONSTITUENTS:`
- [ ] Every class definition is decorated with exactly one structural kind decorator from `support.lib.framework`: `@singleton_type`, `@poly_type`, `@data_type`, or `@variant`
- [ ] In implementation specifications (`<name>_impl.pyi`) defining classes, at least one class is decorated with `@singleton_type`
- [ ] Classes decorated with `@poly_type` do not refine a base poly type with the same short name (poly types can only be extended by other poly types with distinct names to create new abstract object types)
- [ ] `@singleton_type` classes designate active services or tier definitions, expressing subordinate tier membership through `InTier[TierType]`
- [ ] `@poly_type`, `@data_type`, and `@variant` decorators take no arguments
- [ ] Subordinate lifecycle tiers inherit from `ChildTierOf[ParentTier]` where `ParentTier` is a declared `LifecycleTier` type
- [ ] In `@singleton_type` and `@poly_type` classes, every member is decorated with either `@property` or `@operation`, never both or neither; overriding members add `@override`
- [ ] Every class member takes `self` as its first parameter; `@property` methods take only `self`; all other parameters and return types declare explicit type annotations
- [ ] Member bodies consist strictly of an optional docstring followed by `...`; executable statements, assignments, loops, conditionals, and `pass` are prohibited
- [ ] Docstring section headers are closed strictly to `Args:`, `Returns:`, `CONSTITUENTS:`, `INVARIANTS:`, `PRECONDITIONS:`, `POSTCONDITIONS:`, `GROUNDING:` (in `_impl.pyi`), `Raises:`, and `Yields:`
- [ ] The `ASSUMPTIONS:` docstring section and relational predicate headers (`NEW_PREDICATES:`, `RULES:`, `GROUNDING_*`) are strictly prohibited
- [ ] Entries under `CONSTITUENTS:`, `INVARIANTS:`, `PRECONDITIONS:`, `POSTCONDITIONS:`, and `GROUNDING:` start with `- ` and end with a period (`.`)

## Document layout and imports

- [ ] Specifications import structural decorators (`singleton_type`, `poly_type`, `data_type`, `variant`, `operation`, `override`) from `support.lib.framework`
- [ ] Specifications import lifecycle tier primitives (`ChildTierOf`, `RootTier`, `SystemTier`, `InTier`, `get_tier`) from `support.lib.lifecycle`
- [ ] Implementation specifications (`<name>_impl.pyi`) import implemented interface modules directly (`import <module>`) and preserve 1:1 class name and member parity
- [ ] Implementation specifications import collaborator modules providing capabilities cited under `GROUNDING:`
- [ ] Assembly specifications (`<name>_asm.pyi`) define strictly `def __initialize__() -> None:` with a summary and `CONSTITUENTS:` docstring section listing constituent modules mirroring HLS `assembles:`
- [ ] Free-floating `#` comments are prohibited; all narrative justifications and contracts live exclusively inside triple-quoted docstrings; dead imports are prohibited

## Ontological classification and lifecycle tiers

- [ ] Stateful coordinators or singletons map to `@singleton_type` classes inheriting `InTier[TierType]`
- [ ] Root lifecycle tiers subclass `RootTier`; subordinate lifecycle tiers subclass `ChildTierOf[ParentTier]` decorated with `@singleton_type("system")`
- [ ] Members of a lifecycle tier express tier membership by inheriting `InTier[TierType]` on their class definition; interfaces define lifecycle tiers as static types
- [ ] Open multiton capabilities or polymorphic actions map to `@poly_type` without lifecycle arguments; classes decorated with `@poly_type` are purely abstract
- [ ] Only singletons (`@singleton_type`) and data types (`@data_type`, `@variant`) can be instantiated in production code; poly types can be instantiated in tests only as collaborator inputs
- [ ] Implementation specifications (`<name>_impl.pyi`) defining classes must declare at least one `@singleton_type` service
- [ ] Passive entities, value objects, structural records, and messages map to `@data_type`; discriminated sub-classifications and closed sum-type branches map to `@variant`
- [ ] Subtyped data types and sum-type branches preserve Python dataclass inheritance ordering: classes extending a base `@data_type` must not declare non-default fields if an inherited field has a default value
- [ ] Leaf `@data_type` and `@variant` classes declare `@dataclass(frozen=True)` and define state directly as typed dataclass fields documented under `Args:`
- [ ] Data types never inherit from active singleton services; a data type may extend a stateless `@poly_type` protocol provided all requirements are satisfied

## Members and signatures

- [ ] Attributes and exposed states in active services map to `@property` methods, whereas state fields in `@data_type` classes map to typed dataclass fields
- [ ] Actions and callable behaviors map to `@operation` methods
- [ ] Domain string concepts representing names, descriptions, or identifiers declare specialized `NewType` definitions rather than bare `str` primitives
- [ ] Associative collections map strictly to standard Python `Mapping[KT, VT]`; operations accepting arbitrary key-value inputs map parameters to `Mapping[str, Any]`
- [ ] Generic classes and parameterized operations declare Python 3.12 type parameter syntax; return types map to standard Python types

## Invariants, Preconditions, and Postconditions

- [ ] Planning contracts map deterministically: state consistency rules to `INVARIANTS:`, invocation prerequisites to `PRECONDITIONS:`, operational outcomes to `POSTCONDITIONS:`
- [ ] Caller preconditions under `PRECONDITIONS:` state obligations callers must satisfy; callee stubs never specify defensive checks or branches for uncontracted caller errors
- [ ] Exception classes ending in `Error` (`*Error`) designate contract violation errors (checked preconditions that cannot be tested); operations checking preconditions defensively designate them under `PRECONDITIONS:` indicating the `*Error` raised upon caller violation
- [ ] Exception classes ending in `Exception` (`*Exception`) designate non-contract operational failures resulting from unanticipated external conditions and are specified under `POSTCONDITIONS:`
- [ ] Docstring `Raises:` sections are reserved strictly for operational `*Exception` postconditions; documenting contract violation errors (`*Error`) under `Raises:` is strictly prohibited
- [ ] Subtypes inherit all `INVARIANTS:` and `POSTCONDITIONS:` from base types transitively and must not copy-paste base requirements verbatim
- [ ] Conditional requirements and failure branches use exact normative syntax: `- WHEN <condition>, MUST <outcome>.`; unconditional postconditions use: `- MUST <outcome>.`
- [ ] When an operation returns a response record or produces diagnostic feedback on failure, postconditions specify the exact error string template in double quotes
- [ ] One-way conditional preservation: when source planning specifies "A when B", postconditions preserve it strictly as `- WHEN B, MUST A.`; synthesizing the uncontracted converse is prohibited
- [ ] Mentioning collaborators in interface stubs is strictly prohibited; interface stubs (`low/<name>.pyi`) must never name specific collaborator services or classes
- [ ] A specification may name a concrete file literal only if that file is its own artifact, named in its own planning; shared file formats or markers must be imported from `_ext`

## Grounding arguments in implementation specifications

- [ ] Implementation stubs (`low/<name>_impl.pyi`) synthesize grounded knowledge requirements into natural language arguments under `GROUNDING:` in class and member docstrings, explicitly mentioning all imported collaborator components
- [ ] `GROUNDING:` sections appear strictly in implementation stubs (`low/<name>_impl.pyi`) and are strictly prohibited in interface stubs (`low/<name>.pyi`)
- [ ] `GROUNDING:` arguments explicitly name imported components, collaborator classes, and collaborator methods/properties, citing valid `Class.member` or `module.member` tokens
- [ ] `GROUNDING:` arguments describe how internal backing collections and state fields are accessed or mutated to satisfy inherited deferred requirements without repeating base postconditions
