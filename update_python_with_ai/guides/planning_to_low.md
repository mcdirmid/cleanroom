<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T05:04:27Z
LAST_CHANGED: 2026-10-10T21:52:00Z
CHANGE: Clarify that cleanroom metadata headers are managed automatically by submit
CODE_HASH: 7bf214d4ec11
-->

# Guide: Planning to Low-Level Specification Alignment

## Summary

The artifact is a Low-Level Python stub specification (`low/<name>.pyi` or `low/<name>_impl.pyi`) that structurally formalizes `planning/<name>.md`, submitted via `submit(target="<target_file>", change_summary="...")`. In multi-node sessions, multiple low-level specs are processed together by package-relative alias path. Cleanroom metadata headers (under `# --- CLEANROOM METADATA ---`) are managed automatically by Cleanroom tooling upon `submit(change_summary=...)`; direct edits to metadata headers are prohibited and rejected by editing tools. Authority hierarchy: when planning or high-level specifications and a low-level file disagree, the low-level file is wrong and must align with upstream specifications. External specifications (`low/<name>_ext.pyi`) formalize foreign API documentation, usage snippets, and mechanics from `high/<name>_ext.md` into module docstrings without AST code. Assembly specifications (`low/<name>_asm.pyi`) directly mirror assembly instructions from `high/<name>_asm.md` without standalone planning canvases, defining `__initialize__()` with `CONSTITUENTS:` guaranteeing that every constituent implementation is registered into the lifecycle.

Classes, type parameters, properties, operations, and tier memberships materialize in the AST. Types, records, and variants use domain-qualified compound names (e.g. `CommandResult`, `QueryFilter`, `WidgetPayload`). Planning contract requirements are assigned to type invariants (`INVARIANTS:`), caller prerequisites (`PRECONDITIONS:`), and operation outcomes (`POSTCONDITIONS:`). Interface stubs (`low/<name>.pyi`) define abstract protocols without collaborator names. Implementation stubs (`low/<name>_impl.pyi`) maintain 1:1 class parity and full member-level parity with their interfaces, and synthesize planning grounding into natural language arguments under `GROUNDING:` citing valid collaborator classes and methods. A specification may name a concrete file literal only if that file is its own artifact, named in its own planning; knowledge of external file formats, host markers, or shared state files must go through an imported `_ext` external specification. Verification is conducted by the `spec_qa` auditor role.

> META: "Low-level specifications translate Planning Canvas specifications into formal Python interface stubs, type-level tier hierarchies, atomic contracts, and implementation grounding arguments under GROUNDING: without relational Datalog syntax."

## Lint checks

- [ ] Top-level statements consist strictly of imports, classes, type aliases, at most one `def __orphan__() -> None:` (non-assembly specs), at most one `def __initialize__() -> None:` (assembly specs `<name>_asm.pyi`), and optional module docstrings
- [ ] In implementation specifications (`<name>_impl.pyi`), top-level imports declare all non-external modules specified in front-matter `imports:` of the high-level specification (`high/<name>_impl.md`)
- [ ] In implementation specifications (`<name>_impl.pyi`), every imported module must be used in the AST or cited in at least one `GROUNDING:` docstring
- [ ] Hardcoded host file check: non-external specifications must not contain hardcoded file names, configuration markers, or persistence files unless imported from an external boundary specification (e.g. `cleanroom_files_ext`)
- [ ] Implementation stubs maintain 1:1 member parity with their implemented interface: every `@property` and `@operation` declared on an interface class must have an `@override` member on the implementing class
- [ ] External specification stubs (`<name>_ext.pyi`) contain strictly a module docstring with `## External Mechanics & API Documentation`, `## Build Dependencies`, and `## Usage Snippets` sections without Python AST code
- [ ] Top-level `__orphan__()` and `__initialize__()` take no parameters, return `None`, have no decorators, and contain strictly a docstring followed by `...`
- [ ] Top-level `__orphan__()` docstrings contain strictly a summary and `POSTCONDITIONS:`; `__initialize__()` docstrings contain strictly a summary and `CONSTITUENTS:`
- [ ] Every class definition is decorated with exactly one structural kind decorator from `framework`: `@singleton_type`, `@poly_type`, `@data_type`, or `@variant`
- [ ] `@singleton_type` classes designate active services or tier definitions, expressing subordinate tier membership through `InTier[TierType]`
- [ ] `@poly_type`, `@data_type`, and `@variant` decorators take no arguments
- [ ] Subordinate lifecycle tiers inherit from `ChildTierOf[ParentTier]` where `ParentTier` is a declared `LifecycleTier` type
- [ ] In `@singleton_type` and `@poly_type` classes, every member is decorated with either `@property` or `@operation`, never both or neither
- [ ] Overriding members are decorated with `@override` alongside `@property` or `@operation`
- [ ] Every class member takes `self` as its first parameter; `@property` methods take only `self`
- [ ] All positional parameters after `self` and all method return types declare explicit type annotations
- [ ] Member bodies consist strictly of an optional docstring followed by `...`; executable statements, assignments, loops, conditionals, and `pass` are prohibited
- [ ] Docstring section headers are closed strictly to `Args:`, `Returns:`, `CONSTITUENTS:`, `INVARIANTS:`, `PRECONDITIONS:`, `POSTCONDITIONS:`, `GROUNDING:` (in `_impl.pyi`), `Raises:`, and `Yields:`
- [ ] The `ASSUMPTIONS:` docstring section is strictly prohibited; caller prerequisites belong under `PRECONDITIONS:`
- [ ] Relational predicate headers (`NEW_PREDICATES:`, `RULES:`, `GROUNDING_*`) are strictly prohibited
- [ ] Entries under `CONSTITUENTS:`, `INVARIANTS:`, `PRECONDITIONS:`, `POSTCONDITIONS:`, and `GROUNDING:` start with `- `
- [ ] Sentences under `INVARIANTS:`, `PRECONDITIONS:`, `POSTCONDITIONS:`, and `GROUNDING:` end with a period (`.`)

