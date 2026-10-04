# Guide: Planning to Low-Level Specification Alignment

## Summary

The artifact is a Low-Level Python stub specification (`low/<name>.pyi`) that structurally formalizes `planning/<name>.md`, submitted via `submit(target="<target_file>", change_summary="...")`. In multi-node sessions, multiple low-level specs are processed together by package-relative alias path. External specifications (`low/<name>_ext.pyi`) contain module docstrings without AST code. Assembly specifications (`high/<name>_asm.md`) formalize to stubs (`low/<name>_asm.pyi`) defining `__initialize__()` with `CONSTITUENTS:`. Specifications declare structural stubs with static type annotations, ontological classification decorators from `framework` (documented in `framework.pyi`, canonical path `update_python_with_ai/support/lib/framework.pyi`), and lifecycle tier declarations from `support.lib.lifecycle` (documented in `support/lib/lifecycle.pyi`, canonical path `update_python_with_ai/support/lib/lifecycle.pyi`).

Classes, type parameters, properties, operations, and tier memberships materialize in the AST. Types, records, and variants use domain-qualified compound names (e.g. `CommandResult`, `QueryFilter`, `WidgetPayload`) reflecting domain roles; bare, context-free generic names (such as `Response`, `Parameter`, `Config`, `Data`, `Result`) and standard collection collisions (`List`, `Dictionary`, `Set`) are prohibited. Planning contract requirements are assigned to type invariants (`INVARIANTS:`), caller assumptions (`ASSUMPTIONS:`), operation preconditions (`PRECONDITIONS:`), and operation postconditions (`POSTCONDITIONS:`). Invariants of a type hold across all operations of that type and are never repeated as preconditions of an operation in that type. Caller assumptions represent environmental invariants accepted axiomatically with zero callee checks. Datalog predicates, relational facts, and Groundtalk clauses are excluded from low-level specifications. Unbound contracts live under `POSTCONDITIONS:` in top-level `__orphan__()`.

> META: "Low-level specifications translate Planning Canvas specifications into formal Python interface stubs, type-level tier hierarchies, and atomic contracts organized as type invariants, caller assumptions, preconditions, and postconditions, without relational Datalog syntax or facts."

## Lint checks

- [ ] Top-level statements consist strictly of imports, classes, type aliases, at most one `def __orphan__() -> None:` (non-assembly specs), at most one `def __initialize__() -> None:` (assembly specs `<name>_asm.pyi`), and optional module docstrings
- [ ] External specification stubs (`<name>_ext.pyi`) contain strictly a module docstring with `## External Mechanics & API Documentation`, `## Build Dependencies`, and `## Usage Snippets` sections without Python AST code
- [ ] Top-level `__orphan__()` and `__initialize__()` take no parameters, return `None`, have no decorators, and contain strictly a docstring followed by `...`
- [ ] Top-level `__orphan__()` docstrings contain strictly a summary and `POSTCONDITIONS:`; `__initialize__()` docstrings contain strictly a summary and `CONSTITUENTS:`
- [ ] Every class definition is decorated with exactly one structural kind decorator from `framework`: `@singleton_type`, `@poly_type`, `@data_type`, or `@variant`
- [ ] `@singleton_type` classes designate active services or tier definitions, expressing subordinate tier membership through `InTier[TierType]`
- [ ] `@poly_type`, `@data_type`, and `@variant` decorators take no arguments
- [ ] Subordinate lifecycle tiers inherit from `ChildTierOf[ParentTier]` where `ParentTier` is a declared `LifecycleTier` type
- [ ] `@variant` classes inherit from a `@data_type` or another `@variant`, never from an active service
- [ ] `@singleton_type` and `@poly_type` classes inherit from polymorphic interfaces, abstract services, or `InTier[TierType]`, never from data types
- [ ] `@data_type` classes never inherit from active services; a `@data_type` may extend a `@poly_type` only if the polytype has no stateful requirements and the data type satisfies all polytype requirements
- [ ] Every `@data_type` declares at least one property or base type, or serves as a variant sum-type root in the module
- [ ] In `@singleton_type` and `@poly_type` classes, every member is decorated with either `@property` or `@operation`, never both or neither
- [ ] Overriding members are decorated with `@override` alongside `@property` or `@operation`; operations may specialize their return type to a covariant subtype when the override guarantees a restricted outcome
- [ ] Every class member takes `self` as its first parameter; `@property` methods take only `self`
- [ ] All positional parameters after `self` and all method return types declare explicit type annotations
- [ ] Every class and member body consists strictly of an optional docstring followed by `...`; executable statements, assignments, expressions, loops, conditionals, and `pass` are prohibited
- [ ] Every class and member docstring begins with a concise summary description without an artificial header
- [ ] Docstring section headers are closed strictly to `Args:`, `Returns:`, `CONSTITUENTS:`, `INVARIANTS:`, `ASSUMPTIONS:`, `PRECONDITIONS:`, and `POSTCONDITIONS:`
- [ ] Relational predicate headers (`NEW_PREDICATES:`, `RULES:`, `GROUNDING_*`) are strictly prohibited
- [ ] Entries under `CONSTITUENTS:`, `INVARIANTS:`, `ASSUMPTIONS:`, `PRECONDITIONS:`, and `POSTCONDITIONS:` start with `- `
- [ ] Sentences under `INVARIANTS:`, `ASSUMPTIONS:`, `PRECONDITIONS:`, and `POSTCONDITIONS:` end with a period (`.`)
- [ ] Requirements covered by static types (return types, non-null fields, parameter types) are prohibited; contracts contain strictly dynamic behaviors, branches, failure dispatch, and state transitions
- [ ] Preconditions under `PRECONDITIONS:` state caller obligations and operation invocation requirements
- [ ] Invariants of a type are declared strictly under `INVARIANTS:` on the enclosing type and are never repeated as preconditions on operations of that type
- [ ] Types, records, and variants avoid bare generic names (such as `Response`, `Parameter`, `Config`, `Data`, `Result`) and primitive collisions (`List`, `Dictionary`, `Set`), using domain-qualified names instead (e.g. `CommandResult`, `QueryFilter`, `WidgetPayload`, `ElementSequence`)

