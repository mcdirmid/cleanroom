# Guide: Low-Level Specifications (LLS)

## Summary

An LLS is a low-level specification: an artifact that specifies how a component's interface and implementation are realized — concrete types, signatures, preconditions, postconditions, and failure signals — detailed enough that tests and an implementation can be written from it independently and pass when both conform. The artifact conforms to this guide. It is the HLS elaborated, never replaced.

Every LLS statement traces to the HLS: the LLS adds no behavior the HLS does not imply. Each LLS is a stand-alone document; readers use it without the HLS. A file that is a template is filled in.

The artifact declares one or more sections, in order:

1. `# Interface LLS: <name>` — repeatable: `## Data Types`, `## Component-Provided Operations`, `## Invariants`
2. `# Implementation LLS: <name>` — only when the HLS defines an implementation: `## Data Types`, `## Composition`, `## Behavioral Description`, `## Invariants`, `## Non-Concerns`

Term definitions (cross-cutting behavioral rules) appear between Data Types and Component-Provided Operations. Non-Concerns is optional in both kinds. An implementation LLS exists only when the HLS defines an implementation for the interface; the interface LLS stands alone otherwise.

## Structure

- [ ] A file may declare any number of interface and implementation sections
- [ ] Filenames use underscores except the `-low` / `-high` suffix; no hyphens elsewhere
- [ ] The implementation name matches the interface name only when the interface is single-implementation by nature (`pricing` / `pricing_impl`); multi-implementation interfaces use distinct identifying names (`csv_inventory_impl`, `memory_inventory_impl`)
- [ ] The implementation class is `class FooImpl(Foo): ...` in the implementation's Data Types; multi-implementation classes use a distinguishing prefix (`CsvInventoryImpl(InventoryImpl)`)
- [ ] The structure skeleton is never written into the file — it is a shape, not content

## Dependencies

- [ ] LLS dependencies are expressed through interfaces, never implementation LLS files
- [ ] An implementation depends on the interface it implements and on any other interfaces whose types it uses; an imported type counts as used when it appears in a signature, in prose, or as part of the fulfilled contract
- [ ] A Composition section may name concrete implementations without making them dependencies
- [ ] Every dependency-comment entry corresponds to an actual import or direct reference; no spurious entries
- [ ] The comment is the LLS's only front matter: no `terms (owned):` or `terms (from X):` section; owned concepts are type aliases in Data Types; used concepts are imports from those specs' LLS files, listed in the comment

## Termination, channel failure, run failure

- [ ] "Failure" always names one of three distinct signals: termination, channel failure, or run failure
- [ ] Termination is a channel action that ends the session; a session that produces a termination signal produces no further channel results; a successful termination carries a termination result, a failure termination carries a value describing the failure
- [ ] Channel failure is a failed channel action (invalid arguments, a policy violation, a termination channel invoked incorrectly); the session continues and the failure value guides the run's next move
- [ ] Run failure is a run-level failure of the request itself (service failure, malformed response, exceeded iteration limit), signaled by the run's failure result
- [ ] A run recovers from a channel failure by continuing: the failure value is appended to the request history and the request makes its next move; recovery has no stateful effect on the session (no session reset, no history clearing, no new service session)

## Data Types

- [ ] The Data Types block contains all imports, type aliases, and classes; the interface's Protocol class declares only its fresh (non-inherited) methods
- [ ] Prose explaining each type follows the block, never interleaved between code blocks
- [ ] Names are descriptive and domain-specific; distinct purposes get distinct names
- [ ] Type names name the domain concept — what the value is — never its representation or storage form: `InventoryItem`, not `ItemKey`/`ItemId`; `PriceQuote`, not `PriceJson`/`PriceData`; two descriptive words make the name unlikely to clash
- [ ] Type variables are preferred over `Any` for values that pass through unchanged; `Any` only when truly unconstrained
- [ ] Each type variable has one well-defined, documented role; distinct roles get distinct names; imported type variables are reused for the same role
- [ ] Interface specs never resolve a type variable to a concrete type, including in prose (`Outcome[T]`, never `Outcome[str]`); the implementation spec resolves it
- [ ] Mutually exclusive outcomes are discriminated unions with `Literal` discriminators, never a dataclass of optional fields
- [ ] Every interface declares its Protocol class in Data Types, even when no implementation exists yet; a Protocol may be a dataclass combining static data fields with interface methods
- [ ] A type is defined once, in the interface that owns the concept; importing through a re-exporting interface is an error
- [ ] A new type is defined only when no existing type is workable, adding a bridging type to the dependency spec; adaptation between interfaces' types happens in implementation specs, not interface specs
- [ ] Pre-constrained interfaces are referenced, not re-documented

## Operations

- [ ] Each operation is fully self-contained: preconditions, postconditions, failure handling, ordering, and routing rules all appear under the operation, and may reference term definitions by name
- [ ] Operations are at the level of individual actions; clients never read or write more than they need
- [ ] Client-visible operation boundaries (atomicity, all-or-nothing) are postcondition guarantees ("Signals failure for the entire operation if any step fails")
- [ ] Internal mechanics, persistence, validation, and bookkeeping are postconditions or invariants, not operations
- [ ] Content the client provides is imported at initialization; behavior the client initiates is a component-provided operation
- [ ] Postconditions describe outcomes, not mechanisms; each operation has a brief HLS justification, consistent with the HLS and not necessarily a direct quote

## Failure Handling

