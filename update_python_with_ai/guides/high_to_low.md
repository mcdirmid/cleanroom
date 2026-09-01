# Guide: Converting a High-Level Specification to a Low-Level Specification

## Summary

The artifact is the low-level specification (LLS) for a component: it conforms to the LLS structure this guide states and aligns with the component's HLS and its closure. The component kind is determined strictly by filename stem: `<name>_impl.md` is an implementation spec (its HLS declares `implements: <type>`), `<name>_asm.md` is an assembly spec, `<name>_ext.md` is an external boundary spec, and any other `<name>.md` is an interface spec. The conversion reads the immediate HLS and the immediate LLS closure, adapting the LLS minimally in place and filling in templates.

The LLS is the HLS elaborated, never replaced: every behavioral requirement, transformation, precondition, outcome, and failure condition from the immediate HLS is woven into the LLS without dropping details. When an interface defers concrete failure feedback or formatting, the implementation LLS explicitly captures it. External boundary specs (`*_ext.md`) add external information into their LLS that is not purely derivable from their HLS, defining concrete foreign schemas, serialization formats, and third-party signatures for the rest of the system. The LLS is a stand-alone document used without the HLS.

## Front matter

- [ ] A component whose filename stem does not end in `_impl` or `_asm` is an interface — its LLS is `# Interface LLS: <name>`, or `# External LLS: <name>` for an external boundary spec (`*_ext.md`); an implementation LLS exists when the filename ends in `_impl` (`# Implementation LLS: <name>_impl`), and an assembly LLS exists when the filename ends in `_asm` (`# Implementation LLS: <name>_asm`)
- [ ] Filenames use underscores; no hyphens anywhere — high- and low-level specs are distinguished by directory (`high/<name>.md` vs `low/<name>.md`), not by filename suffix
- [ ] The dependency comment is the file's first line — the LLS's only front matter: no `terms (owned):` or `terms from <dep>:` section; a `terms from <dep>:` entry becomes a dependency-comment entry
- [ ] LLS dependencies are expressed through interfaces or external specs, never implementation LLS files; a type is imported from its owner's LLS, never through a re-exporting interface
- [ ] The one exception: an assembly LLS's dependency comment lists the implementation (`- <name>_impl.md`) and assembly (`- <name>_asm.md`) LLS files it assembles — the only LLS kind permitted to depend on implementation or assembly LLS files; its Data Types imports the types of the assembled modules from those files
- [ ] The comment lists the LLS of every interface or external spec named in the converted HLS's front matter — `imports:`, `terms from <dep>:` — a prose-only concept reference is still a dependency
- [ ] External boundaries (external services, external value formats, foreign runtime identifiers) are specified as standard LLS modules under `low/<name>_ext.md` and listed in the dependency comment as `- <name>_ext.md`
- [ ] A component named in LLS prose but not in the HLS front matter is added to the comment; an entry is spurious only when it is neither imported, nor referenced, nor named in the front matter
- [ ] An import `from <module> import ...` maps to the comment entry `- <module>.md`: the module name is the entry's name with the `.md` suffix removed
- [ ] Type-level imports come from the immediate LLS closure — the `low/<name>.md` files the conversion reads; a type-level dependency outside it is a traceability violation, recorded rather than imported or defined
- [ ] An imported type counts as used when it appears in a signature, in prose, or as part of the fulfilled contract; a Composition section may name concrete implementations without making them dependencies

## Data Types

