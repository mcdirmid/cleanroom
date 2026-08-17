# Guide: Converting a High-Level Specification to a Low-Level Specification

## Overview

Starting from an HLS, you produce an LLS by adding the concrete types, signatures, and behaviors that the HLS intentionally omits. The HLS specifies *what* a component does; the LLS specifies the types, signatures, preconditions, postconditions, and failure signals that realize those guarantees in code. The LLS must be detailed enough that tests and an implementation can be written from it independently and pass when both conform.

Think of the HLS-LLS relationship as elaboration, not transformation:
- **HLS:** "The component guarantees that termination values pass through unchanged."
- **LLS:** "The function `run_request(self, payload: str, ...) -> RequestResult[T]` returns a `Termination[T]` containing that value."

The authoritative references are `high_level_spec.md` (the HLS format this guide converts from — its Five Pillars, Structure, Writing Rules, and Validation Checklist) and `low_level_spec.md` (the LLS format this guide converts to — its Structure, Writing Rules, Terminology, and Validation Checklist govern the result). This guide is the conversion procedure: how to get from an HLS to an LLS.

The HLS you start from is a set, not just a file: its effective constraint set is its own lines plus the transitive closure of every spec it references (`imports:` and `fulfills:` front matter, and their references in turn). Because the HLS inherits constraints without restating them, the LLS must inline the entire closure. What the HLS withholds — opaque values, open contents, hooks, details left to the form level — is exactly what the LLS pins.

## Conversion Reading

1. Read the corresponding HLS file (the one with the same component name).
2. Read the transitive closure: every spec named in the HLS's front matter (`imports:` and `fulfills:`), and their imports, until the closure is complete. `terms (from X):` lines name the specs whose definitions are in play.
3. Read the LLS of every component in that closure: the LLS you produce depends only on LLS files, so the dependency LLS files are where the types you import are defined.
4. Write the LLS as a stand-alone document; readers use it without the HLS.

HLS files depend only on HLS files, and LLS files depend only on LLS files; the conversion is the only time you read both. The LLS you produce must not reference the HLS: its dependency comment (the first line of the file) lists only LLS files, and no LLS depends on an implementation LLS.

**Dependency comment = HLS front matter mirrored.** The LLS dependency comment lists the LLS of every interface named in the converted HLS's front matter — `imports:`, `fulfills:`, and `terms (from X):` — whether or not a type is imported; a prose-only concept reference is still a dependency, since its definitions are read alongside. Add any component named in LLS prose that is not in the HLS front matter. An entry is spurious only when it is neither imported, nor referenced, nor named in the HLS front matter.

**Key difference from HLS:** The HLS is organized by concern (Purpose, Owned definitions, Observable dataflow, Contract, Non-concerns; implementation Deltas); the LLS is organized by operation. Each operation's documentation collects ALL rules that apply to it — preconditions, postconditions, error conditions, ordering constraints, failure semantics, routing rules — even when those rules appear in different parts of the HLS, or in different specs of its closure. The LLS is the single source of truth for "what does this operation do?" without jumping between sections or files.

**Note on "Returns":** The HLS prose prohibits "returns" (use "provides," "signals," or "delegates"). In the LLS, "returns" is acceptable in Python signatures and in explanations of return semantics. The two registers serve different audiences.

## Core Rules

### Rule 1: Traceability

Every LLS statement traces to the HLS's effective constraint set: the spec's own lines plus the transitive closure of the specs it references. Because inherited constraints are never restated in the HLS, trace a statement to any spec in the closure, not just the file you are converting. The LLS cannot add behavior not implied by the closure; it can (and must) add details the HLS omits — types, signatures, constants, parameter values, error strings — as long as the behavior is implied. Ask: "Is this behavior implied by the HLS, somewhere in its closure?" If you cannot answer yes, remove it. Implementation details (like transactions) may be added only as necessary to fulfill HLS guarantees.

**Type-level links stay inside the closure.** The LLS imports only from interfaces inside the converted HLS's closure (the transitive set of its `imports:` / `fulfills:` front matter). A type-level dependency outside that closure — extending a Protocol from an unrelated spec, reusing its type variables — is a traceability violation: amend the HLS first (declare the relationship with an `imports:` / `terms (from X):` line), then convert. The HLS names every interface the LLS may need; the LLS never invents one.