## Document layout and imports

- [ ] Specifications import structural decorators (`singleton_type`, `poly_type`, `data_type`, `variant`, `operation`, `override`) from `framework` (`framework.pyi`)
- [ ] Specifications import lifecycle tier primitives (`ChildTierOf`, `RootTier`, `SystemTier`, `InTier`, `get_tier`) from `support.lib.lifecycle` (`support/lib/lifecycle.pyi`)
- [ ] Standard collection and meta-type primitives are imported from `typing`
- [ ] Imported types from sibling or external specifications use direct symbol imports (`from <module> import <Type>`) or module imports (`import <module>`)
- [ ] Implementation specifications (`<name>_impl.pyi`) import implemented interface modules directly (`import <module>`) and preserve 1:1 class name parity
- [ ] Assembly specifications (`<name>_asm.pyi`) define strictly `def __initialize__() -> None:` with a summary description and `CONSTITUENTS:` docstring section listing constituent modules
- [ ] Free-floating `#` comments are prohibited; all narrative justifications and contracts live exclusively inside triple-quoted docstrings
- [ ] Classes are separated by two blank lines, and class members are separated by one blank line

## Ontological classification and lifecycle tiers

- [ ] Ontological classification and lifecycle semantics conform to `framework.pyi` and `support/lib/lifecycle.pyi` definitions
- [ ] Stateful coordinators or singletons map to `@singleton_type` classes inheriting `InTier[TierType]`
- [ ] Root lifecycle tiers subclass `RootTier`; subordinate lifecycle tiers subclass `ChildTierOf[ParentTier]` decorated with `@singleton_type("system")`
- [ ] Members of a lifecycle tier express tier membership by inheriting `InTier[TierType]` on their class definition
- [ ] Interfaces define lifecycle tiers as static types rather than runtime factory values
- [ ] Open multiton capabilities or polymorphic actions map to `@poly_type` without lifecycle arguments
- [ ] Passive entities, value objects, structural records, and messages map to `@data_type`
- [ ] Discriminated sub-classifications and closed sum-type branches map to `@variant` subclassing their base data type
- [ ] Base data types with variants and sum-type roots declare `@dataclass(frozen=True, init=False)` with body `...`
- [ ] Leaf `@data_type` and `@variant` classes declare `@dataclass(frozen=True)` and define state directly as typed dataclass fields (`field_name: Type = ...`), automatically synthesizing constructor parameters and immutable properties
- [ ] Dataclass fields on `@data_type` and `@variant` classes are documented under `Args:` in the class docstring; explicit `def __init__` methods or `@property` getters on dataclasses are prohibited
- [ ] Singletons never declare containment hierarchies; services in the same tier access each other as flat peer collaborators
- [ ] Data types never inherit from active singleton services; a data type may extend a stateless `@poly_type` protocol provided all polytype requirements are satisfied

## Members and signatures

