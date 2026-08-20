# Guide: Converting a High-Level Specification to a Low-Level Specification

## Purpose

Starting from an HLS, produce an LLS by adding the concrete types, signatures, and behaviors the HLS intentionally omits. The HLS specifies *what* a component does; the LLS specifies the types, signatures, preconditions, postconditions, and failure signals that realize those guarantees in code — detailed enough that tests and an implementation can be written from it independently and pass when both conform.

The relationship is elaboration, not transformation: the HLS states a guarantee ("termination values pass through unchanged"); the LLS gives it form ("`run_request(...) -> RequestResult[T]` returns a `Termination[T]` containing that value").

Authoritative references: `high_level_spec.md` (the source format) and `low_level_spec.md` (the target format). This guide is the conversion procedure between them.

## Conversion Reading

The HLS you convert is a set, not just a file: its effective constraint set is its own lines plus the transitive closure of every spec it references (`imports:` and `fulfills:`, and their references in turn). Because the HLS inherits constraints without restating them, the LLS must inline the entire closure. What the HLS withholds — opaque values, open contents, hooks — is exactly what the LLS pins.

1. Read the HLS file for the component.
2. Read the transitive closure: every spec named in the HLS's front matter (`imports:`, `fulfills:`, and `terms (from X):`), recursively, until complete.
3. Read the LLS of every component in that closure — the LLS depends only on LLS files; the types you import are defined there.
4. Write the LLS as a stand-alone document; readers use it without the HLS.

**Dependency comment = HLS front matter mirrored.** The LLS dependency comment (first line of the file) lists the LLS of every interface named in the converted HLS's front matter — `imports:`, `fulfills:`, `terms (from X):` — whether or not a type is imported; a prose-only concept reference is still a dependency, since its definitions are read alongside. Add any component named in LLS prose that is not in the HLS front matter. An entry is spurious only when it is neither imported, nor referenced, nor named in the HLS front matter.

**Key difference from the HLS:** the HLS is organized by concern (Purpose, Owned definitions, Observable dataflow, Contract, Non-concerns); the LLS is organized by **operation**, collecting ALL rules that apply to it — preconditions, postconditions, error conditions, ordering constraints, failure semantics, routing rules — even when they appear in different HLS sections or different specs of the closure. The LLS is the single source of truth for "what does this operation do?" without jumping between sections or files.

**Note on "Returns":** the HLS prohibits "returns"; the LLS accepts it in signatures and explanations of return semantics.

## Core Rules

1. **Traceability.** Every LLS statement traces to the HLS's effective constraint set (own lines plus closure). The LLS cannot add behavior not implied by the closure; it can and must add details the HLS omits (types, signatures, constants, parameter values, error strings) as long as the behavior is implied. Ask: "Is this behavior implied somewhere in the closure?" If not, remove it. Implementation details (e.g., transactions) may be added only as necessary to fulfill HLS guarantees.
   - **Type-level links stay inside the closure.** The LLS imports only from interfaces in the converted HLS's closure. A type-level dependency outside it (extending a Protocol from an unrelated spec, reusing its type variables) is a traceability violation: amend the HLS first (declare the relationship with `imports:` / `terms (from X):`), then convert.
   - **Never resolve HLS ambiguity silently.** When an HLS statement admits two observably different readings, amend the HLS to the intended reading first. A narrowing that bounds a guarantee's scope is recorded under the operation's Failure Handling or in Non-Concerns with a justification, and the HLS is amended to state the boundary.
   - **Absence-of-behavior statements have a home.** A statement of absence ("the component does not prevent X") is recorded as an invariant or postcondition note when a test could check it. If its substance belongs to another component, it lives in that component's spec and the converted LLS records nothing — name the owning spec. A statement neither testable nor owned elsewhere is a dangling fact: cut it from the HLS.

2. **Don't invent failures.** Include error handling only for explicit HLS failure conditions anywhere in the closure. Assumptions are not error conditions. Expected failures become return-value signals; unexpected failures are not documented in interface specs.

