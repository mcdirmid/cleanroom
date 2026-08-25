# Guide: Converting a High-Level Specification to a Low-Level Specification

## Summary

The artifact is the LLS for a component: it conforms to the LLS structure this guide states (a conformant LLS passes the low-level-spec linter), and it aligns with the component's HLS — the HLS and its closure. The LLS is the HLS elaborated, never replaced: it inlines the HLS's effective constraint set (its own lines plus the transitive closure of every spec it references), adds the concrete types, signatures, preconditions, postconditions, and failure signals the HLS omits, and pins what the HLS withholds (opaque values, open contents, hooks).

The conversion reads the immediate HLS and the immediate LLS closure — the `-low.md` files the dependency comment lists. The HLS closure's files are not read: their constraints are already elaborated in those LLS files. Adaptation is minimally invasive: the LLS is changed in place, and conformant content is left exactly as it is; the file is not rewritten, and no section is restructured unless a deviation requires it. Each deviation is fixed with the smallest change that resolves it; a file that is a template is filled in.

Every LLS statement traces to the HLS's effective constraint set: the LLS adds no behavior the closure does not imply, and implementation details appear only as necessary to fulfill HLS guarantees. Each HLS fact appears in exactly one LLS location, never duplicated. A fact the HLS states and the LLS cannot express is a conversion error; a fact implied but never stated is a traceability gap. HLS ambiguity is never resolved silently: a narrowed reading is recorded with a justification under the affected operation's Failure Handling or in Non-Concerns, never in invented structure. The LLS is a stand-alone document; readers use it without the HLS. Type aliases are camelCase with the first letter capitalized (`PendingShipment`, never `pendingShipment` or `pending_shipment`), defined in the Data Types Python block, and used in operation signatures; an HLS-owned term is never dropped. The LLS contains no markdown links. An implementation LLS contains only the implementation sections — `## Data Types`, optional `## Composition`, `## Behavioral Description`, `## Invariants`, `## Non-Concerns` — never interface sections such as `## Component-Provided Operations`. Each checklist section governs the document region it names, in document order.

## Front matter

- [ ] A component whose HLS has no `fulfills:` line is an interface — its LLS is `# Interface LLS: <name>`, never an Implementation LLS; an implementation LLS exists only when the HLS defines an implementation; a file may declare any number of interface and implementation sections
- [ ] Filenames use underscores except the `-low` / `-high` suffix; no hyphens elsewhere
- [ ] The dependency comment is the file's first line — the LLS's only front matter: no `terms (owned):` or `terms (from X):` section; a `terms (from X):` entry becomes a dependency-comment entry
- [ ] LLS dependencies are expressed through interfaces, never implementation LLS files; a type is imported from its owner's LLS, never through a re-exporting interface
- [ ] The comment lists the LLS of every interface named in the converted HLS's front matter — `imports:`, `fulfills:`, `terms (from X):` — a prose-only concept reference is still a dependency
- [ ] A component named in LLS prose but not in the HLS front matter is added to the comment; an entry is spurious only when it is neither imported, nor referenced, nor named in the front matter
- [ ] An import `from <module> import ...` maps to the comment entry `- <module>-low.md`: the module name is the entry's name with the `-low.md` suffix removed; a module name never ends in `_low`
- [ ] Type-level imports come from the immediate LLS closure — the `-low.md` files the conversion reads; a type-level dependency outside it is a traceability violation, recorded rather than imported or defined
- [ ] An imported type counts as used when it appears in a signature, in prose, or as part of the fulfilled contract; a Composition section may name concrete implementations without making them dependencies

## Data Types

