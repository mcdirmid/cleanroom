# Guide: Converting a Low-Level Specification to a High-Level Specification

## Purpose

Starting from an LLS, produce an HLS by removing concrete types, signatures, and implementation details. The LLS specifies *how* a component is built; the HLS specifies *what* it does and what clients can rely on.

The relationship is distillation, not transformation: the LLS gives a guarantee form ("`run_request(...) -> RequestResult[T]` returns a `Termination[T]` containing that value"); the HLS states it ("the component guarantees that termination values pass through unchanged").

Authoritative references: `high_level_spec.md` (the target format — its Five Pillars, Document Structure, Writing Rules, and Validation Checklist govern the result) and `low_level_spec.md` (the source format). This guide is the conversion procedure between them.

Distillation preserves grounding. The HLS is *groundable*, not fully grounded: it pins the use level (what clients observe) and designates the refinement site; the LLS and tests supply the lower levels. When you withhold a detail, mark the withholding (opaque / open / hook) and name what remains observable: **meaning may be withheld, observability never is.** Everything the LLS pins that is observable must survive distillation; everything that is purely form (types, signatures, constants) stays behind.

## Conversion Reading

1. Read the corresponding LLS file.
2. Read the HLS and LLS of every component referenced in that LLS's dependency comment (its first line).
3. Write the HLS as a stand-alone document; readers use it without the LLS.

HLS files depend only on HLS files, and LLS files depend only on LLS files; the conversion is the only time you read both. The HLS never references the LLS: its front matter (`imports:`, `fulfills:`) lists only HLS files.

**Front matter mirrors the LLS dependency comment.** Each LLS dependency (`X-low.md`) becomes the corresponding HLS import (`imports: X`, `terms (from X):`, or `fulfills: X`), whether or not a type was imported — a component named only in LLS prose is still a dependency. The HLS never imports an interface the LLS never references, and never imports an implementation spec. A term the LLS imports from `X` is attributed to `X` even when the LLS obtained the type through a re-exporting interface. External dependencies (filesystem, external services) go to Deltas External Dependencies, never `imports:`.

**Key difference from the LLS:** the LLS is organized by operation and is detailed (types, signatures, preconditions, postconditions); the HLS is organized by **concern** and is abstract — Purpose, Owned definitions, Observable dataflow, Contract, and Non-concerns for interfaces; Deltas and Non-concerns for implementations. No types, no signatures, no implementation mechanics. Group related behaviors by concern, not by operation: a rule that appears under several operations in the LLS is stated once in the HLS, in the section that owns the concern.

## Core Rules

1. **Document failures explicitly.** State what failures the component handles and what failure means for state and outputs — semantically ("signals failure, leaving state unchanged"), never procedurally ("returns an error code"). Actual error strings never appear in the HLS; a Non-concerns entry may de-scope the exact wording ("the exact wording is unspecified") without stating what it would be. An LLS return-value signal handled during normal use (validation failure, policy violation) distills to a semantic guarantee; a precondition violation stays an assumption, not a failure.
2. **Document policies.** Behavioral constraints (ordering, atomicity, routing rules) belong in the HLS, as they affect correctness: ordering in Observable dataflow; persistence, termination, atomicity, and routing in the Contract guarantees — each fact once, in exactly one section. Declarative only: "the new record is persisted before the old record is deleted", never "persists the new record, then deletes the old record".
3. **Document unconstrained behavior.** The HLS Non-concerns lists only aspects that remain non-concerns in the LLS: if the LLS pins a choice (in its Data Types, operations, or Non-Concerns), it is a concern and must not be listed. "Implementations may differ" contradicts an LLS that has fixed the detail.
4. **No types, no signatures.** Zero type declarations, function signatures, parameter lists, or return types. Concepts are described in prose: concepts that would appear as types become terms in Owned definitions (use-level; see Interface Spec Sections); their dataflow is described in Observable dataflow. No implementation details either: no external libraries (except Rule 7), no algorithm choices, no internal data structures, no mechanisms — the HLS says *what*, not *how*.
5. **State constraints are observable dataflow.** Document what is retained, what persists across restarts, what is per-run, what ordering is observable, what terminates the flow. Persistence and termination commitments live in the Contract guarantees (interface) or Deltas State Management (implementation); Observable dataflow covers what enters, what exits, and ordering.
6. **Cross-component communication.** Explain routing rules, message formats, and protocol semantics in Observable dataflow and the Contract. An implementation spec names the interfaces it uses in `imports:` and describes how it uses them in Deltas Behavior and External Dependencies.
7. **Permissible exception — named library.** If a component's behavior is defined by an external library, naming it is acceptable ("Uses the Stripe API for payment processing") — external dependency ownership, not implementation detail.
8. **Ownership is explicit.** Front matter declares ownership: `terms (owned):` for terms the component owns, `fulfills:` for the interface it fulfills, `imports:` for dependencies, `terms (from X):` for terms used from other specs. Ownership determines what the client configures, what the client provides, and what the component provides back — the Contract's sections.
9. **Absence-of-behavior statements** survive distillation only when a client can observe the absence. Cross-component pointers ("the agent loop handles detection of free-text responses") belong to the owning spec, not to the component being distilled.