- [ ] The code-level signal (return value, `None`, `Result`, exception) is documented explicitly in the signature or text
- [ ] Expected failures — conditions the contract handles during normal use (policy violations, validation failures) — are return-value signals documented in the interface spec; never exceptions for expected conditions
- [ ] Unexpected failures — precondition violations, filesystem errors, state corruption — are exceptions or undefined behavior, never documented in interface specs; preconditions are caller obligations, not failure signals
- [ ] When an interface documents an unexpected failure for reader clarity, only the constraint is stated, never how the interface handles the violation
- [ ] Concrete strings (error messages, fallback text) are pinned in implementation specs, never interface specs; error-message wording is stated only when a test must assert it, and only in the implementation spec
- [ ] Dependency failure signals are honored and re-exported; a uniform return-signal contract is never converted to exceptions; unexpected dependency errors are the dependency's exceptions, optionally caught and re-exported as a failure signal

## Term definitions

- [ ] A cross-cutting behavioral rule that applies to multiple operations and cannot be factored into a shared interface is defined as a term, referenced by name in each operation
- [ ] Short definitions are inline prose; longer ones use a heading such as `## Stubbing Semantics (term definition)`

## Implementation LLS

- [ ] The implementation implements the Protocol class defined in the corresponding interface LLS
- [ ] Data Types imports the interface's Protocol and types and declares `class FooImpl(Foo): ...` as a code block; concrete error-message strings and result structures belong here, not in the interface spec
- [ ] Configuration is expressed as the implementation class's `__init__` in Data Types
- [ ] Implementation-owned configuration — capability bundling supplied by the assembler — becomes `__init__` parameters (`fulfillment_impl.__init__(self, inventory: Inventory, pricing: Pricing)`)
- [ ] Interface-owned configuration — domain data the interface's client supplies — is typed in the Interface LLS Data Types with a descriptive name (`InventoryConfig`, never `Config`) and passed as a single `config` parameter
- [ ] No configuration: no `__init__` is declared
- [ ] Assembler implementations name the concrete implementations wired together in a Composition section (names only — not dependencies; the dependency comment still lists interfaces only)
- [ ] Implementation sections reference the interface contract instead of the client ("per the `inventory` interface contract")
- [ ] Behavioral Description states outcomes, not mechanisms; interactions with an external system may be described in the external protocol's terms; imported interfaces are referenced by name, never re-documented; interface preconditions are taken as given, never re-documented
- [ ] Invariants are component-wide guarantees that hold across all operations

## HLS Justification

- [ ] Each operation's HLS Justification is one sentence or a brief phrase, consistent with the HLS; it need not quote it directly
- [ ] "Definition" is never used in place of "interface" or "implementation"

## Non-Concerns

- [ ] Optional in interface and implementation LLSs
- [ ] Record pinned choices as `- **[Aspect]:** [Choice or assumption] — [Justification]`
- [ ] Common aspects: ordering, algorithm choice, representation, unhandled failure modes, caller constraints

## Lint checks

- [ ] Section headings are exactly `# Interface LLS: <name>` and `# Implementation LLS: <name>` matching the filename stem
- [ ] Interface subsections are `## Data Types`, `## Component-Provided Operations`, `## Invariants`; implementation subsections are `## Data Types`, `## Composition`, `## Behavioral Description`, `## Invariants`, `## Non-Concerns`; no other `##` section; sections appear in that order
- [ ] The interface section contains `## Data Types`, `## Component-Provided Operations`, and `## Invariants`; the implementation section contains `## Data Types`, `## Behavioral Description`, and `## Invariants`
- [ ] The dependency comment is the file's first line and lists each dependency as one `- <name>-low.md` entry; it never names an HLS file; every non-stdlib import appears in it
- [ ] The Data Types section opens with exactly one Python code block; the interface's Protocol class is last
- [ ] Type aliases are declared with `TypeAlias` from `typing` (`ShelfCode: TypeAlias = str`); string constants are plain assignments; a bare `X = ...` type assignment is never used
- [ ] The Data Types block imports every `typing`, `dataclasses`, or `enum` name it uses (`from typing import Protocol, TypeAlias, Sequence`); a typing name is never assumed — it is imported exactly like any other name
- [ ] No comments or docstrings in code blocks
- [ ] Never generic type names `Message`, `Result`, `Status`, `Data`
- [ ] A type name is never a single word; a type name never ends in a representation suffix (`Key`, `Id`, `Text`, `Value`, `Data`, `Record`)
- [ ] A type that would be a data class with a single field is a type alias (`ShelfCode: TypeAlias = str`), never a one-field data class; a data class whose only field is a `Literal` discriminator (a union marker) is exempt
- [ ] Interfaces are expressed with `Protocol` from `typing`, never an `abc.ABC` abstract class with `@abc.abstractmethod`
- [ ] Every documented operation is a method of the interface's Protocol class, never a free function
- [ ] Every type name used in the Data Types block or in an operation signature is defined there or imported — a name a dependency (or another linted spec) defines is imported from its owner, never redefined locally
- [ ] Each operation is documented under a `### `operation_name`` heading and documents **Purpose**, **Preconditions**, **Postconditions**, **Failure Handling**, and **HLS Justification**
- [ ] `### ` headings appear only under Component-Provided Operations
- [ ] Term-definition headings appear between Data Types and Component-Provided Operations
- [ ] Implementation sections never mention "client"
- [ ] There is no `## Config` section