3. **Don't overprescribe non-concerns.** Aspects intentionally unspecified because they do not affect correctness (ordering, algorithm choice, representation, unhandled failure modes, caller constraints) are listed in the LLS Non-Concerns as `- **[Aspect]:** [Choice or assumption] — [Justification].` Non-Concerns is optional. An HLS non-concern is not a license to drop the aspect: an LLS that pins a choice for an open aspect records it in Non-Concerns with a justification; an aspect left open stays open.

4. **Granularity and signatures.**
   - Define operations at the level of individual actions; do not force clients to read or write more than they need.

   - Type aliases and signatures are single-line Python code blocks; multi-line only for Config dataclasses, discriminated unions, and complex data structures with named fields. No comments in code blocks.
   - Encode mutually exclusive outcomes as discriminated unions with `Literal` discriminators; never approximate with a single dataclass of optional fields.
   - Prefer type variables over `Any` for values that pass through unchanged. Document each type variable's role; give distinct roles distinct names; reuse imported type variables. Interface specs never resolve a type variable to a concrete type — including in prose (`Outcome[T]`, not `Outcome[str]`); the implementation spec resolves it.
   - Interfaces with implementations are `Protocol` classes whose methods are the operations — never free functions. A Protocol may be a dataclass combining static data fields with interface methods.
   - Shared type ownership: define a type once, in the interface that owns the concept; import it elsewhere; never redefine it. Import each type from its owner's LLS — importing through a re-exporting interface is an error (`ToolDefinition` from `tool_provider`, not from `agent_loop`).
   - Resolve the HLS's withholdings: an **opaque** term becomes a type variable or a concrete type the interface does not inspect; an **open** term becomes a concrete type with named fields or a documented fill-in contract; a **hook** becomes the concrete condition in the implementation or an explicit signal in the interface. The implementation HLS's Refined terms name the withheld precision the implementation LLS must make concrete.

5. **Interface operations only.** Component-provided operations exist for client-initiated behaviors only. Internal behaviors (propagation, persistence, validation) are postconditions, not operations. "Client provides" → imported at initialization; "client initiates" → component-provided operation. In the HLS, client-initiated behaviors appear in the Contract's "The client may:" list; if you cannot produce a direct line from that list justifying an operation, remove it. Never add operations named `propagate_*`, `persist_*`, `validate_*`, `track_*`, `notify_*`, or `sync_*`.

6. **Operations are self-contained.** Every operation's documentation collects ALL rules that apply to it — preconditions, postconditions, invariants, error conditions, ordering constraints, failure semantics, routing rules — directly under that operation. Do not rely on cross-references. This is the LLS mirror of the HLS's constraint inheritance: the HLS spreads constraints across its closure and never restates them; the LLS inlines the whole closure under each operation.

7. **Implementation LLS only when the HLS defines one.** Produce an Implementation LLS section only if an implementation spec exists (`*_impl` file with `fulfills: <interface>`); otherwise the interface LLS stands alone. When one exists:
   - Declare the implementation as a single-line `class FooImpl(Foo): ...` extending the interface's Protocol.
   - The implementation name matches the interface only when exactly one implementation will ever exist; multi-implementation interfaces use distinct names. Abstract bases are named distinctly (`BaseFoo`); the interface-matching `FooImpl` name is reserved for the concrete fulfilling class.
   - Implementation sections never mention "client" — reference the interface contract instead ("per the `inventory` interface contract").
   - Config bundles imported capabilities (implementation-owned) or references the interface-owned config type; it never redefines it.
   - Behavioral Description states outcomes, not mechanisms; interactions with external systems may be described in terms of the external protocol.
   - Non-Concerns records pinned choices (optional).
   - The implementation HLS's Deltas are the semantic source: Behavior, Operation Boundaries, Ordering, State Management, External Dependencies, Error Handling map onto the implementation LLS sections; Refined terms name the withheld precision to make concrete.

8. **Describe outcomes, not mechanisms.**
   - "Iterates until..." → "Completes when..."
   - "Continues looping while..." → "Processes all..."
   - "Returns after..." → "Returns when..."
   - "Calls X then Y" → "X occurs before Y"
   - Implementation details belong in the Behavioral Description, not in preconditions or postconditions.