## Document layout and imports

- [ ] Specifications import structural decorators (`singleton_type`, `poly_type`, `data_type`, `variant`, `operation`, `override`) from `framework`
- [ ] Specifications import lifecycle tier primitives (`ChildTierOf`, `RootTier`, `SystemTier`, `InTier`, `get_tier`) from `support.lib.lifecycle`
- [ ] Imported types from sibling or external specifications use direct symbol imports or module imports
- [ ] Implementation specifications (`<name>_impl.pyi`) import implemented interface modules directly (`import <module>`) and preserve 1:1 class name and member parity
- [ ] Implementation specifications import collaborator modules providing capabilities cited under `GROUNDING:`
- [ ] Assembly specifications (`<name>_asm.pyi`) define strictly `def __initialize__() -> None:` with a summary and `CONSTITUENTS:` docstring section listing constituent modules mirroring HLS `assembles:`
- [ ] Free-floating `#` comments are prohibited; all narrative justifications and contracts live exclusively inside triple-quoted docstrings
- [ ] Dead imports are prohibited; every imported module must be used in type signatures, inheritance, or cited in `GROUNDING:`

## Ontological classification and lifecycle tiers

- [ ] Stateful coordinators or singletons map to `@singleton_type` classes inheriting `InTier[TierType]`
- [ ] Root lifecycle tiers subclass `RootTier`; subordinate lifecycle tiers subclass `ChildTierOf[ParentTier]` decorated with `@singleton_type("system")`
- [ ] Members of a lifecycle tier express tier membership by inheriting `InTier[TierType]` on their class definition
- [ ] Interfaces define lifecycle tiers as static types rather than runtime factory values
- [ ] Open multiton capabilities or polymorphic actions map to `@poly_type` without lifecycle arguments
- [ ] Passive entities, value objects, structural records, and messages map to `@data_type`
- [ ] Discriminated sub-classifications and closed sum-type branches map to `@variant` subclassing their base data type
- [ ] Leaf `@data_type` and `@variant` classes declare `@dataclass(frozen=True)` and define state directly as typed dataclass fields documented under `Args:`
- [ ] Data types never inherit from active singleton services; a data type may extend a stateless `@poly_type` protocol provided all requirements are satisfied

## Members and signatures

- [ ] Attributes and exposed states in active services map to `@property` methods, whereas state fields in `@data_type` classes map to typed dataclass fields
- [ ] Actions and callable behaviors map to `@operation` methods
- [ ] Domain string concepts representing names, descriptions, or identifiers declare specialized `NewType` definitions rather than bare `str` primitives
- [ ] Associative collections map strictly to standard Python `Mapping[KT, VT]`; custom collection classes are prohibited
- [ ] Operations accepting arbitrary key-value inputs map parameters to `Mapping[str, Any]`
- [ ] Generic classes and parameterized operations declare Python 3.12 type parameter syntax
- [ ] Return types map deterministically to standard Python types: `str`, `int`, `bool`, `None`, and tuples for paired compound outcomes

