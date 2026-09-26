# Guide: High-Level to Grounding Specification Alignment

## Summary

The artifact is a Python stub grounding specification (`grounding/<name>.pyi`) that structurally grounds `high/<name>.md` and `requirements/<name>.md`, submitted via `submit(target="<target_file>", change_summary="...")`. External specifications (`grounding/<name>_ext.pyi`) contain module docstrings without AST code. Assembly specifications (`high/<name>_asm.md`) ground to stubs (`grounding/<name>_asm.pyi`) defining `__initialize__()` with `CONSTITUENTS:`. Specifications declare structural stubs with static type annotations, ontological classification decorators from `framework`, lifecycle tier declarations from `support.lib.lifecycle`, and docstring contracts with direct `REQUIREMENTS:` and `ASSUMPTIONS:`.

Root tiers subclass `RootTier`, subordinate tiers subclass `ChildTierOf[ParentTier]`, and singleton services inherit `InTier[TierType]`. Classes, type parameters, properties, operations, and tier memberships materialize in the AST. Types, records, and variants use domain-qualified compound names (e.g. `CommandResult`, `QueryFilter`, `WidgetPayload`) reflecting domain roles; bare, context-free generic names (such as `Response`, `Parameter`, `Config`, `Data`, `Result`) and standard collection collisions (`List`, `Dictionary`, `Set`) are prohibited. Docstrings state conditions and outcomes derived from prototype invariants across the specification. Requirements not bound to an active service live under `REQUIREMENTS:` in top-level `__orphan__()`.

> META: "Grounding specifications translate term-oriented high-level specs into formal Python interface stubs, type-level tier hierarchies, and atomic normative requirement contracts."

## Lint checks

- [ ] Top-level statements consist strictly of imports, classes, type aliases, at most one `def __orphan__() -> None:` (non-assembly specs), at most one `def __initialize__() -> None:` (assembly specs `<name>_asm.pyi`), and optional module docstrings
- [ ] External specification stubs (`<name>_ext.pyi`) contain strictly a module docstring with `## External Mechanics & API Documentation`, `## Build Dependencies`, and `## Usage Snippets` sections without Python AST code
- [ ] Top-level `__orphan__()` and `__initialize__()` take no parameters, return `None`, have no decorators, and contain strictly a docstring followed by `...`
- [ ] Top-level `__orphan__()` docstrings contain strictly a summary and `REQUIREMENTS:`; `__initialize__()` docstrings contain strictly a summary and `CONSTITUENTS:`
- [ ] Every class definition is decorated with exactly one structural kind decorator: `@singleton_type`, `@poly_type`, `@data_type`, or `@variant`
- [ ] `@singleton_type` designates an active service or tier definition, expressing subordinate tier membership through `InTier[TierType]`
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
- [ ] Docstring section headers are closed strictly to `Args:`, `Returns:`, `CONSTITUENTS:`, `ASSUMPTIONS:`, `REQUIREMENTS:`, `GROUNDING_PROVISIONS:`, `GROUNDING_ARGUMENT:`, `GROUNDING_REQUIREMENTS:`, `GROUNDING_ASSUMPTIONS:`, and `GROUNDING_IMPLEMENTS:`
- [ ] `GROUNDING_ARGUMENT:` sections are permitted exclusively in implementation specifications (`<name>_impl.pyi`) on `@singleton_type` classes and their members
- [ ] Obsolete docstring headers (`PURPOSE:`, `INHERITANCE:`, `FRESH_REQUIREMENTS:`, `FRESH_ASSUMPTIONS:`, `INHERITED_REQUIREMENTS:`, `INHERITED_ASSUMPTIONS:`) are prohibited
- [ ] Entries under `CONSTITUENTS:`, `ASSUMPTIONS:`, `REQUIREMENTS:`, `GROUNDING_PROVISIONS:`, `GROUNDING_REQUIREMENTS:`, `GROUNDING_ASSUMPTIONS:`, and `GROUNDING_IMPLEMENTS:` start with `- `
- [ ] Sentences under `REQUIREMENTS:` and `ASSUMPTIONS:` end with a period (`.`)
- [ ] Requirements covered by static types (return types, non-null fields, parameter types) are prohibited; `REQUIREMENTS:` contains strictly dynamic behaviors, branches, failure dispatch, and state transitions
- [ ] Preconditions under `ASSUMPTIONS:` on operations state caller obligations at invocation time rather than passive system invariants
- [ ] Types, records, and variants avoid bare generic names (such as `Response`, `Parameter`, `Config`, `Data`, `Result`) and primitive collisions (`List`, `Dictionary`, `Set`), using domain-qualified names instead (e.g. `CommandResult`, `QueryFilter`, `WidgetPayload`, `ElementSequence`)