9. **Interface granularity.** Split interfaces when responsibilities differ (persistence vs. logic vs. orchestration); each interface has a single responsibility.

10. **HLS justification format.** Keep justifications to one sentence or a brief phrase, consistent with the HLS — they need not quote it. Do not use "definition" in place of "interface" or "implementation".

## Failure Handling: Expected vs. Unexpected

Translate each semantic HLS failure condition into a concrete code-level signal:

- **Expected failures** — conditions the contract handles during normal use (validation failures, policy violations) — are return-value signals, documented in the interface spec. Never raise exceptions for expected conditions.
- **Unexpected failures** — precondition violations, filesystem errors, state corruption — are exceptions or undefined behavior, not documented in interface specs. Preconditions are caller obligations, not failure signals: state the precondition and nothing more. An implementation may document a violation response in its implementation spec if useful, but none is required.
- **Concrete strings** (error messages, fallback text) are pinned in implementation specs, not interface specs. Interfaces document the signal type, the failure categories, and the state preserved on failure. Error-message wording is stated only when a test must assert it — and only in the implementation spec; otherwise not at all. An interface may pin the **absence** of error detail when a test must assert it, recorded in Non-Concerns with a justification; it never states what detail would appear. An interface may defer a detail with "pinned in the implementation spec" only when the named implementation LLS actually states it — verify each deferral's target; an unbacked deferral is an error.
- **Terminology:** distinguish termination (a channel that ends the session), channel failure (a failed channel action, recoverable), and run failure (run-level failure); see `low_level_spec.md` → Terminology.

Every HLS failure statement names a state effect; every such effect must be representable in the LLS — as a precondition, postcondition, or return-value signal. An HLS failure the LLS cannot express is a conversion error.

## Configuration Ownership

Configuration comes in two kinds, each in exactly one place. The deciding question is **who supplies it**: the client of the interface, or the assembler that wires implementations together.

