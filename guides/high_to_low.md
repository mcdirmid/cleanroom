# Guide: Converting a High-Level Specification to a Low-Level Specification

## Summary

The artifact is the LLS for a component: it conforms to the LLS structure this guide states, and it aligns with the component's HLS — the HLS and its closure. The LLS adds the concrete types, signatures, preconditions, postconditions, and failure signals the HLS intentionally omits; it is the HLS elaborated, never replaced. A file that is a template is filled in.

The HLS is a set, not just a file: its effective constraint set is its own lines plus the transitive closure of every spec it references (`imports:` and `fulfills:`, and their references in turn). The LLS inlines the entire closure; what the HLS withholds — opaque values, open contents, hooks — is exactly what the LLS pins. Reading: the HLS file for the component; the transitive closure of its front matter (`imports:`, `fulfills:`, `terms (from X):`), recursively; and the LLS of every component in that closure (the LLS depends only on LLS files).

The artifact declares one or more sections, in order:

- `# Interface LLS: <name>` — repeatable: `## Data Types`, `## Component-Provided Operations`, `## Invariants`
- `# Implementation LLS: <name>` — only when the HLS defines an implementation: `## Data Types`, `## Composition`, `## Behavioral Description`, `## Invariants`, `## Non-Concerns`

Term definitions (cross-cutting behavioral rules such as stubbing) appear between Data Types and Component-Provided Operations. Non-Concerns is optional in both kinds. The HLS is organized by concern; the LLS is organized by operation, collecting all rules that apply to it — preconditions, postconditions, error conditions, ordering, failure semantics, routing — across HLS sections, blocks, and specs of the closure.

## Structure

- [ ] Section headings are exactly `# Interface LLS: <name>` and `# Implementation LLS: <name>`; operations use `### `name``
- [ ] Interface subsections are `## Data Types`, `## Component-Provided Operations`, `## Invariants`; implementation subsections are `## Data Types`, `## Composition`, `## Behavioral Description`, `## Invariants`, `## Non-Concerns`
- [ ] A file may declare any number of interface and implementation sections; an implementation LLS exists only when the HLS defines an implementation (`fulfills:` an interface); the interface LLS stands alone otherwise
- [ ] The required structure is present in the final artifact: no required section is deleted as redundant, and no structure skeleton is written into the file as scaffolding
- [ ] The LLS's only front matter is its dependency comment (first line): no `terms (owned):` or `terms (from X):` section; the HLS's `terms (owned):` becomes type aliases, a `terms (from X):` entry becomes a dependency-comment entry and imports of X's types
- [ ] Filenames use underscores except the `-low` / `-high` suffix; no hyphens elsewhere
- [ ] The implementation class is `class FooImpl(Foo): ...`; the name matches the interface only when exactly one implementation will ever exist; multi-implementation interfaces use distinct names; abstract bases are named distinctly (`BaseFoo`)
- [ ] The LLS is a stand-alone document; readers use it without the HLS

## Dependencies

- [ ] LLS files depend only on other LLS files — never HLS files, never implementation LLS files; dependencies are expressed through interfaces
- [ ] The dependency comment (first line) lists the LLS of every interface named in the converted HLS's front matter — `imports:`, `fulfills:`, `terms (from X):` — whether or not a type is imported; a prose-only concept reference is still a dependency
- [ ] A component named in LLS prose but not in the HLS front matter is added to the comment; an entry is spurious only when it is neither imported, nor referenced, nor named in the front matter
- [ ] Type-level imports stay inside the converted HLS's closure; a type-level dependency outside it is a traceability violation — the HLS is amended first, then the conversion proceeds
- [ ] An imported type counts as used when it appears in a signature, in prose, or as part of the fulfilled contract; a Composition section may name concrete implementations without making them dependencies
- [ ] A type is imported from its owner's LLS; importing through a re-exporting interface is an error

## Traceability and alignment

