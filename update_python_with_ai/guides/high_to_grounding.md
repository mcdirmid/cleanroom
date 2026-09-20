# Guide: High-Level to Grounding Specification Alignment

## Summary

The artifact is a Python stub grounding specification (`<name>.pyi`) that structurally grounds a High-Level Specification (`high/<name>.md`). In a multi-node session, multiple grounding specifications are processed together; each target is identified by its file alias relative path, and each target is submitted individually via `submit(target="<target_file>", change_summary="...")` when complete (in single-target sessions, the target parameter may be omitted). The artifact conforms to this guide and Cleanroom's static AST specification grammar. External boundary specifications (`high/<name>_ext.md`) ground to external boundary stubs (`<name>_ext.pyi`) describing external API mechanics, foreign serialization formats, and third-party SDKs through module docstrings without Python AST code, providing domain knowledge that fulfills grounding promises for importing implementation specifications. Assembly specifications (`high/<name>_asm.md`) ground to assembly stubs (`<name>_asm.pyi`) defining a top-level `__initialize__()` function whose docstring lists constituent implementation and sub-assembly modules under `CONSTITUENTS:`. Specifications declare zero-implementation structural stubs with complete static type annotations, ontological classification decorators imported from `framework`, and co-located docstrings containing ontological purposes, operational preconditions, and behavioral guarantees. Inherited contracts under `INHERITED_REQUIREMENTS:` and `INHERITED_ASSUMPTIONS:`, as well as ancestor member stubs decorated with `@override`, are calculated and synchronized automatically by tooling; they are never manually authored or modified.

Component lifecycles and visibilities are governed by explicit decorator arguments (`@singleton_type("system")` or subordinate tier names defined by interface components), while open interfaces take `@poly_type` without lifecycle arguments, value records take `@data_type`, and discriminated branches take `@variant`. Data types with public constructors declare `@dataclass(frozen=True)` (or `init=True`) with a matching `__init__` method, while factory-constructed data types and base types with variants specify `@dataclass(frozen=True, init=False)` without `__init__`. All members are declared as methods decorated with `@property` or `@operation` with pure ellipsis bodies. Authored requirements and assumptions are written strictly under `FRESH_REQUIREMENTS:` and `FRESH_ASSUMPTIONS:`, leaving inherited sections and generated `@override` stubs untouched; implementation stubs omit `FRESH_REQUIREMENTS:` when contracts are completely defined by the interface. Implementation components directly import their implemented interface modules, subclassing qualified interface classes with 1:1 class name parity without requiring dedicated 1:1 interface specifications. Behavioral requirements not attributable to an active service are captured under `FRESH_REQUIREMENTS:` in an unnested top-level `__orphan__()` function.

> META: "Grounding specifications translate literate high-level specs into formal Python interface stubs, contracts, and requirement docstrings."

## Lint checks

