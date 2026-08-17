# Guide: Converting a Low-Level Specification to a High-Level Specification

## Overview

Starting from an LLS, you produce an HLS by removing concrete types, signatures, and implementation details. The LLS specifies *how* a component is built in code; the HLS specifies *what* it does and what clients can rely on.

Think of the LLS-HLS relationship as distillation, not transformation:
- **LLS:** "The function `run_request(self, payload: str, ...) -> RequestResult[T]` returns a `Termination[T]` containing that value."
- **HLS:** "The component guarantees that termination values pass through unchanged."

The authoritative reference for the HLS side is `high_level_spec.md` — its Five Pillars, Document Structure, Writing Rules, and Validation Checklist govern the result. The LLS side is governed by `low_level_spec.md`. This guide is the conversion procedure: how to get from an LLS to an HLS.

Distillation preserves grounding. The HLS is *groundable*, not fully grounded: it pins the use level (what clients observe) and designates the refinement site; the LLS and tests supply the lower levels. When you withhold a detail, mark the withholding (opaque / open / hook) and name what remains observable: **meaning may be withheld, observability never is.** Everything the LLS pins that is observable must survive distillation; everything that is purely form (types, signatures, constants) stays behind in the LLS.

## Conversion Reading

1. Read the corresponding LLS file (the one with the same component name).
2. Read the HLS and LLS of every component referenced in that LLS's dependency comment (its first line).
3. Write the HLS as a stand-alone document; readers use it without the LLS.

HLS files depend only on HLS files, and LLS files depend only on LLS files; the conversion is the only time you read both. The HLS you produce must not reference the LLS: its front matter (`imports:`, `fulfills:`) lists only HLS files, and `terms (from X):` lines name only HLS specs.

**Front matter mirrors the LLS dependency comment.** The HLS front matter covers every interface the LLS depends on: each LLS dependency (`X-low.md`) becomes the corresponding HLS import (`imports: X`, `terms (from X):`, or `fulfills: X`), whether or not a type was imported — a component named only in LLS prose is still a dependency of the HLS. The HLS never imports an interface the LLS never references, and never imports an implementation spec. A term the LLS imports from `X` is attributed to `X` in the HLS even when the LLS obtained the type through a re-exporting interface. External dependencies (filesystem, external services) go to Deltas External Dependencies, never `imports:`.

**Key difference from LLS:** The LLS is organized by operation and is detailed (types, signatures, preconditions, postconditions). The HLS is organized by concern and is abstract: Purpose, Owned definitions, Observable dataflow, Contract, and Non-concerns for interfaces; Deltas and Non-concerns for implementations. No types, no signatures, no implementation mechanics. The HLS is what readers use to understand *what* a component does and *how it fits with other components*.

## Core Rules

### Rule 1: One Concern Per Section

Group related behaviors by concern, not by operation. The HLS collects all rules that apply to a concern across the entire LLS. One concern per section, one fact per line (Pillars 3 and 4 of the new guide). A rule that appears under several operations in the LLS is stated once in the HLS, in the section that owns the concern.

### Rule 2: Document Failures Explicitly

The HLS must explicitly document failure conditions — what failures the component handles, and what failure means for state and outputs. The LLS encodes failure in signatures and return types; the HLS encodes failure as behavior, semantically ("signals failure, leaving state unchanged"), never procedurally ("returns an error code"). Error-message wording is never part of the HLS; it is stated in the LLS only when a test must assert it. Actual error strings and details never appear in the HLS; a Non-concerns entry may de-scope the exact wording ("the exact wording is unspecified") without stating what it would be. An LLS return-value signal that the contract handles during normal use (validation failure, policy violation) distills to a semantic guarantee; a precondition violation stays an assumption, not a failure.

### Rule 3: Document Policies

Document behavioral constraints (ordering, atomicity, routing rules) in the HLS, as they affect correctness. Ordering, persistence, and termination appear in Observable dataflow; atomicity and routing appear in the Contract guarantees. Declarative only: "the new record is persisted before the old record is deleted", never "persists the new record, then deletes the old record".

### Rule 4: Document Unconstrained Behavior