- [ ] The Data Types section opens with exactly one Python code block; all imports, type aliases, and classes are defined inside it, never in the surrounding prose; the interface's Protocol class is last, declares only its fresh (non-inherited) methods, one per `### <name>` heading in Component-Provided Operations — a Data Types block with no Protocol class is an error; prose explaining each type follows the block
- [ ] An HLS-owned term whose meaning is a value and is used in the interface becomes a type alias in the block, named as a camelCase domain concept with the first letter capitalized: the HLS term `pending shipment` becomes `PendingShipment: TypeAlias = str`; a term never in the HLS **Operations** block is never an operation (a `Shipment` term yields a type or a term-definition entry); an HLS term is never dropped
- [ ] Type alias names are camelCase with the first letter capitalized — `PendingShipment`, `OrderStatus`, `InventoryItem`; never lowercase-camel (`pendingShipment`) and never snake_case (`pending_shipment`)
- [ ] Every alias defined in the block is used in a signature, in a field, or in prose; an alias used nowhere is removed
- [ ] Operation signatures and fields are typed with the Data Types aliases, never their expansions
- [ ] Before defining an alias, the listed dependencies' Data Types are searched for the name; a same-named type in a dependency's LLS is imported, never redefined, and a term from a dependency is realized as its owner's type, never a fresh local alias; a new type is defined only when the closure lacks it
- [ ] Type names name the domain concept — what the value is — never its representation or storage form: `InventoryItem`, not `ItemKey`/`ItemId`; a type name is two descriptive words, never a single word; a Protocol class named after the component is exempt from the two-word rule (`class Inventory(Protocol)`)
- [ ] Mutually exclusive outcomes are discriminated unions with `Literal` discriminators, never `Enum`
- [ ] A pass-through record with a fixed shape is a type alias; a structured value with fields — configuration with defaults, a constructed result — is a `@dataclass`; a fixed set of names is a `Literal` union
- [ ] The event list is one `Literal` union, consumed by the logger callback's signature; per-event payloads are in prose or a table, never a class per event
- [ ] A parameter or field is typed with a closure type where one fits; `Any` is never used where the closure defines one
- [ ] Pass-through values use type variables with documented roles; interface specs never resolve a type variable in prose
- [ ] Every interface declares its Protocol class in Data Types, even when no implementation exists in the closure; the class is named after the component (`class <Name>(Protocol)`, never the component name suffixed or renamed — `<Name>Protocol`) and declares every operation documented under Component-Provided Operations as a method — a documented operation without a Protocol method is a free function
- [ ] An opaque withholding becomes a type variable or an uninspected concrete type; an open withholding becomes a concrete type with named fields
- [ ] Configuration an interface operation takes (a per-call `config` parameter or a config-providing operation) is interface-owned: typed in Data Types with a descriptive name (`InventoryConfig`, never `Config`); defaults the HLS states are `@dataclass` field defaults, never comments, prose notes, or `None`-with-text; a field with no HLS default has no default; configuration that only constructs the implementation is implementation-owned, even when the HLS Inputs lists it under `configured:`

## Term definitions

- [ ] A cross-cutting behavioral rule that cannot be factored into a shared interface is defined as a term; all term definitions are bullets in one `## Term definitions` section between Data Types and Component-Provided Operations — no `## <Name> (term definition)` subsections exist
- [ ] The `## Term definitions` section states each HLS term's realization, one bullet per term: `- **<term>** → the `AliasName` alias` (a term realized as a type; definition in Data Types) or `- **<term>** → term definition: <definition>` (a term realized as prose); a term realized as both states both; the realization is in line, never a link; a term from a dependency points to its owner's realization (`→ the `InventoryItem` alias from inventory`, `→ term definition from inventory`), never restated
- [ ] Term names are the HLS term's words — `pending shipment`, never `pending_shipment`; an HLS **Terms** entry is never reproduced as a `### ` heading
- [ ] A value term used in the interface becomes a type alias in Data Types; a term used in no interface operation or a behavioral-rule term becomes a term-definition entry
- [ ] Each operation that applies a term references it by the term's name — never a markdown link and never restated in full in postconditions or Invariants
- [ ] An HLS term is never dropped — a dependent HLS may name it in `terms (from <owner>):`

## Component-Provided Operations

- [ ] Operations are the client-initiated behaviors named in the HLS Contract's **Operations** block or a named block describing client-invoked behaviors (**File operations**, **Verification**, **Termination**); no operation exists without a direct line from that block
- [ ] Component-provided operations exist for client-initiated behaviors only; internal behaviors (propagation, persistence, validation) are postconditions, not operations; no operations named `propagate_*` or `persist_*`
- [ ] Operations are at the level of individual actions; clients never read or write more than they need; split interfaces when responsibilities differ (persistence vs. logic vs. orchestration)
- [ ] Content the client provides is imported at initialization; behavior the client initiates is a component-provided operation
- [ ] Each operation is documented under a `### `operation_name`` heading; its signature is echoed as `def <name>(...)` in a Python block directly under the heading, typed with the Data Types aliases and mirroring the Protocol method in Data Types — the method is written into the Protocol class, never only as the echo
- [ ] Each operation documents **Purpose**, **Preconditions**, **Postconditions**, **Failure Handling**, and **HLS Justification** under its heading
- [ ] **Preconditions:** an HLS assumption is a precondition, never a failure condition; preconditions are caller obligations and produce no Failure Handling clause
- [ ] **Postconditions:** describe outcomes, not mechanisms; mechanism belongs in the implementation's Behavioral Description, never in a postcondition
- [ ] **Postconditions:** client-visible operation boundaries (atomicity, all-or-nothing) are postcondition guarantees; each operation is fully self-contained — preconditions, postconditions, failure handling, ordering, and routing all appear under it
- [ ] **Postconditions:** a rule already defined as a term is referenced by name, never restated; each HLS fact appears in exactly one LLS location
- [ ] **Failure Handling:** error handling exists only for explicit HLS failure conditions; assumptions are not error conditions; no invented failures; **Unexpected failures** blocks become the affected operations' Failure Handling
- [ ] **Failure Handling:** expected failures (validation failures, policy violations) are return-value signals documented in the interface spec, never exceptions; unexpected failures — precondition violations, filesystem errors, state corruption — are exceptions or undefined behavior, never documented in interface specs
- [ ] **Failure Handling:** "Failure" names one of three distinct signals: termination ends the session; channel failure is a failed channel action after which the session continues; run failure is a run-level failure of the request itself
- [ ] **Failure Handling:** concrete strings (error messages, fallback text) are pinned in implementation specs, not interface specs; wording is stated only when a test must assert it; an interface deferral ("pinned in the implementation spec") is backed by the named implementation LLS actually stating it — an unbacked deferral is an error
- [ ] **Failure Handling:** dependency failure signals are honored and re-exported; a uniform return-signal contract is never converted to exceptions; unexpected dependency errors are the dependency's exceptions, optionally caught and re-exported as a failure signal
- [ ] **HLS Justification:** each operation's justification is one brief phrase tracing to the HLS Contract line or named-block line it derives from, never a quotation of the guarantees; a hook withholding becomes the concrete condition in the implementation or an explicit signal in the interface; the LLS accepts "returns" in signatures and prose (the HLS prohibits it)