- [ ] The Data Types section opens with exactly one Python code block; all imports, type aliases, and classes are defined inside it, never in the surrounding prose; in an interface LLS, the Protocol class is last (an external LLS `*_ext.md` defines shared type aliases and external signatures/stubs, and is exempt from requiring a Protocol class); prose explaining each type follows the block
- [ ] An HLS-owned term whose meaning is a value and is used in the interface becomes a type alias in the block, named as a camelCase domain concept with the first letter capitalized: the HLS term `pending shipment` becomes `PendingShipment: TypeAlias = str`; a term never in the HLS **Operations** block is never an operation (a `Shipment` term yields a type or a term-definition entry); an HLS term is never dropped
- [ ] Type alias names are camelCase with the first letter capitalized — `PendingShipment`, `OrderStatus`, `InventoryItem`; never lowercase-camel (`pendingShipment`) and never snake_case (`pending_shipment`)
- [ ] Every alias defined in the block is used in a signature, in a field, or in prose; an alias used nowhere is removed
- [ ] Operation signatures and fields are typed with the Data Types aliases, never their expansions
- [ ] Before defining an alias, the listed dependencies' Data Types are searched for the name; a same-named type in a dependency's LLS is imported, never redefined, and a term from a dependency is realized as its owner's type, never a fresh local alias; a new type is defined only when the closure lacks it
- [ ] Type names name the domain concept — what the value is — never its representation or storage form: `InventoryItem`, not `ItemKey`/`ItemId`; a type name is two descriptive words, never a single word; a Protocol class named after the component is exempt from the two-word rule (`class Inventory(Protocol)`)
- [ ] Mutually exclusive outcomes are discriminated unions with `Literal` discriminators, never `Enum`
- [ ] A pass-through record with a fixed shape is a type alias; a value containing a single primitive is a type alias to that primitive (single-field `@dataclass` types are prohibited); a structured value with multiple fields — configuration with defaults, a constructed result — is a `@dataclass`; a fixed set of names is a `Literal` union
- [ ] The event list is one `Literal` union, consumed by the logger callback's signature; per-event payloads are in prose or a table, never a class per event
- [ ] A parameter or field is typed with a closure type where one fits; `Any` is never used where the closure defines one
- [ ] Unmandated `Optional` types, placeholder defaults, or speculative optional arguments must never be introduced into signatures or constructors unless the HLS explicitly specifies optionality
- [ ] Pass-through values use type variables with documented roles; interface specs never resolve a type variable in prose
- [ ] Every interface declares its Protocol class in Data Types, even when no implementation exists in the closure; the class is named after the component (`class <Name>(Protocol)`, never the component name suffixed or renamed — `<Name>Protocol`) and declares every operation documented under Component-Provided Operations as a method — a documented operation without a Protocol method is a free function
- [ ] An opaque withholding becomes a type variable or an uninspected concrete type; an open withholding becomes a concrete type with named fields
- [ ] Configuration an interface operation takes (a per-call `config` parameter or a config-providing operation) is interface-owned: typed in Data Types with a descriptive name (`InventoryConfig`, never `Config`); defaults the HLS states are `@dataclass` field defaults, never comments, prose notes, or `None`-with-text; a field with no HLS default has no default; configuration that only constructs the implementation is implementation-owned, even when the HLS Inputs lists it under `configured:`
- [ ] Every entity partition, category mapping, or permission collection declared in HLS Inputs under `Configured:` (e.g. active vs archived records, authorized vs guest accounts) becomes an explicit field on the configuration `@dataclass`, typed with its domain type alias, enabling operations to evaluate category membership

## Term definitions

- [ ] A cross-cutting behavioral rule that cannot be factored into a shared interface is defined as a term; all term definitions are bullets in one `## Term definitions` section between Data Types and Component-Provided Operations — no `## <Name> (term definition)` subsections exist
- [ ] The `## Term definitions` section states each HLS term's realization, one bullet per term: `- **<term>** → the `AliasName` alias` (a term realized as a type; definition in Data Types) or `- **<term>** → term definition: <definition>` (a term realized as prose); a term realized as both states both; the realization is in line, never a link; a term from a dependency points to its owner's realization (`→ the `InventoryItem` alias from inventory`, `→ term definition from inventory`), never restated
- [ ] Term names are the HLS term's words — `pending shipment`, never `pending_shipment`; an HLS **Terms** entry is never reproduced as a `### ` heading
- [ ] A value term used in the interface becomes a type alias in Data Types; a term used in no interface operation or a behavioral-rule term becomes a term-definition entry
- [ ] Each operation that applies a term references it by the term's name — never a markdown link and never restated in full in postconditions or Invariants
- [ ] An HLS term is never dropped — a dependent HLS may name it in `terms from <owner>:`