## Document layout and imports

- [ ] Specifications import structural decorators (`singleton_type`, `poly_type`, `data_type`, `variant`, `operation`, `override`) from `framework`
- [ ] Specifications import lifecycle tier primitives (`ChildTierOf`, `RootTier`, `SystemTier`, `InTier`, `get_tier`) from `support.lib.lifecycle`
- [ ] Standard collection and meta-type primitives are imported from `typing`
- [ ] Imported types from sibling or external specifications use direct symbol imports (`from <module> import <Type>`) or module imports (`import <module>`)
- [ ] Implementation specifications (`<name>_impl.pyi`) import implemented interface modules directly (`import <module>`) and preserve 1:1 class name parity
- [ ] Assembly specifications (`<name>_asm.pyi`) define strictly `def __initialize__() -> None:` with a summary description and `CONSTITUENTS:` docstring section listing constituent modules
- [ ] Free-floating `#` comments are prohibited; all narrative justifications and contracts live exclusively inside triple-quoted docstrings
- [ ] Classes are separated by two blank lines, and class members are separated by one blank line

## Ontological classification and lifecycle tiers

- [ ] Stateful coordinators or singletons map to `@singleton_type` classes inheriting `InTier[TierType]`
- [ ] Root lifecycle tiers subclass `RootTier`; subordinate lifecycle tiers subclass `ChildTierOf[ParentTier]` decorated with `@singleton_type("system")`
- [ ] Members of a lifecycle tier express tier membership by inheriting `InTier[TierType]` on their class definition
- [ ] Interfaces define lifecycle tiers as static types rather than runtime factory values
- [ ] Open multiton capabilities or polymorphic actions map to `@poly_type` without lifecycle arguments
- [ ] Passive entities, value objects, structural records, and messages map to `@data_type`
- [ ] Discriminated sub-classifications and closed sum-type branches map to `@variant` subclassing their base data type
- [ ] Base data types with variants and sum-type roots declare `@dataclass(frozen=True, init=False)` with body `...`
- [ ] Leaf `@data_type` and `@variant` classes declare `@dataclass(frozen=True)` and define state directly as typed dataclass fields (`field_name: Type = ...`), automatically synthesizing constructor parameters and immutable properties
- [ ] Types, branded types, and variants never use bare generic names (such as `Response`, `Parameter`, `Config`, `Data`, `Result`) or primitive collisions (`List`, `Dictionary`, `Set`, `Map`); use domain-qualified compound names (e.g. `CommandResult`, `QueryFilter`, `WidgetPayload`, `ElementSequence`)
- [ ] Dataclass fields on `@data_type` and `@variant` classes are documented under `Args:` in the class docstring; explicit `def __init__` methods or `@property` getters on dataclasses are prohibited
- [ ] Structural facts (such as base inheritance, closed variant sets, tier membership, and type bounds) are expressed directly in the Python AST and are never recorded as narrative requirement bullets under `REQUIREMENTS:` or in `__orphan__()`
- [ ] Singletons never declare containment hierarchies; services in the same tier access each other as flat peer collaborators
- [ ] Data types never inherit from active singleton services; a data type may extend a stateless `@poly_type` protocol provided all polytype requirements are satisfied

## Members and signatures

