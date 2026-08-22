# Guide: Converting a High-Level Specification to a Low-Level Specification

## Purpose

Starting from an HLS, produce an LLS by adding the concrete types, signatures, and behaviors the HLS intentionally omits. The HLS specifies *what* a component does; the LLS specifies the types, signatures, preconditions, postconditions, and failure signals that realize those guarantees in code — detailed enough that tests and an implementation can be written from it independently and pass when both conform.

The relationship is elaboration, not transformation: the HLS states a guarantee ("termination values pass through unchanged"); the LLS gives it form ("`run_request(...) -> RequestResult[T]` returns a `Termination[T]`").

Authoritative references: `high_level_spec.md` (source format) and `low_level_spec.md` (target format). This guide is the conversion procedure between them.

## Conversion Reading

The HLS you convert is a set, not just a file: its effective constraint set is its own lines plus the transitive closure of every spec it references (`imports:` and `fulfills:`, and their references in turn). The LLS must inline the entire closure; what the HLS withholds — opaque values, open contents, hooks — is exactly what the LLS pins.

1. Read the HLS file for the component.
2. Read the transitive closure: every spec named in the HLS front matter (`imports:`, `fulfills:`, `terms (from X):`), recursively.
3. Read the LLS of every component in that closure — the LLS depends only on LLS files.
4. Write the LLS as a stand-alone document; readers use it without the HLS.

**Dependency comment = HLS front matter mirrored.** The LLS dependency comment (first line of the file) lists the LLS of every interface named in the converted HLS's front matter — `imports:`, `fulfills:`, `terms (from X):` — whether or not a type is imported; a prose-only concept reference is still a dependency. Add any component named in LLS prose not in the HLS front matter; an entry is spurious only when it is neither imported, nor referenced, nor named in the front matter.



**The LLS has no terms front matter.** The dependency comment is the LLS's *only* front matter: no `terms (owned):` or `terms (from X):` section. The HLS's `terms (owned):` becomes type aliases; a `terms (from X):` entry becomes a dependency-comment entry and imports of X's types; never restate the HLS's term list.

**Key difference from the HLS:** the HLS is organized by concern (Purpose, Terms, Contract, Non-concerns; the Contract is a set of labeled blocks); the LLS is organized by **operation**, collecting ALL rules that apply to it — preconditions, postconditions, error conditions, ordering, failure semantics, routing — even across HLS sections, blocks, and specs of the closure.

**Note on "Returns":** the HLS prohibits "returns"; the LLS accepts it in signatures and prose.


## Core Rules

1. **Traceability.** Every LLS statement traces to the HLS's effective constraint set (own lines plus closure). The LLS cannot add behavior not implied by the closure; it can and must add details the HLS omits (types, signatures, constants, parameter values, error strings) as long as the behavior is implied. Implementation details may be added only as necessary to fulfill HLS guarantees.
   - **Type-level links stay inside the closure.** The LLS imports only from interfaces in the converted HLS's closure. A type-level dependency outside it is a traceability violation: amend the HLS first (declare the relationship with `imports:` / `terms (from X):`), then convert.
   - **Never resolve HLS ambiguity silently.** When an HLS statement admits two observably different readings, amend the HLS to the intended reading first; a narrowing that bounds a guarantee's scope is recorded under Failure Handling or in Non-Concerns with a justification.
   - **Absence-of-behavior statements have a home.** A statement of absence ("the component does not prevent X") is recorded as an invariant or postcondition note when a test could check it; otherwise it lives in the owning component's spec; neither testable nor owned elsewhere is a dangling fact — cut it from the HLS.

2. **Don't invent failures.** Include error handling only for explicit HLS failure conditions anywhere in the closure; assumptions are not error conditions. Expected failures become return-value signals; unexpected failures are not documented in interface specs.

3. **Don't overprescribe non-concerns.** Aspects intentionally unspecified because they do not affect correctness (ordering, algorithm choice, representation, unhandled failure modes, caller constraints) are listed in the LLS Non-Concerns as `- **[Aspect]:** [Choice] — [Justification].` Non-Concerns is optional; an LLS that pins a choice for an open aspect records it there with a justification.