- [ ] In non-external specifications, top-level statements consist strictly of `import`, `from ... import ...`, `class` definitions, optional top-level `LifecycleTier` declarations in interface specifications, at most one `def __orphan__() -> None:` function (in non-assembly specs), at most one `def __initialize__() -> None:` function (in assembly specs `<name>_asm.pyi`), and an optional module docstring
- [ ] External specification stubs (`<name>_ext.pyi`) contain strictly a module docstring containing `## External Mechanics & API Documentation`, `## Build Dependencies`, and `## Usage Snippets` sections without Python AST code
- [ ] Defining top-level functions other than `__orphan__()` (or `__initialize__()` in assembly specs), or nesting these functions within a class, is prohibited
- [ ] Top-level `__orphan__()` and `__initialize__()` functions have no decorators, take no parameters, return `None`, and contain strictly a docstring followed by an ellipsis (`...`)
- [ ] Top-level `__orphan__()` docstrings contain strictly `PURPOSE:` and `FRESH_REQUIREMENTS:` sections, while `__initialize__()` docstrings contain strictly `PURPOSE:` and `CONSTITUENTS:` sections
- [ ] Every class definition is decorated with exactly one structural kind decorator from `framework`: `@singleton_type("<tier>")`, `@poly_type`, `@data_type`, or `@variant`
- [ ] `@singleton_type` is called with an explicit lifecycle string argument: `"system"` or a subordinate tier name defined in an interface specification
- [ ] `@poly_type`, `@data_type`, and `@variant` decorators take no arguments
- [ ] Direct inheritance from `SystemService` or `AgentSessionService` is prohibited
- [ ] `@variant` classes inherit from a `@data_type` or another `@variant`, never from an active service
- [ ] `@singleton_type` and `@poly_type` classes inherit from polymorphic interfaces or abstract service classes, never from data types
- [ ] `@data_type` classes never inherit from active services
- [ ] Every `@data_type` declares at least one property or base type, or serves as a variant sum-type root in the module
- [ ] Every class member is decorated with either `@property` or `@operation`
- [ ] Decorating a member with both `@property` and `@operation`, or with neither, is prohibited
- [ ] Overriding and inherited ancestor members are decorated with `@override` alongside `@property` or `@operation`
- [ ] Every class member takes `self` as its first parameter
- [ ] `@property` methods take only `self` and declare a return type annotation
- [ ] `@operation` methods declare type annotations for all positional parameters after `self` and declare a return type annotation
- [ ] Every class and member body consists strictly of an optional docstring followed by an ellipsis (`...`)
- [ ] Executable statements, assignments, expressions, loops, conditionals, and `pass` are prohibited in class and member bodies
- [ ] Every class and member docstring begins with a `PURPOSE:` section
- [ ] Docstring section headers are closed strictly to `PURPOSE:`, `CONSTITUENTS:`, `INHERITANCE:`, `FRESH_ASSUMPTIONS:`, `INHERITED_ASSUMPTIONS:`, `FRESH_REQUIREMENTS:`, `INHERITED_REQUIREMENTS:`, and `GROUNDING_ARGUMENT:`
- [ ] `GROUNDING_ARGUMENT:` sections are permitted exclusively in implementation specifications (`<name>_impl.pyi`) on `@singleton_type` classes and their `@operation` or `@property` methods
- [ ] `GROUNDING_ARGUMENT:` sections in non-implementation specifications or on non-singleton classes are prohibited
- [ ] Obsolete docstring headers `REQUIREMENTS:`, `ASSUMPTIONS:`, and `INHERITED FROM <Ancestor>:` are prohibited
- [ ] Entries under `CONSTITUENTS:`, `INHERITANCE:`, `FRESH_ASSUMPTIONS:`, `INHERITED_ASSUMPTIONS:`, `FRESH_REQUIREMENTS:`, and `INHERITED_REQUIREMENTS:` start with `- `
- [ ] All type annotations resolve to builtins, standard `typing` primitives, declared local classes, or imported symbols

## Document layout and imports

- [ ] Specifications import structural decorators (`singleton_type`, `poly_type`, `data_type`, `variant`, `operation`, `override`) from `framework`
- [ ] Standard collection and meta-type primitives are imported from `typing` (`Optional`, `Union`, `Tuple`, `List`, `Set`, `Sequence`, `Any`, `Type`, `Dict`)
- [ ] Imported types from sibling specifications use direct symbol imports (`from <module> import <Type>`) or module imports (`import <module>`), including module imports of external boundary components that fill grounding gaps
- [ ] In implementation specifications (`<name>_impl.pyi`), the implemented interface modules declared under `implements:` are imported directly (`import <module>`)
- [ ] Implementation classes preserve exact 1:1 name parity with their implemented interface class rather than appending an `Impl` suffix
- [ ] Implementation classes subclass the qualified interface class (`class Service(<module>.Service):`)
- [ ] Assembly specifications (`<name>_asm.pyi`) define strictly a `def __initialize__() -> None:` function with `PURPOSE:` and `CONSTITUENTS:` docstring sections listing constituent modules
- [ ] Free-floating `#` comments are prohibited; all narrative justifications and contracts live exclusively inside triple-quoted docstrings
- [ ] Classes are separated by two blank lines, and class members are separated by one blank line

## Ontological classification