## Component-Provided Operations

- [ ] Operations are the client-initiated behaviors named in the HLS Contract's **Operations** block or a named block describing client-invoked behaviors (**File operations**, **Verification**, **Termination**); no operation exists without a direct line from that block
- [ ] Component-provided operations exist for client-initiated behaviors only; internal behaviors (propagation, persistence, validation) are postconditions, not operations; no operations named `propagate_*` or `persist_*`
- [ ] Operations are at the level of individual actions; clients never read or write more than they need; split interfaces when responsibilities differ (persistence vs. logic vs. orchestration)
- [ ] Because Python does not support method overloading, each component operation must have a distinct, unique method name for each distinct behavior (avoid duplicate names with differing parameter types)
- [ ] Content the client provides is imported at initialization; behavior the client initiates is a component-provided operation
- [ ] Each operation is documented under a `### `operation_name`` heading; its signature is echoed as `def <name>(...)` in a Python block directly under the heading, typed with the Data Types aliases and mirroring the Protocol method in Data Types — the method is written into the Protocol class, never only as the echo
- [ ] Each operation documents **Purpose** (explicitly stating which Protocol class provides the operation, e.g. `Processor` or `ProcessingFactory`), **Preconditions**, **Postconditions**, **Failure Handling**, and **HLS Justification** under its heading
- [ ] Factory operations declared in HLS using creation phrasing ("Creating a *<type>* through a *<type> factory* yields a *<type>* configured from a *<type> configuration*") map to factory methods on the factory Protocol class (e.g. `def create_<type>(self, config: <Type>Config) -> <Type>: ...`) under Component-Provided Operations
- [ ] **Preconditions:** an HLS assumption is a precondition, never a failure condition; preconditions are caller obligations and produce no Failure Handling clause
- [ ] **Postconditions:** describe outcomes, not mechanisms; mechanism belongs in the implementation's Behavioral Description, never in a postcondition
- [ ] **Postconditions:** client-visible operation boundaries (atomicity, all-or-nothing) are postcondition guarantees; each operation is fully self-contained — preconditions, postconditions, failure handling, ordering, and routing all appear under it
- [ ] **Postconditions:** a rule already defined as a term is referenced by name, never restated; each HLS fact appears in exactly one LLS location
- [ ] **Failure Handling:** error handling exists only for explicit HLS failure conditions; assumptions are not error conditions; no invented failures; **Unexpected failures** blocks and failure guarantees become the affected operations' Failure Handling
- [ ] **Failure Handling:** expected failures (validation failures, policy violations, permission checks, disallowed argument combinations) are return-value signals documented in the interface spec, never exceptions; unexpected failures — precondition violations, filesystem errors, state corruption — are exceptions or undefined behavior, never documented in interface specs
- [ ] **Failure Handling:** every operational restriction and permission rule in HLS Guarantees (e.g. attempting actions on unauthorized entities, missing required flags, disallowed combinations) is an expected failure that must be explicitly listed under Failure Handling with its return-value failure signal; operational constraints must never be stranded in Postconditions as passive requirements
- [ ] **Failure Handling:** "Failure" names one of three distinct signals: termination ends the session; channel failure is a failed channel action after which the session continues; run failure is a run-level failure of the request itself
- [ ] **Failure Handling:** concrete strings (error messages, fallback text) are pinned in implementation specs, not interface specs; wording is stated only when a test must assert it; an interface deferral ("pinned in the implementation spec") is backed by the named implementation LLS actually stating it — an unbacked deferral is an error
- [ ] **Failure Handling:** dependency failure signals are honored and re-exported; a uniform return-signal contract is never converted to exceptions; unexpected dependency errors are the dependency's exceptions, optionally caught and re-exported as a failure signal
- [ ] **HLS Justification:** each operation's justification is one brief phrase tracing to the HLS Contract line or named-block line it derives from, never a quotation of the guarantees; a hook withholding becomes the concrete condition in the implementation or an explicit signal in the interface; the LLS accepts "returns" in signatures and prose (the HLS prohibits it)