## Invariants, Preconditions, and Postconditions

- [ ] Planning contracts are assigned deterministically: state consistency rules map to `INVARIANTS:`, invocation prerequisites map to `PRECONDITIONS:`, and operational outcomes map to `POSTCONDITIONS:`
- [ ] Caller preconditions under `PRECONDITIONS:` state obligations callers must satisfy; callee stubs never specify defensive checks or branches for uncontracted caller errors
- [ ] Type invariants under `INVARIANTS:` define guarantees preserved across instances and are never repeated as preconditions on operations of that type
- [ ] Subtypes inherit all `INVARIANTS:` from base types transitively; invariants must never be duplicated into subtype docstrings
- [ ] Overriding operations inherit supertype `POSTCONDITIONS:` and must not copy-paste base requirements verbatim
- [ ] Redundancy decision procedure: if a method signature mechanically guarantees a requirement (such as returning a collection), delete the postcondition bullet; if the signature does not encode the property's semantic meaning (e.g. `-> bool` does not guarantee 'reflects current session state'), the postcondition bullet is legitimate and must be retained
- [ ] Conditional requirements and failure branches use exact normative syntax: `- WHEN <condition>, MUST <outcome>.`
- [ ] Unconditional postconditions and state updates use exact normative syntax: `- MUST <outcome>.`
- [ ] When an operation returns a response record or produces diagnostic feedback on failure, postconditions specify the exact error string template in double quotes
- [ ] One-way conditional preservation: when source planning specifies "A when B", postconditions preserve it strictly as `- WHEN B, MUST A.`; synthesizing the uncontracted converse is prohibited
- [ ] Mentioning collaborators in interface stubs is strictly prohibited; interface stubs (`low/<name>.pyi`) must never name specific collaborator services or classes
- [ ] A specification may name a concrete file literal only if that file is its own artifact, named in its own planning; shared file formats, markers, or conventions must be imported from an `_ext` external specification

## Grounding arguments in implementation specifications

- [ ] Implementation stubs (`low/<name>_impl.pyi`) synthesize grounded knowledge requirements into natural language arguments under `GROUNDING:` in class and member docstrings, explicitly mentioning all imported collaborator components
- [ ] `GROUNDING:` sections appear strictly in implementation stubs (`low/<name>_impl.pyi`) and are strictly prohibited in interface stubs (`low/<name>.pyi`)
- [ ] `GROUNDING:` arguments explicitly name imported components, collaborator classes, and collaborator methods/properties
- [ ] Grounding citations must cite valid `Class.member` or `module.member` tokens that genuinely exist on the referenced component specification
- [ ] `GROUNDING:` arguments describe how internal backing collections and state fields are accessed or mutated to satisfy inherited deferred requirements
- [ ] Distinguishing copy-down from grounding: inherited postconditions must not be repeated, but `GROUNDING:` must explicitly name the collaborator member providing the capability

## Common pitfalls

- [ ] Using prohibited ASSUMPTIONS section — declaring `ASSUMPTIONS:` in docstrings instead of mapping caller prerequisites to `PRECONDITIONS:`
- [ ] Missing member parity — failing to implement all interface-declared operations and properties in `low/<name>_impl.pyi`
- [ ] Floating file names — hardcoding file names or format conventions without importing the defining `_ext` component
- [ ] Fabricated grounding citations — citing non-existent collaborator methods or classes in `GROUNDING:`
- [ ] Collaborator leakage in interfaces — naming specific collaborator classes or managers in interface stubs (`low/<name>.pyi`)
- [ ] Missing GROUNDING in implementations — omitting `GROUNDING:` sections on implementation classes or operations in `low/<name>_impl.pyi`
- [ ] Relational logic leakage — including `NEW_PREDICATES:`, `RULES:`, or `GROUNDING_*` clauses in low-level specifications
- [ ] Redundant type requirements — writing requirement bullets that merely restate guarantees already mechanically enforced by static types
- [ ] Redundant precondition repetition — repeating an invariant of a type as a precondition on an operation within that type
- [ ] Copy-down requirement duplication — copying down unwoven base protocol postconditions into subtype specifications
- [ ] Dead imports — declaring module imports in stubs that are never used in AST types or cited in `GROUNDING:`
- [ ] Missing `@operation` decorator on non-property methods
- [ ] Missing type annotations on operation parameters or return types
- [ ] Using `pass` or executable logic in member bodies instead of `...`