**The LLS never resolves HLS ambiguity silently.** When an HLS statement admits two observably different readings, amend the HLS to the intended reading before converting — the LLS does not pick for it. A narrowing that bounds a guarantee's scope (e.g., "the log file is always written" becomes "written once assembly completes") is recorded under the operation's Failure Handling or in Non-Concerns with a justification, and the HLS is amended to state the boundary.

**Absence-of-behavior statements have a home.** An HLS statement of absence ("the component does not prevent X") is recorded in the LLS as an invariant or postcondition note when a test could check it. When its substance belongs to another component (a cross-component pointer, e.g., "the agent loop handles detection of free-text responses"), it lives in that component's spec and the converted LLS records nothing — the converter names the owning spec. A statement neither testable in the LLS nor owned by another component is a dangling fact: cut it from the HLS.

### Rule 2: Don't Invent Failures

Only include error handling for explicit HLS failure conditions, anywhere in the closure. Assumptions ("assumes X") are not error conditions. Expected failures become return-value signals; unexpected failures are not documented in interface specs (see Failure Handling below).

### Rule 3: Don't Overprescribe Non-Concerns

Many aspects are intentionally unspecified because they do not affect correctness. List them in the LLS Non-Concerns section so implementers know they have freedom. Common aspects: ordering, algorithm choice, representation details, unhandled failure modes, caller constraints. Record each as `- **[Aspect]:** [Choice or assumption] — [Justification].` Non-Concerns is optional in both interfaces and implementations.

An HLS Non-concerns entry is not a license to drop the aspect from the LLS. The LLS is complete: where it pins a choice for an aspect the HLS left open, it records the choice in Non-Concerns with a justification. An HLS non-concern that the LLS pins becomes a pinned concern; an HLS non-concern the LLS leaves open stays open.

### Rule 4: Granularity and Signatures

- Define operations at the level of individual actions; do not force clients to read or write more than they need.
- Type aliases and signatures are single-line Python code blocks; multi-line blocks only for Config dataclasses, discriminated unions, and complex data structures with named fields. No comments in code blocks.
- Encode mutually exclusive outcomes as discriminated unions with `Literal` discriminators; do not approximate variants with a single dataclass of optional fields.
- Prefer type variables over `Any` for values that pass through unchanged. Document each type variable's role; give distinct roles distinct names; reuse imported type variables (e.g., `T` from the tool-provider interface). Interface specs never resolve a type variable to a concrete type — including in prose (`Outcome[T]`, not `Outcome[str]`); the implementation spec resolves it.
- Interfaces with implementations are `Protocol` classes whose methods are the operations — never free functions. A Protocol may be a dataclass combining static data fields with interface methods (e.g., `Node(Provider)`).
- Shared type ownership: define a type once, in the interface that owns the concept; import it elsewhere; never redefine an owned type. Import each type from the interface that owns it: importing through a re-exporting interface is an error — if a type appears in a signature, import it from its owner's LLS (`ToolDefinition` from `tool_provider`, not from `agent_loop`).

The HLS's Owned definitions and Observable dataflow name the concepts; the LLS Data Types give them form. Resolve the HLS's withholdings:

- An **opaque** term (passes through unchanged) becomes a type variable, or a concrete type whose contents the interface does not inspect.
- An **open** term (exact content unspecified) becomes a concrete type with named fields, or a documented contract for what the implementation fills in.
- A **hook** ("or custom conditions hold") becomes the concrete condition in the implementation, or an explicit signal in the interface.
- An implementation HLS's Refined terms (`terms (refined): <term> -> <concrete definition>`) name the withheld precision the implementation LLS must make concrete.

### Rule 5: Interface Operations Only

Component-provided operations only for client-initiated behaviors. Internal behaviors (propagation, persistence, validation) are postconditions, not operations. "Client provides" → imported at initialization; "client initiates" → component-provided operation. In the HLS, client-initiated behaviors appear in the Contract's "The client may:" list; if you cannot produce a direct line from that list justifying an operation, remove it. Never add operations named `propagate_*`, `persist_*`, `validate_*`, `track_*`, `notify_*`, or `sync_*`.

### Rule 6: Operations Are Self-Contained