The HLS must include a Non-concerns section listing aspects intentionally left unspecified because they do not affect correctness or observable behavior. Only aspects that remain non-concerns in the LLS belong here: if the LLS pins a choice for an aspect (in its Data Types, operations, or Non-Concerns), it is a concern, not a non-concern, and must not be listed. An HLS entry claiming "implementations may differ" contradicts an LLS that has already fixed the detail. When in doubt, check the corresponding LLS: the HLS Non-concerns is the subset of LLS non-concerns that stay unconstrained.

### Rule 5: No Types, No Signatures

The HLS contains zero type declarations, function signatures, parameter lists, or return types. Concepts are described in prose: the concepts that would appear as types become terms in Owned definitions, and their dataflow is described in Observable dataflow.

- A type the interface inspects or routes is defined at use level — precisely enough to use the interface, no more.
- A type that passes through unchanged becomes an **opaque** term: "an opaque value; the component does not inspect, transform, or interpret it; it passes through unchanged."
- A type whose content only the implementation fills becomes an **open** term: "the exact content is unspecified."
- A condition the implementation chooses becomes a **hook**: "or custom conditions hold." — but only when the LLS leaves the condition open. If the LLS pins the condition, the HLS states it (a guarantee, or a `terms (refined):` in the implementation spec), not a hook.
- Types imported from other interfaces become `terms (from X):` references — never re-definitions. Attribute the term to the interface that owns it, not a re-exporting interface: a type the LLS imports via `agent_loop` but that `tool_provider` owns yields `terms (from tool_provider)`. The LLS's type-variable roles and reused imports show which terms pass through and which are shared.

### Rule 6: State Constraints are Observable Dataflow

Document all state constraints: what is retained, what is not, what persists across restarts, what is per-run, what ordering is observable, what terminates the flow. State management is a primary concern in the HLS and lives in Observable dataflow (interface) or Deltas State Management (implementation).

### Rule 7: Cross-Component Communication

The HLS must explain how the component communicates with other components: routing rules, message formats, and protocol semantics — in Observable dataflow and the Contract. An implementation spec names the interfaces it uses in `imports:` front matter and describes how it uses them in Deltas Behavior and External Dependencies.

### Rule 8: Ownership is Explicit

Front matter declares ownership. The component owns the terms in its Owned definitions (`terms (owned):`), fulfills its interface (`fulfills:`), and imports what it depends on (`imports:`); terms it uses from other specs are listed (`terms (from X):`). Ownership determines what the client configures, what the client provides, and what the component provides back — the Contract's sections.

### Rule 9: Keep It Abstract

No implementation details: no external libraries, no algorithm choices, no internal data structures, no mechanism descriptions. The HLS says *what*, not *how*. An implementation LLS's Behavioral Description distills to Deltas Behavior outcomes, never to its code.

Absence-of-behavior statements survive distillation only when a client can observe the absence. Cross-component pointers ("the agent loop handles detection of free-text responses") belong to the owning spec, not to the component being distilled.

### Rule 10: Permissible Exception — Named Library

If a component's behavior is defined by an external library, naming it is acceptable (e.g., "Uses the Stripe API for payment processing"). This is external dependency ownership, not implementation detail.

---

## Distillation Procedure

For each LLS section, produce the corresponding HLS content:

- Data Types (types, type variables) → Owned definitions (use-level; withholdings marked) + Observable dataflow; imported types → `terms (from X):` lines
- Dependency comment (first line) → HLS front matter: `imports:` / `fulfills:` / `terms (from X):` (mirror; HLS files only; external dependencies go to Deltas External Dependencies, never `imports:`)
- Protocol class operations → Contract "The client may:" verb phrases
- Preconditions → Contract "The component assumes:"
- Postconditions → Contract "The component guarantees:" (grouped by concern)
- Failure Handling → Contract guarantees/assumptions, described semantically
- Invariants → Observable dataflow (interface) or Deltas State Management (implementation)
- Config (capability bundling) → Implementation front matter `imports:`; Deltas External Dependencies
- Composition (concrete implementations) → Implementation front matter `imports:` (interfaces only; concrete choices are LLS-level)
- Behavioral Description → Implementation Deltas Behavior; per-concern deltas where they exist
- Non-Concerns → HLS Non-concerns — only aspects that remain non-concerns in the LLS