- **Interface-owned configuration** — supplied by the interface's client (the HLS Contract's "The client configures the component with:" list): typed in the Interface LLS Data Types with a descriptive name (`InventoryConfig`, not `Config`).
- **Implementation-owned configuration** — capability bundling known only to the assembler: lives in the Implementation LLS Config section (e.g., `fulfillment_impl`'s `Config` bundling `inventory` and `pricing`). In the HLS this is the implementation spec's `imports:` front matter and Deltas External Dependencies.
- **No capabilities to bundle:** the Config section references the interface-owned type or states "None."

## LLS Structure

```
1. [Interface LLS: name]                  — repeatable
   1.1 Data Types                         — types, type variables, the Protocol class
   1.2 Component-Provided Operations      — each operation, fully self-contained
   1.3 Invariants
2. [Implementation LLS: name]             — only if an implementation HLS exists
   2.1 Data Types                         — imports + `class FooImpl(Foo): ...`
   2.2 Config                             — capability bundling (or interface-owned config reference)
   2.3 Composition                        — concrete implementations an assembler wires together
   2.4 Behavioral Description
   2.5 Invariants
   2.6 Non-Concerns
```

Term definitions (cross-cutting behavioral rules such as stubbing semantics) go between Data Types and Component-Provided Operations. Non-Concerns is optional.

## Operation Documentation Template

```
### `operation_name`

    def operation_name(self, param: Type) -> ReturnType

**Purpose:** [What the operation does.]

**Preconditions:** [Conditions that must be true before calling.]

**Postconditions:** [State changes, return semantics, ordering, routing, guarantees — declarative language.]

**Failure Handling:** [Error conditions and signaling; expected failures as return values, unexpected failures not documented.]

**HLS Justification:** [Brief phrase traceable to a line in the HLS closure.]
```

## Step-by-Step Process

### Interface LLS

1. Identify component-provided operations from the HLS Contract's "The client may:" list.
2. Define type aliases for concepts owned by this interface (from Owned definitions and Observable dataflow); imported terms map to imported types. Type the interface-owned configuration; declare the interface as a `Protocol` class whose methods are the operations.
3. Import types as needed; list every dependency in the dependency comment (per Conversion Reading — mirrors the HLS front matter plus any component named in prose; remove spurious entries).
4. Resolve the HLS's withholdings (per Core Rule 4); check the implementation spec's Refined terms for the withheld precision the implementation pins.
5. For each operation, collect ALL rules from across the HLS closure: preconditions from assumptions and ordering; postconditions from guarantees; error handling from failure semantics; routing from Observable dataflow; ordering from cross-cutting concerns.
6. Document each operation with the template, including all collected rules.
7. Add term definitions for cross-cutting behavioral rules (between Data Types and Operations).
8. Define global invariants.

### Implementation LLS (only if an implementation HLS exists)

1. Identify dependencies: the fulfilled interface (from `fulfills:`), other interfaces in `imports:` / `terms (from X):`, plus any component named in prose. List them in the dependency comment (interfaces only — never another implementation LLS).
2. Declare `class FooImpl(Foo): ...` in Data Types.
3. Define a Config dataclass bundling imported capabilities; if the interface owns a config type, reference it instead of redefining it.
4. For assembler implementations, list the wired concrete implementations in a Composition section (names only).
5. State which operations it implements; describe responsibilities declaratively. The implementation HLS's Deltas are the semantic source; Refined terms pin the concrete conditions and values.
6. Define internal behavioral invariants.
7. List Non-Concerns implementers might otherwise worry about (optional).

## What NOT to Expose

Internal mechanics, guarantees, bookkeeping, persistence operations, validation, between-operation changes, and mutations to client-owned data are not component-provided operations.

## Validation Checklist

- [ ] Every LLS statement traces to the HLS's effective constraint set (own lines + transitive closure)
- [ ] LLS dependency comment (first line) lists only LLS files; no HLS references; no implementation LLS dependencies
- [ ] Dependency comment mirrors the HLS front matter plus any component named in prose; every entry is imported or referenced; no spurious entries
- [ ] Type-level LLS imports stay inside the converted HLS's closure; outside dependencies require an HLS amendment first
- [ ] Each interface defines its own types in its own Data Types; owned types imported elsewhere, never redefined
- [ ] HLS withholdings resolved: opaque → type variable or pass-through type; open → concrete type; hook → concrete condition or explicit signal
- [ ] Implementation HLS refinements (`terms (refined):`) made concrete in the implementation LLS
- [ ] Type aliases and signatures are single-line code blocks; multi-line only for Config dataclasses/unions/complex dataclasses
- [ ] No comments in code blocks
- [ ] Descriptive domain-specific type names (never generic `Message`/`Result`/`Status`/`Data`)
- [ ] Mutually exclusive outcomes encoded as discriminated unions with `Literal` discriminators
- [ ] Pass-through values use type variables; roles documented; interface specs never resolve type variables in prose
- [ ] Interfaces with implementations declare `Protocol` classes; operations are methods, never free functions
- [ ] Every operation has a brief HLS justification; self-contained with all rules collected
- [ ] No operations for internal behavior (propagation, persistence, validation); no monolithic read/write operations
- [ ] Error handling only for explicit HLS failure conditions; expected failures are return-value signals
- [ ] Unexpected failures (precondition violations) not documented in interface specs
- [ ] Concrete strings pinned in implementation specs; error-message wording stated only when a test must assert it
- [ ] Interface deferrals ("pinned in the implementation spec") are backed by statements in the named implementation LLS
- [ ] Interface pins of error-detail absence allowed only when a test must assert them; presence never stated
- [ ] Implementation LLS exists only if an implementation HLS exists (`fulfills:` an interface)
- [ ] Implementation class declared as `class FooImpl(Foo): ...`; name matches the interface only when exactly one implementation will ever exist
- [ ] Abstract implementation bases named distinctly (`BaseFoo`); no abstract class takes the bare `FooImpl` name
- [ ] Implementation sections never mention "client" (reference the interface contract instead)
- [ ] Implementation Config bundles capabilities or references the interface-owned config type; does not redefine it
- [ ] Interface-owned config typed in the Interface LLS Data Types with descriptive names
- [ ] Operation postconditions describe outcomes, not mechanisms; external-system interactions excepted
- [ ] Non-Concerns (optional) records pinned choices with justifications
- [ ] LLS is detailed enough to write passing tests