Every operation's documentation must be self-contained. All rules that apply to the operation — preconditions, postconditions, invariants, error conditions, ordering constraints, failure semantics, routing rules — appear directly under that operation. Do not rely on the reader to cross-reference other sections. This is the LLS mirror of the HLS's constraint inheritance: the HLS spreads constraints across its closure and never restates them; the LLS inlines the whole closure under each operation.

### Rule 7: Implementation LLS Only When the HLS Defines One

Only produce an Implementation LLS section if the HLS defines an implementation for the interface — an implementation spec (a `*_impl` file) whose front matter says `fulfills: <interface>`. Otherwise the interface LLS stands alone. When one does exist:

- Declare the implementation class as a single-line `class FooImpl(Foo): ...` extending the interface's Protocol.
- The implementation name matches the interface name only when exactly one implementation will ever exist for the interface; multi-implementation interfaces use distinct names (e.g., `csv_inventory_impl` implements `inventory`). With an abstract base plus concrete subclasses, the base is named distinctly (`BaseFoo`, `FooBase`, or a purpose prefix) — the interface-matching name (`FooImpl`) is reserved for the concrete class that fulfills the contract. A concrete class with a distinguishing prefix (`FooFileImpl`) means the interface is multi-implementation in the naming sense, and no class takes the bare `FooImpl` name.
- Implementation sections never refer to "client" — reference the interface contract instead (e.g., "Configured with SKU list and reorder thresholds (per the `inventory` interface contract)"), never "the client configures the component with...".
- Config bundles imported capabilities (implementation-owned) or references the interface-owned config type (see Configuration Ownership); it never redefines it.
- Behavioral Description states outcomes, not mechanisms; interactions with external systems may be described in terms of the external protocol.
- Non-Concerns records pinned choices (optional).

The implementation HLS's Deltas are the semantic source: Behavior, Operation Boundaries, Ordering, State Management, External Dependencies, and Error Handling map onto the implementation LLS sections; Refined terms name the withheld precision the LLS must make concrete.

### Rule 8: Describe Outcomes, Not Mechanisms

Describe *what* the operation guarantees, not *how* the implementation achieves it.

- Avoid "Iterates until..." — use "Completes when..."
- Avoid "Continues looping while..." — use "Processes all..."
- Avoid "Returns after..." — use "Returns when..."
- Avoid "Calls X then Y" — use "X occurs before Y"

Implementation details belong in the Behavioral Description, not in operation preconditions or postconditions.

### Rule 9: Interface Granularity

Split interfaces when responsibilities differ (persistence vs. logic vs. orchestration). Each interface should have a single responsibility.

### Rule 10: HLS Justification Format

Keep HLS justifications to one sentence or a brief phrase. Justifications must be consistent with the HLS — they need not quote it directly. Do not use the word "definition" in place of "interface" or "implementation".

---

## Failure Handling: Expected vs. Unexpected

The HLS describes failures semantically in prose — what failure means for the component's state and outputs ("signals failure, leaving the queue unchanged and halting the operation"). The LLS encodes failure in signatures and return types — the concrete signal (`None`, `False`, exception, `Result`). Translate each semantic HLS failure condition into a concrete code-level signal:

- **Expected failures** — conditions the contract handles during normal use (validation failures, policy violations) — are return-value signals, documented in the interface spec. Never raise exceptions for expected conditions.
- **Unexpected failures** — precondition violations, filesystem errors, state corruption — are exceptions or undefined behavior and are not documented in interface specs. Preconditions are caller obligations, not failure signals: the interface states the precondition and nothing more. An implementation may document a violation response in its implementation spec if useful, but none is required (e.g., `inventory_impl` documents `ValueError` for unknown SKUs).
- **Concrete strings** (error messages, fallback text) are pinned in implementation specs, not interface specs. Interfaces document the signal type, the failure categories, and the state preserved on failure. Error-message wording is stated only when a test must assert it — and then only in the implementation spec; otherwise it is not stated at all (not even as "unspecified"). An interface may pin the **absence** of error detail when a test must assert it ("failure results carry no message detail"), recorded in Non-Concerns with a justification; it never states what detail **would** appear. An interface may defer a detail with "pinned in the implementation spec" only when the named implementation LLS actually states it — the converter verifies each deferral's target; an unbacked deferral is an error (add the statement to the implementation spec, or drop the deferral from the interface).
- **Terminology:** distinguish termination (a channel that ends the session), channel failure (a failed channel action, recoverable), and run failure (run-level failure). Do not conflate them; see `low_level_spec.md` → Terminology.