- [ ] Attributes, exposed states, and entity references in active services and polymorphic interfaces (`@singleton_type`, `@poly_type`) map to `@property` methods, whereas state fields in `@data_type` and `@variant` classes map directly to typed dataclass fields
- [ ] Actions, capabilities, and callable behaviors introduced as italicized verbs in `high/<name>.md` map to `@operation` methods
- [ ] When a relationship is established dynamically at runtime (such as self-registering an extension), an initialization method (`@operation def initialize(self) -> None:`) is anchored directly to the registering entity
- [ ] Italicized argument concepts introduced in operation descriptions map to typed positional arguments
- [ ] Operations accepting arbitrary key-value inputs map parameters to `Mapping[str, Any]`, while operations accepting structured domain inputs map parameters to typed parameter models or domain data types
- [ ] Entities parameterized by actual, wire, element, or key and value types map to generic classes declared with Python 3.12 type parameter syntax (`class TypeName[T]:` or `class TypeName[ActualT, WireT: WireBound]:`)
- [ ] Parameterized operations and properties use declared type parameters directly in parameter and return type annotations
- [ ] References to parameterized types declare explicit type arguments when known, reserving bare generic references or explicit `Any` type arguments strictly for heterogeneous collections
- [ ] Return types map deterministically to standard Python types: `str`, `int`, `bool`, `None`, and tuples for paired compound outcomes
- [ ] Meta-type references whose values are data type symbols map to `Type` (or `Type[T]`)
- [ ] Grounding operations governing relational requirements declare explicit parameters or collaborator lookup operations to distinguish targets; grounding operations without arguments necessary to evaluate requirement conditions is prohibited

## Docstring contracts and normative requirements

- [ ] Every class and property docstring begins with a summary description containing the ontological justification sentence from `high/<name>.md`
- [ ] Every operation docstring provides an `Args:` section documenting parameters and semantics especially when unstructured types are used
- [ ] Every operation returning a non-None value provides a `Returns:` section summarizing the produced result or response
- [ ] Class inheritance and interface implementation are expressed directly in Python AST class definitions (`class Sub(Base):`); redundant docstring inheritance annotations are prohibited
- [ ] Each operation projects prototypes and invariants across `high/<name>.md` into operation-specific caller preconditions (`ASSUMPTIONS:`) or behavioral outcomes (`REQUIREMENTS:`)
- [ ] Preconditions on operations placed under `ASSUMPTIONS:` describe caller obligations at invocation time rather than passive global invariants
- [ ] Behavioral invariants, validation rules, state transitions, postconditions, and failure rules from `high/<name>.md` are placed under `REQUIREMENTS:`
- [ ] Requirements covered by static types (return types, non-null fields, or parameter types) are prohibited; `REQUIREMENTS:` contains strictly dynamic behaviors, conditional branches, failure dispatch, and state transitions
- [ ] Overriding operations can specialize their return type to a covariant subtype; when failure is eliminated by type specialization, failure-handling requirements are omitted
- [ ] Conditional requirements and failure branches are formulated as atomic normative clauses using exact syntax: `- WHEN <condition>, MUST <outcome>.`
- [ ] Unconditional postconditions, state updates, and invariants are formulated as normative assertions using exact syntax: `- MUST <outcome>.`
- [ ] Compound conditions in `high/<name>.md` are decomposed into distinct atomic requirement bullets rather than combined into a single compound sentence
- [ ] Operational failure is treated as a standard outcome branch modeled preferentially on domain response or outcome records
- [ ] When an operation can fail but its returned value cannot be augmented to represent failure, the return type is unioned with a dedicated failure data type (`ReturnType | OperationFailure`) carrying diagnostic failure details
- [ ] When an operation fails with diagnostic feedback, requirement outcomes specify concrete CommonMark string templates or phrases so tests can assert exact content
- [ ] Pre-invocation resolution, conversion, and validation failures return domain failure responses with concrete CommonMark failure strings
- [ ] Polymorphic operations returning response objects specify concrete CommonMark failure strings for each component failure condition in HLS
- [ ] Requirements strictly reflect the behavioral mandates of `high/<name>.md` without unmandated embellishment
- [ ] Grounding clauses (`GROUNDING_PROVISIONS:`, `GROUNDING_REQUIREMENTS:`, `GROUNDING_ASSUMPTIONS:`, `GROUNDING_IMPLEMENTS:`) declare reachability contracts using `- action("verb", TargetType, [prep, AuxType]): <justification>` and `- knows(text_type, pyi_type): <justification>` referencing numbered requirements
- [ ] Grounding facts formalize the knowledge and action plans authored in `requirements/<name>.md` rather than pattern-matching Python member names or creating tautological self-referential actions
- [ ] Action verbs in grounding facts are descriptive snake_case terms (e.g. `validate_access_token`, `parse_payload`, `dispatch`), avoiding vague words (`process`), member-name echoes, or spaces/slashes
- [ ] Grounding facts target domain types and never mention collaborator services or types; collaborator resolution is strictly inferred by reachability over component imports and lifecycle tiers
- [ ] In `knows(text_type, pyi_type)`, `text_type` is a descriptive snake_case term identifying the domain concept (e.g. `"token_quota"`, `"cache_ttl"`), never duplicating the Python property or type name; `pyi_type` specifies the structural Python type
- [ ] Properties providing domain state or observations require `GROUNDING_PROVISIONS:` declaring what they provide; in implementation specifications (`<name>_impl.pyi`), these properties define a `GROUNDING_ARGUMENT:` explaining how that provision is satisfied
- [ ] In implementation specifications (`<name>_impl.pyi`), `GROUNDING_ARGUMENT:` sections articulate concrete derivation paths, collaborator wiring, and parameter provenance satisfying requirements
- [ ] Actions acting upon or registering the instance itself use `Self` (from `typing`) as target type; actions converting an input target the converted entity; specifying over-generalized supertypes is prohibited
- [ ] When an operation coordinates constituent concepts defined elsewhere, grounding decomposes the coordination into discrete atomic `WHEN ... MUST ...` requirement bullets mandated by those constituent contracts
- [ ] Behavioral requirements not attributable to an active service are placed under `REQUIREMENTS:` in a top-level `__orphan__()` function
- [ ] Sections without entries are omitted rather than left with empty headers
- [ ] Alignment reconciles High-Level Specification changes while preserving existing generic type parameters, bounds, and variant hierarchies