4. **Granularity and signatures.** (Type rules per `low_level_spec.md` → Writing Rules; summary:)
   - Define operations at the level of individual actions; do not force clients to read or write more than they need.
   - Data Types opens with exactly one Python code block: all imports, type aliases, and classes — the interface's Protocol class last, declaring only its fresh (non-inherited) methods. Every interface declares its Protocol class, even when no implementation exists in the closure; the `### operation` signature blocks mirror its methods. Every type alias is `X: TypeAlias = ...` (from `typing`); never a bare `X = ...` except string constants and `TypeVar` declarations. No comments in code; prose explaining each type follows the block.
   - Encode mutually exclusive outcomes as discriminated unions with `Literal` discriminators; pass-through values use type variables (roles documented; interface specs never resolve them in prose); shared types are imported from their owner's LLS, never redefined (import from the owner — `ToolDefinition` from `tool_provider`, not `agent_loop`).
   - Resolve the HLS's withholdings: an **opaque** term becomes a type variable or a concrete type the interface does not inspect; an **open** term becomes a concrete type with named fields; a **hook** becomes the concrete condition in the implementation or an explicit signal in the interface. The implementation's `[refines]` lines name the withheld precision the implementation LLS makes concrete.

5. **Interface operations only.** Component-provided operations exist for client-initiated behaviors only. Internal behaviors (propagation, persistence, validation) are postconditions, not operations. "Client provides" → imported at initialization; "client initiates" → component-provided operation. In the HLS, client-initiated behaviors appear in the Contract's **Operations** block; if you cannot produce a direct line from that block justifying an operation, remove it. Never add operations named `propagate_*`, `persist_*`, `validate_*`, `track_*`, `notify_*`, or `sync_*`.

6. **Operations are self-contained.** Every operation's documentation collects ALL rules that apply to it — preconditions, postconditions, invariants, error conditions, ordering, failure semantics, routing — directly under that operation; the LLS inlines the whole closure under each operation.

7. **Implementation LLS only when the HLS defines one.** Produce an Implementation LLS section only if an implementation spec exists (`*_impl` file with `fulfills: <interface>`); otherwise the interface LLS stands alone. When one exists:
   - Declare the implementation as `class FooImpl(Foo): ...` extending the interface's Protocol. The name matches the interface only when exactly one implementation will ever exist; multi-implementation interfaces use distinct names. Abstract bases are named distinctly (`BaseFoo`).
   - Implementation sections never mention "client" — reference the interface contract instead ("per the `inventory` interface contract"). (The HLS forbids such pointers in its Deltas; the LLS may reference the contract.)
   - Configuration is the implementation class's `__init__` (in Data Types): bundled capabilities as parameters, an interface-owned config type as a single `config` parameter, none as no `__init__`. There is no Config section.
   - Behavioral Description states outcomes, not mechanisms; interactions with external systems may be described in terms of the external protocol.
   - Non-Concerns records pinned choices (optional).
   - The implementation HLS's Deltas are the semantic source: each line is a delta (untagged behavior, or tagged `[ordering]`, `[boundary]`, `[state]`, `[external]`, `[failure]`) mapping onto the implementation LLS sections; `[refines]` lines name the withheld precision to make concrete.

8. **Describe outcomes, not mechanisms.** "Iterates until..." → "Completes when..."; "Calls X then Y" → "X occurs before Y". Implementation details belong in the Behavioral Description, not in preconditions or postconditions.

9. **Interface granularity.** Split interfaces when responsibilities differ (persistence vs. logic vs. orchestration).

10. **HLS justification format.** Keep justifications to one sentence or a brief phrase, consistent with the HLS — they need not quote it.

## Named Contract Blocks

The HLS Contract's named blocks (`**Logging**`, `**Events**`, `**Stubbing**`, `**Views**`, `**Verification**`, `**Termination**`, `**Unexpected failures**`, ...) are sub-contracts, each holding guarantees about one concern. Common mappings:

- **Events / Logging** — the event list becomes a `Literal` union or callback signature in Data Types; log and path rules become postconditions, failure-handling notes, or an Invariant.
- **Stubbing / Views / behavioral sub-contracts** — becomes a term definition (per `low_level_spec.md` → Term Definitions) or an Invariant.
- **File operations / Verification / Termination** — a block describing client-invoked behaviors is a source of component-provided operations alongside the **Operations** block: the tools become operations, their facts becoming preconditions, postconditions, and failure handling.
- **Unexpected failures** — becomes the Failure Handling of the affected operations; concrete exception classes and strings are pinned in the implementation LLS.