- [ ] Attributes, exposed states, and entity references in active services and polymorphic interfaces (`@singleton_type`, `@poly_type`) map to `@property` methods, whereas state fields in `@data_type` and `@variant` classes map directly to typed dataclass fields
- [ ] Actions, capabilities, and callable behaviors introduced as operations in `planning/<name>.md` map to `@operation` methods
- [ ] When a relationship is established dynamically at runtime, an initialization method (`@operation def initialize(self) -> None:`) is anchored directly to the registering entity
- [ ] Argument concepts introduced in operation descriptions map to typed positional arguments
- [ ] Domain string concepts representing names, descriptions, or identifiers declare specialized `NewType` definitions (e.g. `ToolName = NewType("ToolName", str)`, `ParameterName = NewType("ParameterName", str)`) rather than bare `str` primitives
- [ ] Untyped or heterogeneous values requiring existential or dependent type constraints at verification time declare a specialized `NewType` on `object` (e.g. `SomeParameterActualType = NewType("SomeParameterActualType", object)`); declaring `NewType` on `Any` is prohibited
- [ ] Wire-format representations declare explicit type aliases using Python 3.12 type syntax (`type WireType = str | int | float | bool | Mapping[str, WireType] | Sequence[WireType]`) rather than `NewType`, as `NewType` does not support union types
- [ ] Custom collection wrappers and bespoke named set classes (such as `UniqueNamedSet` or `*ParameterBindings`) are prohibited; associative collections map strictly to standard Python `Mapping[KT, VT]`
- [ ] Declaring `NewType` over collection types (such as `NewType("...", Mapping[...])`) is prohibited; collections remain standard parameterized `Mapping[KT, VT]`, `Set[T]`, and `Sequence[T]`
- [ ] Operations accepting arbitrary key-value inputs map parameters to `Mapping[str, Any]`, while operations accepting structured domain inputs map parameters to typed parameter models or domain data types
- [ ] Entities parameterized by actual, wire, element, or key and value types map to generic classes declared with Python 3.12 type parameter syntax (`class TypeName[T]:` or `class TypeName[ActualT, WireT]:`)
- [ ] Parameterized operations and properties use declared type parameters directly in parameter and return type annotations
- [ ] References to parameterized types declare explicit type arguments when known, reserving bare generic references or explicit `Any` type arguments strictly for heterogeneous collections
- [ ] Return types map deterministically to standard Python types: `str`, `int`, `bool`, `None`, and tuples for paired compound outcomes

## Invariants, Assumptions, Preconditions, and Postconditions

- [ ] Planning contracts are assigned deterministically to the owning structural entity: type-level guarantees and state consistency rules map to `INVARIANTS:`, caller/environment guarantees map to `ASSUMPTIONS:`, invocation prerequisites map to `PRECONDITIONS:`, and operational outcomes map to `POSTCONDITIONS:`
- [ ] Caller assumptions under `ASSUMPTIONS:` define caller-established domain facts, topological invariants, and environmental guarantees (such as graph acyclicity, valid workspace path bounds, or well-formed build manifests) that the callee accepts axiomatically; callee stubs and implementations never specify defensive checks, branch logic, or error outcomes for items under `ASSUMPTIONS:`
- [ ] Type invariants under `INVARIANTS:` define invariants preserved across instances of the class (such as name uniqueness within a collection)
- [ ] Subtypes inherit all `INVARIANTS:` and `ASSUMPTIONS:` from base types transitively; invariants and assumptions are conjoined and must never be duplicated or copied down into subtype docstrings
- [ ] Caller preconditions under `PRECONDITIONS:` state obligations that callers must establish at invocation time; overriding operations must not strengthen or add caller preconditions
- [ ] Invariants declared on a type hold across all operations of that type and are never repeated as preconditions on operations of that type
- [ ] Postconditions under `POSTCONDITIONS:` define observable outcomes, state updates, produced responses, and failure dispatch resulting from execution
- [ ] Overriding operations inherit supertype `POSTCONDITIONS:` and may only strengthen them with subtype-specific outcomes; derived components must not copy-paste unwoven base requirements
- [ ] Conditional requirements and failure branches are formulated as atomic normative clauses using exact syntax: `- WHEN <condition>, MUST <outcome>.`
- [ ] Unconditional postconditions, state updates, and invariants are formulated as normative assertions using exact syntax: `- MUST <outcome>.`
- [ ] When an operation returns a response record or produces diagnostic feedback on failure, postconditions specify the exact error string template or diagnostic phrase in double quotes (e.g. `MUST produce a ToolResponse with failed set to True, content starting with "Error: Unknown file '{path}'. Available files: ", and reminder "Only declared files can be inspected."`) so tests can assert exact content
- [ ] When an operation signature returns a pure value rather than a response record, failure branches map to declared domain exceptions (such as `@data_type class ...Error(ValueError):`) raised with diagnostic feedback formatted as specified in quotes and caught by the coordinating service to dispatch domain failure responses
- [ ] Unexpected system crashes, memory exhaustion, and uncontracted runtime exceptions are non-concerns excluded from specifications
- [ ] One-way conditional preservation — when source planning specifies "A when B", postconditions preserve it strictly as a one-way guarantee (`- WHEN B, MUST A.`); translating "when" into a biconditional or synthesizing the uncontracted converse (`- WHEN not B, MUST not A.`) is strictly prohibited unless explicitly contracted
- [ ] Constant properties from planning (such as a tool being named a specific string) declare explicit postconditions on the property method when first specialized in an interface: `- MUST return '<exact_name>'.`
- [ ] No verbatim copy-down to refinements/subtypes — postconditions do not need to be copied down to overrides or implementation stubs verbatim; if an override has nothing to add beyond its supertype contract, do not add anything (leave member body as `...`); the grounding process considers requirements in the type and all of its supertype declarations transitively
- [ ] Mentioning collaborators in low-level specs is prohibited — neither interface nor implementation stubs may name specific collaborator services, classes, or managers (such as NodeConfig, ToolManager, AliasManager) in docstrings, preconditions, or postconditions; state requirements state sources generically (e.g. `- MUST expose declared read-only files from other objects.`), deferring collaborator resolution strictly to Groundtalk (`grounding/*.gt`)
- [ ] Data provenance in postconditions — operations and properties producing composite records or transformed data specify explicit derivation rules for constituent fields, avoiding floating output records with ungrounded fields
- [ ] Sections without entries are omitted rather than left with empty headers

