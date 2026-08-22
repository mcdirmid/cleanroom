# Low-Level Specification Guide

## Purpose

An LLS specifies *how* a component's interface and implementation are realized: concrete types, signatures, preconditions, postconditions, and failure signals — detailed enough that tests and an implementation can be written from it independently and pass when both conform; the HLS elaborated, never replaced.

## Structure

Every LLS file declares one or more sections, in the order below. An implementation LLS exists only when the HLS defines an implementation for the interface.

```
1. [Interface LLS: name]                  — repeatable
   1.1 Data Types                         — types, type variables, the Protocol class
   1.2 Component-Provided Operations      — each operation, fully self-contained
   1.3 Invariants
2. [Implementation LLS: name]             — only if the HLS defines one
   2.1 Data Types                         — imports, `class FooImpl(Foo): ...` with `__init__` expressing configuration
   2.2 Composition                        — concrete implementations an assembler wires together
   2.3 Behavioral Description             — how the implementation fulfills the contract
   2.4 Invariants
   2.5 Non-Concerns
```

Term definitions (cross-cutting behavioral rules) appear between Data Types and Component-Provided Operations. Non-Concerns is optional in both interfaces and implementations.

### Naming

- Section headings are exactly `# Interface LLS: <name>` and `# Implementation LLS: <name>`.
- Subsections use `##`: `## Data Types`, `## Component-Provided Operations`, `## Invariants`, `## Non-Concerns` (implementation LLS: `## Composition`, `## Behavioral Description`); operations use `### `name``. Never write the structure skeleton into the file — it is a shape, not content.
- The implementation name matches the interface name only when the interface is single-implementation by nature (`pricing` / `pricing_impl`) — not merely because one implementation exists today. Multi-implementation interfaces use distinct identifying names (`csv_inventory_impl`, `memory_inventory_impl`).
- The implementation class is `class FooImpl(Foo): ...` (in the implementation's Data Types); multi-implementation classes use a distinguishing prefix (`CsvInventoryImpl(InventoryImpl)`).
- A file may declare any number of interface and implementation sections.
- Filenames use underscores except the `-low` / `-high` suffix; no hyphens elsewhere.

## Dependency Rules

- LLS files depend only on other LLS files — never HLS files, never implementation LLS files. Dependencies are expressed through interfaces: an implementation depends on the interface it implements and on any other interfaces whose types it uses. An imported type counts as used when it appears in a signature, in prose, or as part of the fulfilled contract. A Composition section may name concrete implementations without making them dependencies.
- The markdown comment at the top of the file (its first line) lists the specs to read alongside it. Every entry must correspond to an actual import or direct reference; spurious entries are removed. This comment is the LLS's only front matter: no `terms (owned):` or `terms (from X):` section. Owned concepts are type aliases in Data Types; used concepts are imports from those specs' LLS files, listed in the comment (see `high_to_low.md`).
- Each LLS is a stand-alone document; readers use it without the HLS. The HLS/LLS boundary is crossed only during conversion (see `high_to_low.md`).
- **Traceability.** Every LLS statement traces to the HLS; the LLS cannot add behavior not implied by it. If you cannot answer "where does the HLS say this?", remove it. Implementation details may be added only as necessary to fulfill HLS guarantees.

## Terminology: Termination, Channel Failure, Run Failure

Termination and failure are distinct signals; do not use "failure" ambiguously.

- **Termination** — a channel action that ends the session (e.g., a termination channel invoked correctly). Termination is terminal: a session that produces a termination signal produces no further channel results. A successful termination signal carries a termination result; a failure termination signal carries a value describing the failure.
- **Channel failure** — a failed channel action (invalid arguments, a policy violation, or a termination channel invoked incorrectly). A channel failure is not a termination: the session continues, and the failure value guides the run's next move.
- **Run failure** — a run-level failure of the request itself (service failure, malformed response, exceeded iteration limit), signaled by the run's failure result.

A run recovers from a channel failure by continuing: the failure value is appended to the request history and the request makes its next move. Recovery has no stateful effect on the session — no session reset, no history clearing, no new service session. Specs must state which kind of failure they mean.

## Writing Rules

### Data Types

- **One code block.** The Data Types section opens with exactly one Python code block containing all imports, type aliases, and classes — the interface's Protocol class last, declaring only its fresh methods (those not inherited from a base class). Type aliases are declared with `TypeAlias` from `typing` (`UserId: TypeAlias = int`); string constants are plain assignments. No comments in code blocks; prose explaining each type follows the block, never interleaved between code blocks.
- **Naming.** Descriptive, domain-specific names; never generic `Message`, `Result`, `Status`, `Data` (use `NodeMessage`, `CleanResult`, `HistoryEntry`). Distinct purposes get distinct names.
- **Type variables.** Prefer type variables over `Any` for values that pass through unchanged; use `Any` only when truly unconstrained. Each type variable has one well-defined, documented role; distinct roles get distinct names; reuse imported type variables for the same role. Interface specs never resolve a type variable to a concrete type — including in prose (`Outcome[T]`, not `Outcome[str]`); the implementation spec resolves it.
- **Discriminated unions.** Encode mutually exclusive outcomes as discriminated unions with `Literal` discriminators; never approximate variants with a dataclass of optional fields.
- **Protocol classes.** Every interface declares its `Protocol` class whose methods are the operations — never free functions, even when no implementation exists yet. A Protocol may be a dataclass combining static data fields with interface methods.
- **Imports and shared ownership.** Define a type once, in the interface that owns the concept; all other specs import it, never redefine it. Import each type from its owner's LLS — importing through a re-exporting interface is an error. Use the dependency's types directly; define a new type only when no existing type is workable, adding a bridging type to the dependency spec. Adaptation between interfaces' types happens in implementation specs, not interface specs. Pre-constrained interfaces are referenced, not re-documented.

### Operations

Each operation is documented under a `### `operation_name`` heading and is fully self-contained: preconditions, postconditions, failure handling, ordering, and routing rules all appear under the operation, and may reference term definitions by name.

- **Granularity.** Define operations at the level of individual actions; do not force clients to read or write more than they need.
- **Boundaries.** When operation boundaries (atomicity, all-or-nothing) are client-visible, state them as postcondition guarantees ("Signals failure for the entire operation if any step fails").
- **What not to expose.** Internal mechanics, persistence, validation, and bookkeeping are postconditions or invariants, not operations. "Client provides" → imported at initialization; "client initiates" → component-provided operation.
- **Template:**

```markdown
### `operation_name`

    def operation_name(self, param: Type) -> ReturnType

**Purpose:** [What the operation does.]

**Preconditions:** [What must be true before calling.]

**Postconditions:** [State changes, return semantics, ordering, routing, guarantees — declarative language.]

**Failure Handling:** [Error conditions and signals.]

**HLS Justification:** [Brief phrase consistent with the HLS.]
```

### Failure Handling

- **Signals.** Document the code-level signal (return value, `None`, `Result`, exception) explicitly in the signature or text.
- **Expected failures** — conditions the contract handles during normal use (policy violations, validation failures) — are return-value signals, documented in the interface spec. Never raise exceptions for expected conditions.
- **Unexpected failures** — precondition violations, filesystem errors, state corruption — are exceptions or undefined behavior, not documented in interface specs. If an interface documents one for reader clarity, state only the constraint; never describe how the interface handles the violation. Preconditions are caller obligations, not failure signals. The implementation may raise, return, or behave otherwise — no exception is required; if it documents its violation response, that lives in the implementation spec (e.g., `inventory_impl` documents `ValueError` for unknown SKUs).
- **Concrete strings** (error messages, fallback text) are pinned in implementation specs, not interface specs. Interfaces document the signal type, the failure categories, and the state preserved on failure. Error-message wording is stated only when a test must assert it — and only in the implementation spec; otherwise not at all (not even as "unspecified").
- **Dependency failures.** Honor and re-export the dependency's failure signals; do not suppress them or convert a uniform return-signal contract into exceptions. Unexpected dependency errors are exceptions raised by the dependency's implementation; the current interface may catch and re-export them as a failure signal, optionally.

### Term Definitions

When a cross-cutting behavioral rule (stubbing semantics, etc.) applies to multiple operations and cannot be factored into a shared interface, define it as a term and have each operation reference it by name: short definitions appear as inline prose before `## Data Types`; longer ones use a heading (e.g., `## Stubbing Semantics (term definition)`) between Data Types and Operations.

### Implementation LLS

- Produce an implementation LLS only when the HLS defines an implementation for the interface; otherwise the interface LLS stands alone. The implementation implements the Protocol class defined in the corresponding interface LLS.
- **Data Types.** Import the interface's Protocol and types; declare `class FooImpl(Foo): ...` as a code block. Concrete error-message strings and result structures belong here, not in the interface spec.
- **Configuration.** There is no Config section: configuration is expressed as the implementation class's `__init__` in Data Types. Implementation-owned configuration — capability bundling supplied by the assembler — becomes `__init__` parameters (e.g., `fulfillment_impl.__init__(self, inventory: Inventory, pricing: Pricing)`). Interface-owned configuration — domain data the interface's client supplies — is typed in the Interface LLS Data Types with a descriptive name (`InventoryConfig`, never `Config`) and passed as a single `config` parameter. No configuration: no `__init__` is declared.
- **Composition.** For assembler implementations, name the concrete implementations wired together (names only — not dependencies; the dependency comment still lists interfaces only).
- **No "client" in implementation sections.** Describe internal behavior and assembler wiring, never interface clients. Reference the interface contract instead ("Configured with SKU list and reorder thresholds (per the `inventory` interface contract)").
- **Behavioral Description.** State outcomes, not mechanisms ("Returns `X` when..."; avoid "iterates over..."). Exception: interactions with an external system may be described in terms of the external protocol — observable behavior, not internal bookkeeping. Reference imported interfaces by name rather than re-documenting their semantics. Take interface preconditions as given; do not re-document them.
- **Invariants.** Component-wide guarantees that hold across all operations.
- **Non-Concerns.** Record choices pinned to resolve HLS non-concerns, with a one-line justification, as `- **[Aspect]:** [Choice or assumption] — [Justification].` Common aspects: ordering, algorithm choice, representation, unhandled failure modes, caller constraints. Optional in both interfaces and implementations.

### HLS Justification

Keep to one sentence or a brief phrase, consistent with the HLS — need not quote it directly. When an LLS is reviewed without the HLS, accept justifications at face value — they record what the HLS established; no re-verification is required. Do not use "definition" in place of "interface" or "implementation".

## Example Patterns

### Interface LLS (shape of `inventory-low.md`)

```markdown
# Interface LLS: inventory

## Data Types

    from typing import TypeAlias, Protocol

    Sku: TypeAlias = str
    Quantity: TypeAlias = int

    class Inventory(Protocol):
        def get_stock(self, sku: Sku) -> Quantity: ...
        def add_stock(self, sku: Sku, quantity: Quantity) -> None: ...
        def remove_stock(self, sku: Sku) -> None: ...

## Component-Provided Operations

### `get_stock`

    def get_stock(self, sku: Sku) -> Quantity

**Purpose:** Retrieve the current stock level for a given SKU.

**Preconditions:** `sku` must exist in the system.

**Postconditions:** Provides the current stock level (zero if none).

**HLS Justification:** "The client may read the stock level for an SKU."

## Invariants

- Read, write, and delete operations are atomic per SKU.
```

### Implementation LLS (shape of `csv_inventory_impl-low.md`)

```markdown
# Implementation LLS: csv_inventory_impl

## Data Types

    from inventory import Inventory, Sku, Quantity
    from pricing import Pricing

    class CsvInventoryImpl(Inventory):
        def __init__(self, pricing: Pricing): ...

## Behavioral Description

`CsvInventoryImpl` fulfills the `Inventory` Protocol (see `inventory-low.md`):
- **`get_stock`** — Returns the SKU's current stock level from the SKU directory's stock file.
- **`add_stock`** — Appends the given quantity to the SKU's stock level and persists the result.

## Invariants

- Storage operations are atomic per SKU.

## Non-Concerns

- **Stock file naming:** Pinned to `state.json` in the SKU directory (the interface leaves the filename open).
```

### Operation with early termination and failure (shape of a request LLS)

```markdown
### `run_request`

    def run_request(self, payload: str, channels: list[ChannelSpec], handler: Handler[T], sink: EventSink | None = None) -> RequestResult[T]

**Purpose:** Run the request. Completes when the service produces a final response, a channel terminates the session, or a failure occurs.

**Preconditions:**
- `payload` is a non-empty string
- `channels` are valid channel definitions
- `handler` handles all channels in `channels`

**Postconditions:**
- Returns `FinalResult` on normal completion
- Returns `Termination[T]` with the value from `CompleteWithSuccess` (a `SuccessResult`)
- Returns `Failure` with the request history on error; state unchanged
- Channel failures (`ChannelError[T]`) are appended to the request history and the run continues

**Failure Handling:**
- Returns `Failure` (run failure) on service failure, malformed response, or exceeded iteration limit; state unchanged

**HLS Justification:** "The client may request a run with a user payload and available channels."
```

## Validation Checklist

### Structure and Naming

- [ ] Interface sections are `# Interface LLS: <name>`; implementation sections are `# Implementation LLS: <name>`
- [ ] Implementation LLS exists only if the HLS defines one; the interface LLS stands alone otherwise
- [ ] Implementation name matches the interface when single-implementation by nature; multi-implementation interfaces use distinct names
- [ ] Implementation classes are `class FooImpl(Foo): ...` (extending the Protocol); multi-implementation classes use distinguishing prefixes
- [ ] Sections ordered per the Structure skeleton; term definitions between Data Types and Operations
- [ ] Filenames use underscores except the `-low` / `-high` suffix

### Dependencies

- [ ] No LLS references an HLS file
- [ ] No LLS depends on an implementation LLS; dependency comments list interfaces only
- [ ] Every dependency-comment entry is actually imported or referenced (a direct reference suffices; no spurious entries)
- [ ] A spec uses its dependency's types directly rather than defining equivalent local types; adaptation happens in implementation specs

### Types

- [ ] Types owned once, imported elsewhere (no duplicate definitions)
- [ ] Descriptive domain-specific names (never generic `Message` / `Result` / `Status` / `Data`)
- [ ] Type aliases declared with `TypeAlias` from `typing`; constants are plain assignments
- [ ] Data Types is one Python code block (imports, aliases, classes) followed by prose; no comments in code blocks
- [ ] Mutually exclusive outcomes encoded as discriminated unions with `Literal` discriminators
- [ ] Pass-through values use type variables; roles documented; distinct roles get distinct names
- [ ] Interface specs never resolve type variables to concrete types, including in prose
- [ ] Every interface declares its Protocol class in Data Types (even without an implementation); operations are methods, never free functions

### Operations

- [ ] Each operation is self-contained (preconditions, postconditions, failure handling, ordering, routing)
- [ ] No operations for internal behavior (propagation, persistence, validation)
- [ ] No monolithic read/write operations; granularity at individual actions
- [ ] Atomicity and operation boundaries stated as postcondition guarantees
- [ ] Each operation has a brief HLS justification (consistent with the HLS, not necessarily a direct quote)
- [ ] Postconditions describe outcomes, not mechanisms

### Failure Handling

- [ ] Expected failures are return-value signals, documented in interface specs; no exceptions for expected conditions
- [ ] Unexpected failures (precondition violations, filesystem errors) not documented in interface specs; preconditions are caller obligations only, and no exception is required
- [ ] Concrete strings (error messages, fallback text) are pinned in implementation specs; error-message wording is stated only when a test must assert it
- [ ] Dependency failure signals are honored; uniform return-signal contracts are not converted to exceptions
- [ ] "Failure" terminology distinguishes termination / channel failure / run failure

### Implementation

- [ ] Configuration expressed as the implementation class's `__init__`: bundled capabilities as parameters, an interface-owned config type as a single `config` parameter, none as no `__init__`; no Config section
- [ ] Assembler implementations list composed concrete implementations in a Composition section (names only — not dependencies)
- [ ] Implementation sections never mention "client" (reference the interface contract instead)
- [ ] Interface-owned config typed in Interface LLS Data Types with descriptive names
- [ ] Behavioral Description states outcomes; external-system interactions excepted; imported interfaces referenced by name
- [ ] Implementation takes interface preconditions as given and does not re-document them
- [ ] Non-Concerns record pinned choices with justifications (optional)

### Completeness

- [ ] LLS is detailed enough to write passing tests
- [ ] Multiple interface or implementation LLS sections may coexist in a single file