- [ ] Every LLS statement traces to the HLS's effective constraint set (own lines plus closure); the LLS adds no behavior the closure does not imply
- [ ] The LLS adds the details the HLS omits (types, signatures, constants, parameter values, error strings) as long as the behavior is implied; implementation details appear only as necessary to fulfill HLS guarantees
- [ ] HLS withholdings are resolved: an opaque term becomes a type variable or a concrete type the interface does not inspect; an open term becomes a concrete type with named fields; a hook becomes the concrete condition in the implementation or an explicit signal in the interface
- [ ] The implementation's `[refines]` Deltas lines name the withheld precision the implementation LLS makes concrete
- [ ] An HLS fact the LLS cannot express is a conversion error; a fact implied but never stated is a traceability gap
- [ ] HLS ambiguity is never resolved silently: two observably different readings are resolved by amending the HLS first; a narrowing that bounds a guarantee's scope is recorded under Failure Handling or in Non-Concerns with a justification
- [ ] Absence-of-behavior statements have a home: a statement of absence is an invariant or postcondition note when a test could check it, otherwise it lives in the owning component's spec; neither testable nor owned elsewhere is a dangling fact

## Data Types

- [ ] Data Types opens with exactly one Python code block containing all imports, type aliases, and classes; the interface's Protocol class is last, declaring only its fresh (non-inherited) methods
- [ ] Every type alias is `X: TypeAlias = ...` (from `typing`); never a bare `X = ...` except string constants and `TypeVar` declarations; no comments in code; prose explaining each type follows the block
- [ ] Names are descriptive and domain-specific; never generic `Message`, `Result`, `Status`, `Data`
- [ ] Mutually exclusive outcomes are discriminated unions with `Literal` discriminators
- [ ] Pass-through values use type variables with documented roles; interface specs never resolve a type variable in prose (`Outcome[T]`, never `Outcome[str]`)
- [ ] Shared types are imported from their owner's LLS, never redefined (`ToolDefinition` from `tool_provider`, not `agent_loop`)
- [ ] An HLS-owned term never in the HLS **Operations** block is a type alias, not an operation (a `Subgraph` term yields a `Subgraph` type, never a `get_subgraph` operation)
- [ ] Every interface declares its Protocol class in Data Types, even when no implementation exists in the closure; every operation signature is a method of it, never a free function
- [ ] Interface-owned configuration is typed in the Interface LLS Data Types with a descriptive name (`InventoryConfig`, never `Config`)

## Operations

- [ ] Each operation is documented under a `### `operation_name`` heading and is fully self-contained: preconditions, postconditions, failure handling, ordering, and routing rules all appear under the operation
- [ ] Component-provided operations exist for client-initiated behaviors only; internal behaviors (propagation, persistence, validation) are postconditions, not operations
- [ ] An operation derives from the HLS Contract's **Operations** block or a named block describing client-invoked behaviors (e.g., **File operations**, **Verification**, **Termination**); no operation without a direct line from that block
- [ ] No operations named `propagate_*`, `persist_*`, `validate_*`, `track_*`, `notify_*`, or `sync_*`
- [ ] Operations are at the level of individual actions; clients never read or write more than they need
- [ ] Client-visible operation boundaries (atomicity, all-or-nothing) are postcondition guarantees ("Signals failure for the entire operation if any step fails")
- [ ] Content the client provides is imported at initialization; behavior the client initiates is a component-provided operation
- [ ] Each operation documents **Purpose**, **Preconditions**, **Postconditions**, **Failure Handling**, and **HLS Justification**
- [ ] Postconditions describe outcomes, not mechanisms ("Completes when...", never "Iterates until..."); implementation details belong in the Behavioral Description, not in preconditions or postconditions
- [ ] The LLS accepts "returns" in signatures and prose (the HLS prohibits it)
- [ ] Split interfaces when responsibilities differ (persistence vs. logic vs. orchestration)

## Failure Handling

- [ ] "Failure" always names one of three distinct signals: termination, channel failure, or run failure — termination is a channel action that ends the session (a session that produces a termination signal produces no further channel results); channel failure is a failed channel action (invalid arguments, a policy violation, a termination channel invoked incorrectly) after which the session continues; run failure is a run-level failure of the request itself (service failure, malformed response, exceeded iteration limit)
- [ ] Error handling exists only for explicit HLS failure conditions anywhere in the closure; assumptions are not error conditions
- [ ] Expected failures — conditions the contract handles during normal use (validation failures, policy violations) — are return-value signals documented in the interface spec; never exceptions for expected conditions
- [ ] Unexpected failures — precondition violations, filesystem errors, state corruption — are exceptions or undefined behavior, never documented in interface specs; preconditions are caller obligations, not failure signals
- [ ] An HLS assumption is a precondition, never a failure condition: it appears under **Preconditions** and produces no Failure Handling clause
- [ ] Concrete strings (error messages, fallback text) are pinned in implementation specs, not interface specs; wording is stated only when a test must assert it
- [ ] An interface deferral ("pinned in the implementation spec") is backed by the named implementation LLS actually stating it; an unbacked deferral is an error; error-detail-absence pins appear only when a test must assert them
- [ ] Dependency failure signals are honored and re-exported; a uniform return-signal contract is never converted to exceptions; unexpected dependency errors are the dependency's exceptions, optionally caught and re-exported as a failure signal