A named block's facts appear in exactly one LLS location.

## Failure Handling: Expected vs. Unexpected

Translate each semantic HLS failure condition into a concrete code-level signal:

- **Expected failures** — conditions the contract handles during normal use (validation failures, policy violations) — are return-value signals, documented in the interface spec. Never raise exceptions for expected conditions.
- **Unexpected failures** — precondition violations, filesystem errors, state corruption — are exceptions or undefined behavior, not documented in interface specs. Preconditions are caller obligations, not failure signals; an implementation may document a violation response if useful, but none is required. An HLS assumption is a precondition, never a failure condition: it appears under **Preconditions** and produces no Failure Handling clause.
- **Concrete strings** (error messages, fallback text) are pinned in implementation specs, not interface specs; wording is stated only when a test must assert it. An interface may pin the **absence** of error detail when a test must assert it (Non-Concerns), and may defer a detail with "pinned in the implementation spec" only when the named implementation LLS actually states it — an unbacked deferral is an error.
- **Terminology:** distinguish termination, channel failure, and run failure (see `low_level_spec.md`).

Every HLS statement — guarantee, ordering constraint, or failure condition — is represented in the LLS: as a precondition, postcondition, invariant, term definition, or return-value signal. An HLS fact the LLS cannot express is a conversion error; a fact implied but never stated is a traceability gap.

## Configuration Ownership

Configuration comes in two kinds, each in exactly one place, decided by **who supplies it**: the client of the interface, or the assembler.

- **Interface-owned configuration** — supplied by the interface's client (the HLS Contract's **Inputs** block, items marked "configured:"): typed in the Interface LLS Data Types with a descriptive name (`InventoryConfig`, not `Config`), passed to the implementation as a single `config` parameter.
- **Implementation-owned configuration** — capability bundling known only to the assembler: becomes the implementation class's `__init__` parameters in the Implementation LLS Data Types (e.g., `fulfillment_impl.__init__(self, inventory: Inventory, pricing: Pricing)`); in the HLS this is the implementation's `imports:` front matter and `[external]` Deltas lines.
- **No capabilities to bundle:** no `__init__` is declared.

## LLS Structure

Per `low_level_spec.md`: each LLS file declares `# Interface LLS: <name>` sections (Data Types, Component-Provided Operations, Invariants) and, when an implementation HLS exists, `# Implementation LLS: <name>` sections (Data Types, Composition, Behavioral Description, Invariants, Non-Concerns). Subsections use `##`; operations use `### `name``. The skeleton is a shape, never content — do not write it into the file. Term definitions (cross-cutting rules such as stubbing) go between Data Types and Operations. Non-Concerns is optional.

## Operation Documentation Template

```
### `operation_name`

    def operation_name(self, param: Type) -> ReturnType

**Purpose:** [What the operation does.]
**Preconditions:** [Conditions that must be true before calling.]
**Postconditions:** [State changes, return semantics, ordering, routing, guarantees — declarative.]
**Failure Handling:** [Error conditions and signaling; expected failures as return values, unexpected failures not documented.]
**HLS Justification:** [Brief phrase traceable to the HLS closure.]
```

## Step-by-Step Process

### Interface LLS