Every HLS failure statement names a state effect; every one of those state effects must be representable in the LLS — as a precondition, a postcondition, or a return-value signal. An HLS failure the LLS cannot express is a conversion error.

---

## Configuration Ownership

Configuration comes in two kinds, and each lives in exactly one place. The deciding question is **who supplies it**: the client of the interface, or the assembler that wires implementations together.

- **Interface-owned configuration** — configuration the client of the interface supplies (the HLS Contract's "The client configures the component with:" list): SKU list, reorder thresholds, connection parameters. Because the interface's client must construct it to use the interface, it is typed in the Interface LLS Data Types with a descriptive name (`InventoryConfig`, `PricingConfig`, `LedgerConfig`), never the bare name `Config`.
- **Implementation-owned configuration** — capability bundling: which implementations an implementation uses. This is known only to the assembler (the code that wires concrete implementations together), not to the interface's client, so it belongs in the Implementation LLS Config section (e.g., `fulfillment_impl`'s `Config` bundling `inventory` and `pricing`). In the HLS this is the implementation spec's `imports:` front matter and Deltas External Dependencies.

**Decision test:** Who supplies this configuration — the client of the interface, or the assembler? Supplied by the interface's client → interface-owned (Interface LLS Data Types). Supplied by the assembler (it only wires implementations together) → implementation-owned (Implementation LLS Config). **No capabilities to bundle:** the Config section references the interface-owned type or states "None."

---

## LLS Structure

```
1. [Interface LLS: name]                  — repeatable
   1.1 Data Types                         — types, type variables, the Protocol class
   1.2 Component-Provided Operations      — each operation, fully self-contained
   1.3 Invariants
2. [Implementation LLS: name]             — only if an implementation HLS exists (`fulfills:` an interface)
   2.1 Data Types                         — imports + `class FooImpl(Foo): ...`
   2.2 Config                             — capability bundling (or a reference to the interface-owned config)
   2.3 Composition                        — concrete implementations an assembler wires together (assembler implementations only)
   2.4 Behavioral Description
   2.5 Invariants
   2.6 Non-Concerns
```

Term definitions (cross-cutting behavioral rules such as stubbing semantics) go between Data Types and Component-Provided Operations. Non-Concerns is optional.

---

## Operation Documentation Template

### `operation_name`

    def operation_name(self, param: Type) -> ReturnType

Operations are methods of the interface's `Protocol` class (declared in Data Types).

**Purpose:** [What the operation does.]

**Preconditions:** [Conditions that must be true before calling.]

**Postconditions:** [State changes, return semantics, ordering, routing, guarantees — declarative language.]

**Failure Handling:** [Error conditions and signaling; expected failures as return values, unexpected failures not documented.]

**HLS Justification:** [Brief phrase consistent with the HLS — traceable to a line in the HLS closure.]

---

## Step-by-Step Process

### Interface LLS

1. Identify component-provided operations from client-initiated HLS behaviors — the Contract's "The client may:" list.
2. Define type aliases for concepts owned by this interface — from Owned definitions and Observable dataflow; terms imported from other specs (`terms (from X):`) map to imported types. Type the client-supplied configuration listed in the HLS Contract's "The client configures the component with:" (interface-owned config); declare the interface as a `Protocol` class whose methods are the operations.
3. Import types from other interfaces as needed; list every dependency in the dependency comment (the first line of the file). The dependency comment mirrors the converted HLS's front matter (`imports:` / `fulfills:` / `terms (from X):`) plus any component named in prose. An entry is justified by an import, a direct reference in the file (e.g., a component named in the Composition or Behavioral Description), or a front-matter line in the HLS; it is spurious only when none of these hold. Remove spurious entries.
4. Resolve the HLS's withholdings: an opaque term becomes a type variable or a pass-through type; an open content becomes a concrete type with fields; a hook becomes the concrete condition or an explicit signal. Check the implementation spec's Refined terms for the withheld precision the implementation pins.
5. For each operation, collect ALL rules that apply to it from across the HLS closure: preconditions from assumptions and ordering; postconditions from guarantees and behavioral rules; error handling from failure semantics; routing from Observable dataflow and message definitions; ordering from cross-cutting concerns.
6. Document each operation with the template, including all collected rules.
7. Add term definitions for cross-cutting behavioral rules (between Data Types and Operations).
8. Define global invariants.