## Configuration

- [ ] Configuration comes in two kinds, each in exactly one place, decided by who supplies it: the client of the interface, or the assembler
- [ ] Interface-owned configuration — supplied by the interface's client (the HLS **Inputs** block, items marked "configured:") — is typed in the Interface LLS Data Types with a descriptive name (`InventoryConfig`, not `Config`) and passed to the implementation as a single `config` parameter
- [ ] Implementation-owned configuration — capability bundling known only to the assembler — becomes the implementation class's `__init__` parameters in the Implementation LLS Data Types (`fulfillment_impl.__init__(self, inventory: Inventory, pricing: Pricing)`); in the HLS this is the implementation's `imports:` front matter and `[external]` Deltas lines
- [ ] No capabilities to bundle: no `__init__` is declared
- [ ] There is no Config section

## Implementation LLS

- [ ] An Implementation LLS section exists only when the HLS defines an implementation (an `*_impl` spec with `fulfills: <interface>`); otherwise the interface LLS stands alone
- [ ] The implementation is declared as `class FooImpl(Foo): ...` extending the interface's Protocol
- [ ] The implementation name matches the interface only when exactly one implementation will ever exist; multi-implementation interfaces use distinct names; abstract bases are named distinctly (`BaseFoo`)
- [ ] Implementation sections never mention "client" — they reference the interface contract instead ("per the `inventory` interface contract")
- [ ] The implementation HLS's Deltas are the semantic source: untagged behavior lines and tagged (`[ordering]`, `[boundary]`, `[state]`, `[external]`, `[failure]`) lines map onto the Behavioral Description, Invariants, and Failure Handling; `[refines]` lines pin concrete conditions and values
- [ ] Assembler implementations list the wired concrete implementations in a Composition section (names only — not dependencies; the dependency comment still lists interfaces only)
- [ ] Behavioral Description states outcomes, not mechanisms; interactions with external systems may be described in the external protocol's terms
- [ ] Invariants are component-wide guarantees that hold across all operations
- [ ] Non-Concerns (optional) records pinned choices as `- **[Aspect]:** [Choice] — [Justification]`; aspects intentionally unspecified because they do not affect correctness: ordering, algorithm choice, representation, unhandled failure modes, caller constraints

## Named Contract blocks

- [ ] Each named block's facts land in exactly one LLS location, never duplicated
- [ ] **Events / Logging** blocks: the event list becomes a `Literal` union or callback signature in Data Types; log and path rules become postconditions, failure-handling notes, or an Invariant
- [ ] **Stubbing / Views / behavioral sub-contracts**: become a term definition (between Data Types and Operations) or an Invariant
- [ ] **File operations / Verification / Termination** blocks (client-invoked behaviors): the tools become operations alongside the **Operations** block, their facts becoming preconditions, postconditions, and failure handling
- [ ] **Unexpected failures**: becomes the Failure Handling of the affected operations; concrete exception classes and strings are pinned in the implementation LLS

## Common pitfalls

- [ ] No restated HLS constraints — each HLS fact appears in exactly one LLS location
- [ ] No invented failures — error handling exists only for explicit HLS failure conditions
- [ ] No unresolved withholdings — opaque, open, and hook terms are pinned in the LLS
- [ ] No missing required structure — the full section inventory is present in the final artifact
- [ ] No generic names — `Message`/`Result`/`Status`/`Data` become descriptive names
- [ ] No type-level imports outside the HLS closure — the HLS is amended first
- [ ] No mechanism in postconditions — outcomes, not steps
- [ ] No operations for internal behavior — propagation, persistence, and validation are postconditions
- [ ] No unbacked deferrals — "pinned in the implementation spec" only when the named implementation LLS states it