## Invariants

- [ ] Invariants are component-wide guarantees that hold across all operations; each invariant is stated once; the Invariants section is never empty
- [ ] A rule already defined as a term definition is referenced by name in Invariants, never restated
- [ ] A statement of absence is an invariant or postcondition note when a test could check it, otherwise it lives in the owning component's spec; an absence neither testable nor owned elsewhere is a dangling fact

## Implementation sections

- [ ] An Implementation LLS section exists only when the component filename ends in `_impl.md` (declaring `implements: <type>` in its HLS) or `_asm.md`; otherwise the interface LLS stands alone
- [ ] The implementation is declared as `class FooImpl(Foo): ...` extending the fulfilled interface's Protocol, imported from the interface's LLS and never redeclared locally; the implementation name matches the interface only when exactly one implementation will ever exist; multi-implementation interfaces use distinct names; abstract bases are named distinctly (`BaseFoo`)
- [ ] When an interface defines a factory operation, the implementation LLS declares `class FooFactoryImpl(FooFactory): ...` implementing the factory protocol, and defines an internal class `_FooImpl(Foo)` implementing the created protocol; the internal class captures factory method arguments (such as per-task configuration) and satisfies the behavioral requirements declared for that protocol type
- [ ] An assembly is declared as `class FooAsm(FooImpl): ...` subclassing the concrete implementation (which fulfills the interface Protocol) and ending with the `Asm` suffix; its `__init__` takes only domain configuration parameters (never concrete `_impl` instances) and instantiates all sub-component `_impl` classes directly inside `__init__` before delegating to `super().__init__(...)`; concrete `_impl` classes must be instantiated inside an `_asm` class and can never be used as arguments to a constructor; it performs configuration and assembly of other modules and no other functionality, and it is never tested
- [ ] Implementation sections reference the interface contract instead of the client; implementation sections never mention "client"
- [ ] The implementation HLS's `## Behavior` lines are the semantic source: every plain declarative requirement in the implementation HLS's `## Behavior` maps onto `## Behavioral Description`, `## Invariants`, or `## Failure Handling`; concrete conditions, schemas, parameter names, and error feedback (such as listing available readable files on failure) are pinned in the implementation LLS
- [ ] The implementation's Invariants add implementation-specific guarantees; the fulfilled interface's invariants are honored
- [ ] Assembler implementations list the wired concrete implementations in a Composition section (names only — not dependencies; the dependency comment still lists interfaces only); an assembly's Composition section is required and lists the concrete implementations it wires, and its dependency comment lists the implementation LLS files those implementations come from (the one exception to the interfaces-only rule)
- [ ] Behavioral Description states outcomes, not mechanisms; interactions with external systems may be described in the external protocol's terms
- [ ] Operations that compare, index, or store external value formats (such as external target labels) specify their canonicalization and normalization behavior in Behavioral Description or Invariants
- [ ] The fulfilled interface's operations are documented in the interface LLS; the implementation documents them in Behavioral Description as bullets — never in an interface section, never under `### ` headings
- [ ] Implementation-owned configuration becomes the implementation class's `__init__` parameters in the Implementation LLS Data Types (`fulfillment_impl.__init__(self, inventory: Inventory, pricing: Pricing)`); in the HLS this is the implementation's `imports:` front matter and constructor configuration types; no other `__init__` is declared
- [ ] A limit a guarantee names without an Inputs entry (e.g., a "retry limit") is an internal constant stated in Failure Handling, never a config field

## Final sweep