## Distillation Procedure

For each LLS section, produce the corresponding HLS content:

- Data Types → Owned definitions (use-level; withholdings marked) + Observable dataflow; imported types → `terms (from X):` lines
- Dependency comment (first line) → HLS front matter (mirror; HLS files only; external dependencies go to Deltas External Dependencies)
- Protocol class operations → Contract "The client may:" verb phrases
- Preconditions → Contract "The component assumes:"
- Postconditions → Contract "The component guarantees:" (grouped by concern)
- Failure Handling → Contract guarantees/assumptions, described semantically
- Invariants → Observable dataflow (interface) or Deltas State Management (implementation)
- Config (capability bundling) → Implementation front matter `imports:`; Deltas External Dependencies
- Composition (concrete implementations) → Implementation front matter `imports:` (interfaces only; concrete choices are LLS-level)
- Behavioral Description → Implementation Deltas Behavior; per-concern deltas where they exist
- Non-Concerns → HLS Non-concerns — only aspects that remain non-concerns in the LLS

**Preserve semantics, not syntax — never reintroduce ambiguity the LLS resolved.** Keep the behavioral distinctions the LLS encodes, including its chosen readings. Termination (a channel that ends the session), channel failure (a failed channel action, recoverable), and run failure (run-level failure) remain distinct in HLS prose even though their signal names disappear — state them behaviorally ("Signals a channel failure, leaving the session active"). When the LLS pins a reading (both success and failure termination are terminal; the log file is written once assembly completes), the HLS states that reading. An HLS statement observably weaker or stronger than the LLS it distills is a conversion error.

## Interface Spec Sections

### Purpose

One or two sentences: what the component provides to clients. Nothing else.

### Owned definitions

Term meanings only — no behavior, no guarantees. Each term is defined at use level: precisely enough to use the interface and take the term for granted, no more. Where the LLS pins more than the user needs, withhold it — and say so:

- **Opaque** — meaning withheld: "an opaque value; the component does not inspect, transform, or interpret it; it passes through unchanged."
- **Open** — content withheld: "the exact content is unspecified."
- **Hook** — conditions withheld: "or custom conditions hold" — but only when the LLS leaves the condition open; a pinned condition is stated (a guarantee, or `terms (refined):` in the implementation spec), not hooked.

Every withholding names what *is* pinned — the observable consequence, the dataflow path, or the refinement site; a vague term with no pinned consequence is ungrounded. Every owned term is used or refined; a definition no one references is free-floating. Do not include concepts owned by other interfaces; reference them with `terms (from X):`. A type the interface inspects or routes is defined at use level; a type passing through unchanged becomes opaque; a type only the implementation fills becomes open. Attribute terms to their owners, not re-exporting interfaces (a type the LLS imports via `agent_loop` but `tool_provider` owns yields `terms (from tool_provider)`).

### Observable dataflow

What enters, what exits, ordering, persistence, termination — observable relationships only, never internal processing. Opaque values and open contents are named here: who produces them, who consumes them, what they trigger, what happens to them. The LLS's operations and their sequencing distill to the dataflow the client can observe.

### Contract

The complete behavior, one fact per line:

- **The client configures the component with** — items the client sets once at setup (the LLS's interface-owned Config type, if any). Assembler-supplied wiring belongs in the implementation spec. Omit when all inputs are per-operation.
- **For each [operation / session], the client provides** — per-use inputs.
- **The client may** — actions the client can initiate (the LLS's Protocol operations); each line is a verb phrase.
- **The component guarantees** — the behavioral contract, grouped by concern (the LLS's postconditions and invariants, distilled).
- **The component assumes** — prerequisites and invariants the component relies on (the LLS's preconditions).

## Implementation Spec Sections

### Front matter

`fulfills:` names the fulfilled contract; `imports:` names the HLS specs whose constraints are inherited; `terms (from X):` names terms used from other specs; `terms (refined):` names the withheld precision this implementation pins.

### Deltas beyond the <interface> contract

Implementation specs contain only deltas: the difference between the effective constraint set (own lines + inherited closure) and the inherited set — no restating. Optional sub-sections, each present only when the component adds something:

- **Behavior** — outcomes, not mechanisms; how imported interfaces are used.
- **Operation Boundaries** — atomicity, transaction scope, partial results.
- **Ordering** — sequencing guarantees beyond the interface.
- **State Management** — what state is maintained, persistence, caching, lifetime.
- **External Dependencies** — external systems and services (the LLS's Config and Composition, distilled to interfaces).
- **Error Handling** — how failures are detected and signaled, state implications.
- **Refined terms** — concrete definitions for hooks instantiated, open content filled, opaque roles identified: `- <term> -> <concrete definition>`.

A refinement **narrows** — it instantiates, fills, or identifies; never contradicts the interface; exists only when implementing requires the precision; binds locally, never propagating back to the interface.

### Non-concerns

Only aspects that remain non-concerns in the LLS, each self-justifying, as `- **[Aspect]:** Brief explanation of why it doesn't matter and what freedom implementers have.` Do not include implementation details that belong in the implementation LLS.

## Steps to the HLS

1. Identify the concerns the LLS addresses: dataflow, state, ordering, failures, cross-component interaction.
2. Distill each concern into prose — strip types, signatures, and mechanisms; keep the behavioral guarantees (per the Distillation Procedure mapping).
3. Write the interface spec: Purpose, Owned definitions (use-level, withholdings marked), Observable dataflow, Contract (one fact per line).
4. For implementations: write Deltas — Behavior plus only the per-concern sub-sections where a delta exists. Declare front matter by mirroring the LLS dependency comment; external dependencies go to Deltas External Dependencies.
5. Add Non-concerns for aspects that remain non-concerns in the LLS.
6. Verify per the Self-Check below.

## Self-Check

- [ ] Every contract item traces to the LLS
- [ ] Zero type declarations, function signatures, or parameter lists
- [ ] The HLS is about *what*, not *how*
- [ ] Failure conditions explicitly documented, semantically, never procedurally; no error-message content
- [ ] State management clearly stated in Observable dataflow (retention, persistence, per-session)
- [ ] Cross-component interaction documented (Observable dataflow; implementation `imports:` + Deltas)
- [ ] Non-concerns lists only aspects that remain non-concerns in the LLS
- [ ] Owned definitions use-level only; withholdings marked opaque / open / hook; each names what is pinned
- [ ] Terms used from elsewhere listed in `terms (from X):` and attributed to their owners
- [ ] Termination / channel failure / run failure remain distinct in the HLS prose
- [ ] No "returns" (use "provides," "signals," or "delegates")
- [ ] No pseudo-code identifiers (`exit_success`, `item_id`, `True`/`False`, `None`)
- [ ] Implementation never mentions "client"; Deltas do not repeat interface guarantees
- [ ] Front matter complete: `fulfills:`, `imports:`, `terms (from X):`, `terms (refined):` as needed
- [ ] HLS front matter mirrors the LLS dependency comment; no HLS import the LLS never references; external dependencies in Deltas, never `imports:`
- [ ] Hooks appear only where the LLS leaves the condition open; pinned conditions are stated, not hooked
- [ ] The HLS states the LLS's resolved readings; no ambiguity reintroduced, no statement observably weaker or stronger than the LLS
- [ ] Absence-of-behavior statements distilled only when client-observable; cross-component pointers live in the owning spec
- [ ] Refinements narrow, never contradict; declared in front matter and detailed in Deltas Refined terms
- [ ] Every guarantee testable from the specs alone; what the HLS withholds has a refinement site in the closure
- [ ] No restated inherited constraints (effective set = own lines + closure)
- [ ] Tables used only for rectangular matrices with self-contained cells — lists preferred