## Common pitfalls

- [ ] Relational logic leakage — including `NEW_PREDICATES:`, `RULES:`, or `GROUNDING_*` clauses in low-level specifications
- [ ] Using passive descriptive prose instead of normative `WHEN <condition>, MUST <outcome>.` clauses
- [ ] Conflating multiple failure modes into a single compound requirement bullet instead of writing atomic bullets
- [ ] Repeating structural AST facts (properties, base classes, return types, or required response record fields) as requirement bullets under `POSTCONDITIONS:`
- [ ] Redundant type requirements — writing requirement bullets that merely restate guarantees already enforced by static types
- [ ] Redundant precondition repetition — repeating an invariant of a type as a precondition on an operation within that type
- [ ] Copy-down requirement duplication — copying down unwoven base protocol requirements (such as generic Tool requirements) into subtype specifications instead of leveraging transitive contract inheritance
- [ ] Clobbering generic type parameters or variant hierarchies during alignment reconciliation
- [ ] Using string literals or runtime values for lifecycle tiers instead of `ChildTierOf[ParentTier]` and `InTier[TierType]`
- [ ] Vague failure outcomes — writing failure postconditions with paraphrased descriptions instead of exact quoted error templates or phrases
- [ ] Free-floating `#` comments outside triple-quoted docstrings
- [ ] Missing `@operation` decorator on non-property methods
- [ ] Missing type annotations on operation parameters or return types
- [ ] Using `pass` or executable logic in member bodies instead of `...`
- [ ] Attributing service operations or failure rules to passive `@data_type` records instead of active services or top-level `__orphan__()`
- [ ] Defining redundant `__init__` or `@property` getters on dataclasses instead of declaring fields documented under `Args:` in class docstring
- [ ] Generic type names and collisions — naming domain types or variants with bare generic words (such as `Response`, `Parameter`, `Config`) or standard collection names (like `List` or `Dictionary`) instead of domain-qualified names
- [ ] Translating if to if and only if — expanding a one-way conditional (`- WHEN B, MUST A.`) into a biconditional with an invented converse (`- WHEN not B, MUST not A.`)
- [ ] Mentioning collaborators in docstrings — naming specific collaborator classes, services, or managers in `low/*.pyi` docstrings instead of stating obligations generically (e.g. "from other objects")
- [ ] Declaring NewType on Any or union types — using `NewType("...", Any)` instead of `NewType("...", object)`, or attempting to use `NewType` for union types instead of Python 3.12 type aliases (`type WireType = ...`)
- [ ] Origin amnesia — specifying that an operation or property produces a composite record without defining derivation rules for its constituent fields