- [ ] Entities introduced in `high/<name>.md` with `*system* service` map to `@singleton_type("system")`
- [ ] Entities introduced in `high/<name>.md` with a specific singleton service tier (e.g. `*<tier_name>* service`) map to `@singleton_type("<tier_name>")`
- [ ] Subordinate lifecycle tiers introduced in `high/<name>.md` map to a module-level annotated declaration `<tier_name>: LifecycleTier` in the corresponding interface specification
- [ ] Entities introduced in `high/<name>.md` with `polymorphic service` or open multiton interfaces map to `@poly_type`
- [ ] Passive entities, value objects, structural records, and identifiers map to `@data_type`
- [ ] Discriminated sub-classifications and sum-type branches map to `@variant` subclassing their base data type
- [ ] Data types constructed exclusively through service operations declare `@dataclass(frozen=True, init=False)` and do not declare `def __init__`
- [ ] Leaf data types with direct public construction declare `@dataclass(frozen=True, init=True)` (or default `@dataclass(frozen=True)`) and define a matching `def __init__(self, ...): ...`
- [ ] Instances can only be created from leaf data types without variants or leaf variant branches; base types with variants and sum-type roots never declare `def __init__`
- [ ] Polymorphic types never declare lifecycle tiers in their docstrings or class decorators
- [ ] Entities parameterized by actual, wire, element, or key and value types map to generic classes declared with Python 3.12 type parameter syntax (`class TypeName[T]:` or `class TypeName[ActualT, WireT]:`)
- [ ] Singletons never declare containment hierarchies; services in the same tier access each other as flat peer collaborators
- [ ] Data types never inherit from active services or polymorphic interfaces

## Members and signatures

- [ ] Attributes, exposed states, and entity references introduced as italicized nouns in `high/<name>.md` map to `@property` methods
- [ ] Actions, capabilities, and callable behaviors introduced as italicized verbs in `high/<name>.md` map to `@operation` methods
- [ ] Italicized argument concepts introduced in operation descriptions map to typed positional arguments
- [ ] Operations and properties of parameterized types use the declared type parameters directly in parameter and return type annotations
- [ ] Unbound references to parameterized entities in heterogeneous collections use bare generic references or explicit `Any` type arguments (e.g. `Sequence[Parameter]`)
- [ ] Return types map deterministically to standard Python types: `str` for strings, `int` for integers, `bool` for booleans, `None` for unit returns
- [ ] Meta-type references whose values are data type symbols map to `Type` (or `Type[T]`)
- [ ] Optional concepts map to `Optional[T]`
- [ ] Alternating outcomes map to `Union[T1, T2]`
- [ ] Unordered entity collections map to `Set[T]`
- [ ] Ordered sequences map to `List[T]`
- [ ] Paired records map to `Tuple[T1, T2]`
- [ ] Self-references and forward references use string literals (e.g. `-> "EntityName"`)
- [ ] Every `@data_type` declares at least one property participating in its structural identity
- [ ] Grounding operations that govern relational or identity-sensitive requirements (such as matching a specific resource, entity, or state) declare explicit parameters, metadata markers, or collaborator lookup operations to distinguish targets; grounding operations without the arguments or attributes necessary to evaluate requirement conditions is prohibited

## Docstring contracts