### Implementation LLS (only if an implementation HLS exists)

1. Identify which interfaces it depends on: the interface it fulfills (from the implementation HLS's `fulfills:`), plus any other interfaces named in its `imports:` and `terms (from X):` front matter, plus any component named in the LLS prose. List them in the dependency comment (interfaces only — never another implementation LLS).
2. Declare `class FooImpl(Foo): ...` in Data Types.
3. Define a Config dataclass bundling imported capabilities; if the interface owns a config type, reference it instead of redefining it.
4. For assembler implementations, list the concrete implementations wired together in a Composition section (names only — not dependencies).
5. State which operations it implements; describe responsibilities declaratively (outcomes, not mechanisms). The implementation HLS's Deltas — Behavior, Operation Boundaries, Ordering, State Management, External Dependencies, Error Handling — are the semantic source; Refined terms pin the concrete conditions and values.
6. Define internal behavioral invariants.
7. List Non-Concerns implementers might otherwise worry about (optional).

---

## What NOT to Expose

Internal mechanics, guarantees, bookkeeping, persistence operations, validation, between-operation changes, and mutations to client-owned data are not component-provided operations.

---

## Validation Checklist

- [ ] Every LLS statement traces to the HLS's effective constraint set (own lines + transitive closure of `imports:` / `fulfills:`)
- [ ] LLS dependency comment (first line) lists only LLS files; no HLS references; no implementation LLS dependencies
- [ ] Every dependency-comment entry is actually imported or referenced (a direct reference, e.g. in Composition or Behavioral Description, is sufficient)
- [ ] LLS dependency comment mirrors the HLS front matter (`imports:` / `fulfills:` / `terms (from X):`) plus any component named in prose; no spurious entries
- [ ] Type-level LLS imports stay inside the converted HLS's closure; a dependency outside it required an HLS amendment first
- [ ] Each interface defines its own types in its own Data Types subsection; owned types imported elsewhere, never redefined
- [ ] HLS withholdings resolved: opaque → type variable or pass-through type; open → concrete type; hook → concrete condition or explicit signal
- [ ] Implementation HLS refinements (`terms (refined):`) made concrete in the implementation LLS
- [ ] Type aliases and function signatures are single-line code blocks; multi-line only for Config dataclasses/unions/complex dataclasses
- [ ] No comments in code blocks
- [ ] Types use descriptive domain-specific names (never generic `Message`/`Result`/`Status`/`Data`)
- [ ] Mutually exclusive outcomes encoded as discriminated unions with `Literal` discriminators
- [ ] Pass-through values use type variables; roles documented; interface specs never resolve type variables to concrete types, including in prose
- [ ] Interfaces with implementations declare `Protocol` classes; operations are methods, never free functions
- [ ] Every operation has a brief HLS justification; self-contained with all rules collected
- [ ] No operations for internal behavior (propagation, persistence, validation); no monolithic read/write operations
- [ ] Error handling only for explicit HLS failure conditions; expected failures are return-value signals
- [ ] Unexpected failures (precondition violations) not documented in interface specs; preconditions stated as caller obligations only
- [ ] Concrete strings (error messages, fallback text) pinned in implementation specs; error-message wording stated only when a test must assert it
- [ ] Interface deferrals ("pinned in the implementation spec") are backed by statements in the named implementation LLS
- [ ] Interface pins of error-detail absence allowed only when a test must assert them; presence never stated
- [ ] Implementation LLS exists only if an implementation HLS exists (`fulfills:` an interface)
- [ ] Implementation class declared as `class FooImpl(Foo): ...`; implementation name matches the interface only when exactly one implementation will ever exist
- [ ] Abstract implementation bases named distinctly (`BaseFoo`); no abstract class takes the bare `FooImpl` name
- [ ] Implementation sections never mention "client" (reference the interface contract instead)
- [ ] Implementation Config bundles capabilities or references the interface-owned config type; does not redefine it
- [ ] Interface-owned config (from the HLS Contract's "The client configures the component with:") typed in the Interface LLS Data Types with descriptive names
- [ ] Operation postconditions describe outcomes, not mechanisms; external-system interactions excepted
- [ ] Non-Concerns (optional) records pinned choices with justifications
- [ ] LLS is detailed enough to write passing tests