## Invariants

- [ ] Invariants are component-wide guarantees that hold across all operations; each invariant is stated once; the Invariants section is never empty
- [ ] A rule already defined as a term definition is referenced by name in Invariants, never restated
- [ ] A statement of absence is an invariant or postcondition note when a test could check it, otherwise it lives in the owning component's spec; an absence neither testable nor owned elsewhere is a dangling fact

## Non-Concerns

- [ ] Non-Concerns is optional; it records pinned choices as `- **[Aspect]:** [Choice] — [Justification]`; aspects intentionally unspecified: ordering, algorithm, representation
- [ ] An HLS non-concern is recorded here; a narrowed reading is recorded here or under the affected operation's Failure Handling, with a justification

## Implementation sections

- [ ] An Implementation LLS section exists only when the HLS defines an implementation (an `*_impl` spec with `fulfills: <interface>`); otherwise the interface LLS stands alone
- [ ] The implementation is declared as `class FooImpl(Foo): ...` extending the fulfilled interface's Protocol, imported from the interface's LLS and never redeclared locally; the implementation name matches the interface only when exactly one implementation will ever exist; multi-implementation interfaces use distinct names; abstract bases are named distinctly (`BaseFoo`)
- [ ] Implementation sections reference the interface contract instead of the client; implementation sections never mention "client"
- [ ] The implementation HLS's Deltas are the semantic source: untagged behavior lines and tagged (`[ordering]`, `[boundary]`, `[state]`, `[external]`, `[failure]`) lines map onto the Behavioral Description, Invariants, and Failure Handling; `[refines]` lines pin concrete conditions and values and name the withheld precision
- [ ] The implementation's Invariants add delta-derived guarantees only; the fulfilled interface's invariants are never restated
- [ ] Assembler implementations list the wired concrete implementations in a Composition section (names only — not dependencies; the dependency comment still lists interfaces only)
- [ ] Behavioral Description states outcomes, not mechanisms; interactions with external systems may be described in the external protocol's terms
- [ ] The fulfilled interface's operations are documented in the interface LLS; the implementation documents them in Behavioral Description as bullets — never in an interface section, never under `### ` headings
- [ ] Implementation-owned configuration becomes the implementation class's `__init__` parameters in the Implementation LLS Data Types (`fulfillment_impl.__init__(self, inventory: Inventory, pricing: Pricing)`); in the HLS this is the implementation's `imports:` front matter and `[external]` Deltas lines; no other `__init__` is declared
- [ ] A limit a guarantee names without an Inputs entry (e.g., a "retry limit") is an internal constant stated in Failure Handling, never a config field

## Final sweep

- [ ] No restated HLS constraints — each HLS fact appears in exactly one LLS location
- [ ] No unresolved withholdings — opaque, open, and hook terms are pinned in the LLS
- [ ] No missing required structure — the full section inventory is present; no template scaffolding remains
- [ ] No type-level imports outside the immediate LLS closure — a type the closure lacks is a recorded gap, never an import or a local definition
- [ ] No unbacked deferrals — "pinned in the implementation spec" only when the named implementation LLS states it
- [ ] No dead aliases — every alias is used in a signature, a field, or prose; no HLS-owned term is dropped
- [ ] No markdown links — `[text](...)` is never used
- [ ] No `__init__`-style configuration — a config class is a `@dataclass`

## Lint checks

- [ ] Section headings are exactly `# Interface LLS: <name>` and `# Implementation LLS: <name>` matching the filename stem
- [ ] Interface subsections are `## Data Types`, `## Component-Provided Operations`, `## Invariants`; implementation subsections are `## Data Types`, `## Composition`, `## Behavioral Description`, `## Invariants`, `## Non-Concerns`; no other `##` section; sections appear in that order
- [ ] The interface section contains `## Data Types`, `## Component-Provided Operations`, and `## Invariants`; the implementation section contains `## Data Types`, `## Behavioral Description`, and `## Invariants`
- [ ] The dependency comment is the file's first line — the LLS's only front matter — and lists each dependency as one `- <name>-low.md` entry; it never names an HLS file; every non-stdlib import appears in it
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
- [ ] An `# Implementation LLS:` heading appears only in a `<name>_impl-low.md` file
- [ ] There is no `## Config` section