**Preserve semantics, not syntax — and never reintroduce ambiguity the LLS resolved.** When distilling, keep the behavioral distinctions the LLS encodes — and its chosen readings. In particular, termination (a channel that ends the session), channel failure (a failed channel action, recoverable), and run failure (run-level failure) remain distinct concepts in the HLS prose, even though their signal names disappear. State them in behavioral terms (e.g., "Signals a channel failure, leaving the session active" / "Signals failure when the run mishandles a channel"). When the LLS pins a reading (e.g., both success and failure termination are terminal; the log file is written only once assembly completes), the HLS states that reading — distillation strips types and signal names, never behavioral distinctions. An HLS statement observably weaker or stronger than the LLS it distills is a conversion error.

---

## Interface Spec Sections

### Purpose

One or two sentences: what the component provides to clients. Nothing else — no definitions, no guarantees, no dataflow.

### Owned definitions

Term meanings only — no behavior, no guarantees. Each term is defined at use level: precisely enough to use the interface and take the term for granted, no more. Where the LLS pins more than the user needs, withhold it — and say so:

- **Opaque:** the user does not need the meaning at all: "an opaque value; the component does not inspect, transform, or interpret it; it passes through unchanged."
- **Open:** the user does not need the content: "the exact content is unspecified."
- **Hook:** the user does not need the conditions: "or custom conditions hold."

Every withholding names what *is* pinned — the observable consequence, the dataflow path, or the designated refinement site. A vague term with no pinned consequence is ungrounded. Every owned term is used by someone or refined by an implementation; a definition no one references is free-floating.

Do not include concepts owned by other interfaces; reference them with `terms (from X):` front matter.

### Observable dataflow

What enters, what exits, ordering, persistence, termination — observable relationships only, never internal processing. Opaque values and open contents are named here: who produces them, who consumes them, what they trigger, what happens to them. The LLS's operations and their sequencing distill to the dataflow the client can observe.

### Contract

The contract specifies the complete behavior: what the client must provide, what the component does, and what the component assumes. Each sub-section is a list — one fact per line:

- **The client configures the component with** — items the client of the interface sets once at setup. Captures the interface-owned configuration (the LLS's interface-owned Config type, if any). Configuration the assembler supplies instead (wiring concrete implementations together) belongs in the implementation spec, not the interface contract. When all inputs are per-operation, this section may be omitted.
- **For each [operation / session], the client provides** — per-use inputs.
- **The client may** — actions the client can initiate (the LLS's Protocol operations). Each line is a verb phrase.
- **The component guarantees** — the behavioral contract, grouped by concern (the LLS's postconditions and invariants, distilled).
- **The component assumes** — prerequisites and invariants the component relies on; the constraints the client must satisfy (the LLS's preconditions).

---

## Implementation Spec Sections

### Front matter

`fulfills: <interface>` names the contract being fulfilled; `imports:` names the HLS specs whose constraints are inherited; `terms (from X):` names the terms used from other specs; `terms (refined):` names the withheld precision this implementation pins.

### Deltas beyond the <interface> contract

Implementation specs contain only deltas: the difference between the effective constraint set (own lines + inherited closure) and the inherited set. No restating. Optional sub-sections, each present only when the component adds something beyond the fulfilled interface:

- **Behavior** — outcomes, not mechanisms; how imported interfaces are used.
- **Operation Boundaries** — atomicity, transaction scope, partial results.
- **Ordering** — sequencing guarantees beyond the interface.
- **State Management** — what state is maintained, persistence, caching, lifetime.
- **External Dependencies** — external systems and services (the LLS's Config and Composition, distilled to interfaces).
- **Error Handling** — how failures are detected and signaled, state implications.
- **Refined terms** — concrete definitions for hooks instantiated, open content filled, opaque roles identified: `- <term> -> <concrete definition>`.

A refinement **narrows**: it instantiates, fills, or identifies — it never contradicts the interface definition. It exists only when implementing requires the precision the interface withheld, and it binds locally: it never propagates back to the interface.

### Non-concerns

Document constraints intentionally left unspecified because they do not affect correctness or observable behavior.

**Non-concerns**

The following aspects are intentionally left unspecified and do not affect correctness or observable behavior. Implementations may differ in these details while still conforming to the specification.

- **[Aspect]:** Brief explanation of why it doesn't matter and what freedom implementers have.

Rules: only include aspects that could legitimately affect a reader's understanding; do not include implementation details that belong in the implementation LLS; each aspect should be self-justifying; **only list aspects that remain non-concerns in the LLS** — if the LLS pins a choice, it is a concern and must not be listed.

---

## Steps to the HLS

1. **Identify the concerns** the LLS addresses: dataflow, state, ordering, failures, cross-component interaction.
2. **Distill each concern into prose.** Strip types, signatures, and mechanisms; keep the behavioral guarantees. Use the Distillation Procedure mapping as a guide.
3. **Write the interface spec.** Purpose, Owned definitions (use-level, withholdings marked), Observable dataflow, Contract (client configures / provides / may / guarantees / assumes, one fact per line).
4. **For implementations:** write Deltas — Behavior plus only the per-concern sub-sections where a delta exists. Declare front matter (`fulfills:`, `imports:`, `terms (from X):`, `terms (refined):`) by mirroring the LLS dependency comment; external dependencies go to Deltas External Dependencies, never `imports:`.
5. **Add Non-concerns** for aspects that remain non-concerns in the LLS (aspects the LLS pins are concerns and are not listed).
6. **Verify.** No types, no signatures, no "returns," no pseudo-code identifiers, no implementation details, every guarantee testable, every term used or refined, every withholding marked and grounded.

---

## Self-Check

Before finalizing, verify:

- [ ] Every contract item traces to the LLS (does the LLS document this behavior?)
- [ ] The HLS contains zero type declarations, function signatures, or parameter lists
- [ ] The HLS is about *what*, not *how*
- [ ] Failure conditions are explicitly documented (not just implied by the LLS), described semantically ("signals failure, leaving state unchanged"), never procedurally
- [ ] State management is clearly stated in Observable dataflow (retention, persistence, per-session)
- [ ] Cross-component interaction is documented (Observable dataflow; implementation `imports:` + Deltas)
- [ ] Non-concerns section lists only aspects that remain non-concerns in the LLS (no pinned-in-LLS entries)
- [ ] Owned definitions are use-level only; withholdings marked opaque / open / hook; each names what is pinned
- [ ] Definitions are minimal and only include terms this interface owns; terms used from elsewhere listed in `terms (from X):`
- [ ] Termination / channel failure / run failure remain distinct in the HLS prose
- [ ] No use of "returns" (use "provides," "signals," or "delegates")
- [ ] No pseudo-code identifiers (`exit_success`, `item_id`, `True`/`False`, `None`) — natural language only
- [ ] Implementation never mentions "client"; Deltas do not repeat interface guarantees
- [ ] Front matter complete: `fulfills:`, `imports:`, `terms (from X):`, `terms (refined):` as needed
- [ ] HLS front matter mirrors the LLS dependency comment; no HLS import the LLS never references; external dependencies in Deltas, never `imports:`
- [ ] Terms attributed to their owners, not re-exporting interfaces
- [ ] Hooks appear only where the LLS leaves the condition open; pinned conditions are stated, not hooked
- [ ] The HLS states the LLS's resolved readings; no ambiguity reintroduced, no statement observably weaker or stronger than the LLS
- [ ] The HLS never states error-message content: actual strings and details never appear; de-scoping the exact wording is a Non-concerns entry, not a statement of content
- [ ] Absence-of-behavior statements distilled only when client-observable; cross-component pointers live in the owning spec
- [ ] Refinements narrow, never contradict; declared in front matter and detailed in Deltas Refined terms
- [ ] Every guarantee testable from the specs alone; what the HLS withholds has a refinement site in the closure
- [ ] No restated inherited constraints (effective set = own lines + closure)
- [ ] Tables used only for rectangular matrices with self-contained cells — lists preferred