- [ ] Total Requirement Weaving: every single behavioral requirement, transformation, precondition, outcome, and failure condition stated in the immediate HLS is woven into at least one concrete location in the generated LLS (Data Types, Preconditions, Postconditions, Failure Handling, Behavioral Description, Invariants, or Term Definitions); omitting any immediate HLS requirement is a conversion error; requirements may be elaborated, split, or woven across multiple locations
- [ ] No unresolved withholdings — opaque, open, and hook terms are pinned in the LLS
- [ ] External boundaries: foreign formats, third-party APIs, and runtime identifiers reference external boundary specs (`low/<name>_ext.md`); an agent lacking required external schema knowledge produces an explicit error rather than omitting the requirement
- [ ] Deferred details: all concrete failure feedback, error lists, formatting schemas, and recovery signals deferred from an interface spec are explicitly woven into the implementation LLS
- [ ] No missing required structure — the full section inventory is present; no template scaffolding remains
- [ ] No type-level imports outside the immediate LLS closure — a type the closure lacks is a recorded gap, never an import or a local definition
- [ ] No unbacked deferrals — "pinned in the implementation spec" only when the named implementation LLS states it
- [ ] No dead aliases — every alias is used in a signature, a field, or prose; no HLS-owned term is dropped
- [ ] No markdown links — `[text](...)` is never used
- [ ] No `__init__`-style configuration — a config class is a `@dataclass`

## Lint checks

- [ ] Section headings are exactly `# Interface LLS: <name>` and `# Implementation LLS: <name>` matching the filename stem
- [ ] Interface subsections are `## Data Types`, optional `## Term definitions`, `## Component-Provided Operations`, `## Invariants`; implementation subsections are `## Data Types`, optional `## Composition`, `## Behavioral Description`, `## Invariants`; external subsections are `## Data Types`; no other `##` section; sections appear in that order
- [ ] The interface section contains `## Data Types`, `## Component-Provided Operations`, and `## Invariants`; the implementation section contains `## Data Types`, `## Behavioral Description`, and `## Invariants`
- [ ] The dependency comment is the file's first line — the LLS's only front matter — and lists each dependency as one `- <name>.md` entry; it never names an HLS file (an HLS has the virtual name `high/<name>.md`); every non-stdlib import appears in it
- [ ] The Data Types section opens with exactly one Python code block; the interface's Protocol class is last
- [ ] Every type alias is `X: TypeAlias = ...`; never a bare `X = ...` except string constants and `TypeVar` declarations
- [ ] The Data Types block imports every `typing`, `dataclasses`, or `enum` name it uses (`from typing import Protocol, TypeAlias, Sequence`); a typing name is never assumed — it is imported exactly like any other name
- [ ] No comments or docstrings in code blocks
- [ ] Never generic type names `Message`, `Result`, `Status`, `Data`
- [ ] A type name is never a single word; a type name never ends in a representation suffix (`Key`, `Id`, `Text`, `Value`, `Data`, `Record`)
- [ ] A type that would be a data class with a single field is a type alias (`ShelfCode: TypeAlias = str`), never a one-field data class; a data class whose only field is a `Literal` discriminator (a union marker) is exempt
- [ ] Interfaces are expressed with `Protocol` from `typing`, never an `abc.ABC` abstract class with `@abc.abstractmethod`
- [ ] A type owned by a listed dependency is imported, never redefined — a local alias with the same value is still a redefinition
- [ ] Every type name used in the Data Types block or in an operation signature is defined there or imported; no undefined type names
- [ ] Every documented operation is a method of the interface's Protocol class, never a free function
- [ ] Each operation is documented under a `### `operation_name`` heading and documents **Purpose**, **Preconditions**, **Postconditions**, **Failure Handling**, and **HLS Justification**
- [ ] Each operation's signature is echoed as `def <name>(...)` in a ```python block directly under its `### `name`` heading
- [ ] Records are `@dataclass` classes or `TypeAlias` aliases; `TypedDict` is never used
- [ ] `### ` headings appear only under Component-Provided Operations
- [ ] Term-definition headings appear between Data Types and Component-Provided Operations
- [ ] Implementation sections never mention "client"
- [ ] No markdown links (`[text](...)`) anywhere in the document
- [ ] An `# Implementation LLS:` heading appears only in a `<name>_impl.md` or `<name>_asm.md` file (virtual name `low/<name>_impl.md` or `low/<name>_asm.md`)
- [ ] There is no `## Config` section
- [ ] There is no `## Non-Concerns` section