- [ ] Every class docstring begins with `PURPOSE:` containing the ontological justification sentence from `high/<name>.md`
- [ ] If a class subclasses secondary bases or interfaces, `INHERITANCE:` records each base with its justification (`- <BaseName>: <Justification>`)
- [ ] Preconditions and environment constraints from `high/<name>.md` are formulated as complete sentences under `FRESH_ASSUMPTIONS:`
- [ ] Behavioral invariants, validation rules, state transitions, and postconditions from `high/<name>.md` are formulated as complete sentences under `FRESH_REQUIREMENTS:`; in implementation specifications (`<name>_impl.pyi`), `FRESH_REQUIREMENTS:` are omitted when all behavioral obligations are defined on the implemented interface and inherited under `INHERITED_REQUIREMENTS:`
- [ ] `INHERITED_ASSUMPTIONS:` and `INHERITED_REQUIREMENTS:` sections are generated and updated automatically by tooling and are never manually authored or modified
- [ ] Every property and operation docstring contains a `PURPOSE:` section explaining why the member exists
- [ ] Operation preconditions (conditions caller must guarantee) are placed under `FRESH_ASSUMPTIONS:`
- [ ] Operation postconditions, return guarantees, state updates, and explicit failure-handling rules are placed under `FRESH_REQUIREMENTS:`
- [ ] Requirements articulate verifiable behavioral guarantees, state transitions, and return values, keeping ontological 'why' explanations and motivational clauses strictly inside `PURPOSE:`
- [ ] Exact logical qualifications from `high/<name>.md` (such as 'if, but not only if,') are preserved verbatim in requirements without omission or simplification
- [ ] Sentences under `FRESH_REQUIREMENTS:` and `FRESH_ASSUMPTIONS:` end with a period (`.`)
- [ ] In implementation specifications (`<name>_impl.pyi`), `GROUNDING_ARGUMENT:` sections articulate the concrete derivation path, collaborator wiring, and parameter provenance satisfying requirements; well-groundedness is the default and ritual boilerplate ("Well-grounded." prefixes) is omitted, while ungrounded gaps are exceptional and explicitly flagged
- [ ] Property `GROUNDING_ARGUMENT:` reasoning establishes where property values originate through an explicit derivation path (delegated from an imported collaborator, populated via mutable operations, or set via configuration operations); vague phrases such as "loaded from external data source" or "derived from environment" are prohibited without specifying the context provider, loader service operation, and return transformation
- [ ] `GROUNDING_ARGUMENT:` reasoning verifies that collaborator singletons exist in the same lifecycle tier or an ancestor lifecycle tier (descendant tiers can access ancestor tiers, but ancestor tiers cannot access descendant tiers) and that the collaborator's defining specification is imported
- [ ] `GROUNDING_ARGUMENT:` reasoning assumes that requirements of un-implemented collaborator types hold to satisfy implementation obligations
- [ ] Grounding argument reasoning explicitly establishes how conditional and relational requirements (such as operations affecting matching entities or the same resource) are distinguished from distinct entities or resources, without hand-waving unpassed context
- [ ] Behavioral requirements not attributable to an active service (such as external boundary behaviors in boundary specifications) are recorded under `FRESH_REQUIREMENTS:` in a top-level `__orphan__()` function
- [ ] Sections without entries are omitted rather than left with empty headers

## Common pitfalls

- [ ] Ritual grounding prefixes — prefixing `GROUNDING_ARGUMENT:` entries with boilerplate phrases like "Well-grounded." instead of directly stating the derivation path and collaborator wiring
- [ ] Hand-waving external data in grounding — writing phrases like "Loaded from external data source" without naming the collaborator providing the context key and the collaborator performing the load
- [ ] Manually writing, modifying, or removing `INHERITED_REQUIREMENTS:` or `INHERITED_ASSUMPTIONS:` sections, which are synchronized automatically by tooling
- [ ] Manually copying or synthesizing ancestor member stubs decorated with `@override`, which are injected automatically by tooling
- [ ] Decorating members with obsolete `@inherited` decorator
- [ ] Missing `@operation` decorator on non-property methods
- [ ] Using legacy `REQUIREMENTS:` or `ASSUMPTIONS:` headers instead of `FRESH_REQUIREMENTS:` and `FRESH_ASSUMPTIONS:`
- [ ] Mixing purpose into requirements — including explanatory 'why' clauses or concept justifications under `FRESH_REQUIREMENTS:` instead of placing them under `PURPOSE:`
- [ ] Scrubbing logical qualifications — omitting or simplifying precise logical qualifications from HLS (such as 'if, but not only if') when formulating requirements
- [ ] Specifying lifecycle tiers on `@poly_type` classes
- [ ] Empty data types lacking properties or base types
- [ ] Attributing external service mechanics as behavioral requirements on passive `@data_type` records instead of using top-level `__orphan__()`
- [ ] Adding arguments, decorators, or non-ellipsis bodies to `__orphan__()`
- [ ] Using `pass` or executable statements in member bodies instead of `...`
- [ ] Adding artificial suffixes (`Impl`) to implementation class names instead of preserving 1:1 name parity with the interface
- [ ] Free-floating `#` comments outside docstrings
- [ ] Qualifying `typing` primitives as `typing.<Symbol>` instead of importing from `typing`
- [ ] Missing type annotations on operation parameters or return types
- [ ] Placing tool execution or editing workflow rules in checklist sections instead of `## Summary`
- [ ] Grounding relational or entity-matching requirements into operations that lack parameters or context to distinguish entities, creating ungrounded identity shortcuts
- [ ] Exposing file paths — using filesystem paths (e.g. `grounding/<name>.pyi`) instead of virtual file names (`<name>.pyi`)