1. Identify component-provided operations from the HLS Contract's **Operations** block.
2. Define type aliases for concepts owned by this interface (from the Terms section and the Contract's Inputs/Guarantees/Assumptions blocks); type the interface-owned configuration; declare the interface as a `Protocol` class whose methods are the operations — all in one Data Types code block. An HLS-owned term never in the **Operations** block is a type alias, not an operation (a `Subgraph` term yields a `Subgraph` type, never a `get_subgraph` operation).
3. Import types as needed; list every dependency in the dependency comment (per Conversion Reading; remove spurious entries).
4. Resolve the HLS's withholdings (per Core Rule 4); check the implementation's `[refines]` Deltas lines for the withheld precision it pins.
5. For each operation, collect ALL rules from across the HLS closure: preconditions from Assumptions and Inputs; postconditions, routing, and ordering from Guarantees and named blocks; error handling from their failure semantics.
6. Document each operation with the template; add term definitions for cross-cutting rules; define global invariants.

### Implementation LLS (only if an implementation HLS exists)

1. Identify dependencies: the fulfilled interface (from `fulfills:`), other interfaces in `imports:` / `terms (from X):`, plus any component named in prose; list them in the dependency comment (interfaces only).
2. Declare `class FooImpl(Foo): ...` in Data Types.
3. Express configuration as the implementation class's `__init__` in Data Types: bundled capabilities as parameters, an interface-owned config type as a single `config` parameter, none as no `__init__`.
4. For assembler implementations, list the wired concrete implementations in a Composition section (names only).
5. State which operations it implements; describe responsibilities declaratively. The implementation HLS's Deltas are the semantic source — untagged behavior lines and tagged (`[ordering]`, `[boundary]`, `[state]`, `[external]`, `[failure]`) lines map onto the Behavioral Description, Invariants, and Error Handling; `[refines]` lines pin concrete conditions and values.
6. Define internal behavioral invariants.
7. List Non-Concerns implementers might otherwise worry about (optional).

## Validation Checklist

- [ ] Every LLS statement traces to the HLS's effective constraint set (own lines + closure)
- [ ] LLS dependency comment (first line) lists only LLS files; no HLS or implementation LLS dependencies
- [ ] Dependency comment mirrors the HLS front matter plus any component named in prose; every entry imported or referenced; no spurious entries
- [ ] Type-level LLS imports stay inside the converted HLS's closure; outside dependencies require an HLS amendment first
- [ ] Each interface defines its own types in its own Data Types; owned types imported elsewhere, never redefined
- [ ] HLS withholdings resolved: opaque → type variable or pass-through type; open → concrete type; hook → concrete condition or signal

- [ ] Implementation HLS refinements (`terms (refined):` names; `[refines]` lines) made concrete in the implementation LLS
- [ ] Data Types is one Python code block (imports, aliases, classes; Protocol last) followed by prose, no comments; every type alias is `X: TypeAlias = ...` (no bare `X = ...` type assignments); descriptive names (never generic `Message`/`Result`/`Status`/`Data`)
- [ ] Mutually exclusive outcomes encoded as discriminated unions with `Literal` discriminators
- [ ] Pass-through values use type variables with documented roles; interface specs never resolve them in prose
- [ ] Interface LLS declares the Protocol class in Data Types (even when no implementation is in the closure); every operation signature is a method of it, never a free function
- [ ] Every operation derives from the HLS **Operations** block or a named block describing client-invoked behaviors (e.g., **File operations**, **Verification**, **Termination**); each has a brief HLS justification and is self-contained
- [ ] Every HLS guarantee, ordering constraint, and invariant is represented in the LLS (precondition, postcondition, invariant, term definition, or failure-handling note); no HLS fact dropped as implied
- [ ] Named Contract blocks converted: each block's facts land in exactly one LLS location, never duplicated

- [ ] No operations for internal behavior (propagation, persistence, validation); no monolithic read/write operations
- [ ] Error handling only for explicit HLS failure conditions; expected failures are return-value signals; unexpected failures (precondition violations) not in interface specs; no Failure Handling clause for an HLS assumption (assumptions are Preconditions only)
- [ ] Concrete strings pinned in implementation specs; wording stated only when a test must assert it
- [ ] Interface deferrals ("pinned in the implementation spec") backed by the named implementation LLS; error-detail-absence pins only when a test must assert them
- [ ] Subsections use `##` headings (Data Types, Component-Provided Operations, Invariants, ...); operations use `### `name``; no skeleton text in the file
- [ ] Implementation LLS exists only if an implementation HLS exists (`fulfills:` an interface)
- [ ] Implementation class declared as `class FooImpl(Foo): ...`; name matches the interface only when exactly one implementation will ever exist; abstract bases named distinctly (`BaseFoo`)
- [ ] Implementation sections never mention "client" (reference the interface contract instead)
- [ ] Configuration expressed as `__init__` parameters on the implementation class (bundled capabilities; single `config` for an interface-owned type; none absent); interface-owned config typed in Interface LLS Data Types; no Config section
- [ ] Postconditions describe outcomes, not mechanisms; external-system interactions excepted
- [ ] Non-Concerns (optional) records pinned choices with justifications
- [ ] LLS is detailed enough to write passing tests