## Common pitfalls

- [ ] Using passive descriptive prose instead of normative `WHEN <condition>, MUST <outcome>.` clauses
- [ ] Conflating multiple failure modes into a single compound requirement bullet instead of writing atomic bullets
- [ ] Repeating structural AST facts (properties, base classes, return types, or required response record fields) as requirement bullets under `REQUIREMENTS:`
- [ ] Redundant type requirements — writing requirement bullets that merely restate guarantees already enforced by static types
- [ ] Passive operational assumptions — stating preconditions on operations as passive global invariants instead of caller-facing constraints on arguments at invocation time
- [ ] Neglecting chained reasoning — overlooking prototype invariants across `high/<name>.md` when grounding an operation
- [ ] Embellishment — fabricating unmandated qualifications, adverbs, or constraints that lack semantic basis in `high/<name>.md`
- [ ] Composite collapse — collapsing coordination of constituent concepts into a single summary requirement bullet
- [ ] Clobbering generic type parameters or variant hierarchies during alignment reconciliation
- [ ] Using string literals or runtime values for lifecycle tiers instead of `ChildTierOf[ParentTier]` and `InTier[TierType]`
- [ ] Inventing multi-class wrapper hierarchies or uncontracted exceptions instead of augmenting domain records or using failure unions
- [ ] Vague failure outcomes — writing failure requirements without specifying concrete CommonMark feedback strings or diagnostic messages
- [ ] Using obsolete `FRESH_` or `INHERITED_` headers instead of direct `REQUIREMENTS:` and `ASSUMPTIONS:`
- [ ] Manually copying or synthesizing ancestor member stubs decorated with `@override`
- [ ] Free-floating `#` comments outside triple-quoted docstrings
- [ ] Missing `@operation` decorator on non-property methods
- [ ] Missing type annotations on operation parameters or return types
- [ ] Using `pass` or executable logic in member bodies instead of `...`
- [ ] Attributing service operations or failure rules to passive `@data_type` records instead of active services or top-level `__orphan__()`
- [ ] Defining redundant `__init__` or `@property` getters on dataclasses instead of declaring fields documented under `Args:` in class docstring
- [ ] Undocumented naked types — using unstructured primitive or generic types (such as `Mapping[str, Any]`) without an `Args:` docstring section explaining domain semantics
- [ ] Artificial PURPOSE headers — using legacy `PURPOSE:` docstring headers instead of standard Python docstrings with a summary, `Args:`, and `Returns:` sections
- [ ] Over-generalized grounding provision types — specifying a general base type instead of the specific type in `GROUNDING_PROVISIONS:`
- [ ] Generic type names and collisions — naming domain types or variants with bare generic words (such as `Response`, `Parameter`, `Config`) or standard collection names (like `List` or `Dictionary`) instead of domain-qualified names
- [ ] Pattern-matched grounding facts — mechanically echoing member names in action/knows predicates instead of formalizing planned domain knowledge and actions from `requirements/<name>.md`
