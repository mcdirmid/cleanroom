# Guide: High-Level Specifications (HLS)

## Purpose

An HLS states what a component does — concepts, behaviors, contracts — in natural language, with no implementation details. It is the single source of truth for design, implementation, and tests: complete, unambiguous, testable.

## The Five Pillars

1. **Natural language, not DSL.** Ordinary English; no formal grammar, schema, or invented vocabulary beyond naming. Structure removes duplication, never replaces prose.
2. **Declarative.** Constraints, invariants, and observable relationships — never procedures. No internal steps, no sequencing except observable ordering, no mechanisms.
3. **One fact per line.** Every line is a complete, self-contained fact stating exactly one concern.
4. **Extreme separation of concerns.** One component per file; one concern per section; one fact per line; deltas only.
5. **Terms defined once.** Each term is owned by exactly one interface; other specs reference it by name and never re-define it.

## The Reading Model

An LLM reads a spec as a token stream, with no memory of prior reads and no guarantee that the whole context is present.

- **Self-contained lines.** A line before a truncation cut must remain a complete, correct fact. Lists survive; table rows without their header do not.
- **Lists over tables.** Tables only for genuinely rectangular matrices where the grid is the information (e.g., logger events × fields). Heterogeneous facts (some rows conditional, some effects, some neither) go in lists, with shared effects factored once; cells must not depend on their header to be understood.
- **No grammar beyond English.** Ordinary English; `->` may abbreviate "if...then" (see Formatting). A rule inexpressible in ordinary English does not belong in an HLS.

## Declarative Writing

- **Constraints, not steps.** "The new record is persisted before the old record is deleted" is an ordering constraint; "the component persists the new record, then deletes the old" is a procedure. Only the former is declarative.
- **Sequencing language only for observable ordering.** "First/then/next" appear only for orderings clients or downstream components can observe — the order of visible effects, persistence, or delivery — never for internal steps.
- **No mechanism.** No "iterates", "builds", "calls", "stores in a hash map". State what clients can rely on and what state changes are visible.
- **The observability test.** For every sentence ask: "Can a client or downstream component observe this?" If only the implementation can, cut it or restate it as an observable constraint.
- **Failure is a semantic statement.** "Signals failure, leaving the queue unchanged and halting the operation" — never "raises an error", never "returns an error code".
- **Declarative is not vague.** "or custom conditions hold" and "at most once per run" are declarative; precision is independent of relationship.

## Separation of Concerns

The HLS separates design concerns at a coarse grain — and, decisively, the interface's usage contract from the implementation's specifics — in different specs. The format enforces this at three levels.

- **File level.** One component per file. An interface spec contains no implementation content; an implementation spec contains no interface content beyond what it fulfills. The split is enforced by the file system, not by prose discipline.
- **Naming.** A file whose name contains `impl` is an implementation spec; every other file is an interface spec. `dag_storage-high.md` is an interface; its implementation would be `dag_storage_impl-high.md`.
- **Section level.** Each fixed section owns exactly one concern; mixing is an error. (See Document Structure for the section inventory.)
- **Line level.** Each line states exactly one concern. A line mixing a guarantee with an assumption, or behavior with mechanism, is an error.

## Term Ownership

### Ownership rules

- Every term is owned by exactly one interface — the one that defines it in its Owned definitions section.
- A spec that uses a term it does not own lists it in front matter: `terms (from order_service): held, receipt`.
- Re-defining a term owned elsewhere is an error; using a term without listing it is an error.
- **There is no global glossary.** Readers load the transitive closure of referenced specs; the owning definition is always in it. `terms (from ...)` lines are pointers (and lint anchors), not duplicates.

### Use-level definitions (interfaces)

An interface defines a term only as precisely as users need, deliberately withholding the rest — and saying so, in one of three ways:

- **Opaque** — meaning withheld: "an opaque value; passes through unchanged; the component does not inspect, transform, or interpret it."
- **Open** — content withheld: "the exact content is unspecified."
- **Hook** — conditions withheld: "or custom conditions hold"; the trigger is the interface's business.

Definition rewrites preserve all testable content — direction, cardinality, ordering, identity. Removing any is allowed only as a marked withholding (opaque/open/hook) with its consequence pinned. Precision loss is a regression, not a fix. The `->` shorthand is allowed; removing it or its fact is a precision loss, not a grammar fix.

Consumers take such terms for granted: they know *that* a held order blocks fulfillment, not *what* makes it held.

An interface defines terms *for* its consumers: a term may be unused in the owning file's own body yet required by specs that list it in `terms (from X):` — that is use. Do not delete a term (or its definition) because the file itself never mentions it.

### Concrete definitions (implementations)

An implementation refines a term it must make concrete — instantiating a hook, filling open content, identifying an opaque role — declared in front matter (`terms (refined): held -> payment pending beyond the hold window or the fraud check flagged the order`) and detailed in the implementation's Deltas.

Refinement rules:

- A refinement **narrows**: it instantiates, fills, or identifies; it never contradicts the interface definition.
- It exists only when implementing requires the precision the interface withheld — no precision, no refinement.
- It is **local**: it binds in the implementation and its dependents (via their own `terms (from ...)` lines); it never propagates back to the interface.

## Constraint Inheritance

A spec's effective constraint set is its own lines plus the transitive closure of the constraints of every spec it depends on (`imports:`, `fulfills:`). Inherited constraints are **in effect without being restated**: the delta is the difference between the effective set and the inherited set.

- **Restating an inherited constraint is an error** — the constraint appears in exactly one spec; a duplicate creates two sources of truth that can drift apart.
- **Dependencies' assumptions are inherited.** A dependent that must establish a dependency's precondition says so only when it adds precision.
- **Non-concerns propagate as "not guaranteed".** A dependent may not rely on behavior a dependency declares out of scope.
- **Narrowing is allowed; contradicting is not.** "At most once per call" may become "exactly once per call"; the opposite may not be stated.

## Grounding

Meaning may be withheld; observability never is. Every vague term anchors to an observable consequence, a refinement site, and eventually a test.

- **Every withholding names what is pinned.** Opaque: the pass-through path (enters, exits, unchanged). Open: the delivery and routing (who receives it, when). Hook: the behavior it controls (held orders are not fulfilled until released). A vague term with no pinned consequence is ungrounded.
- **Every owned term is used or refined somewhere in the closure** — its own body, a consumer's `terms (from X):`, or a refinement site; absence of use within the file alone is not free-floating. When in doubt, do not delete the term.
- **Every guarantee is testable from the specs alone** — the AI Action Test at line level, test-suite reachability at contract level.
- **Boundaries to the un-specified are declared.** An external service or human operator is grounded by declaration; the integration point is pinned in the implementation spec.
- **Ungrounded:** a vague term with no withholding marker and no observable consequence; a hook with no refinement site; a term unused and unrefined; a guarantee no test could check; a constraint with no trigger, no state effect, and no failure semantics.

## Document Structure

### Interface vs. implementation

- One component can have two specs, in separate files: an interface (what clients rely on) and an implementation (how a concrete system fulfills it).
- Interface content: Purpose, Owned definitions, Observable dataflow, Contract, Non-concerns. Implementation content: Deltas beyond the interface contract (Behavior, Operation Boundaries, Ordering, State Management, External Dependencies, Error Handling, Refined terms), Non-concerns.
- An interface spec never contains implementation content — no mechanism, no internal state, no refinements, no `fulfills:`.
- An implementation spec never contains interface content — no `## Contract`, no owned definitions, no client language; it fulfills exactly one interface.
- Editing preserves the kind: never convert an interface spec into an implementation spec, or vice versa; a spec cannot fulfill itself.
- A spec that declares `fulfills:` is an implementation of that interface, never a restatement of it.

### Interface spec

```
# <name>

imports: <dep> (what it provides)              # optional
terms (from <dep>): ...                        # optional
terms (owned): ...                             # optional

## Purpose

<one or two sentences: what the component provides to clients>

## Owned definitions          # present iff terms (owned)

- <term>: <use-level definition>
- ...

## Observable dataflow

<short prose: what enters, what exits, and ordering.
 Each line states one change; preservation lines ("unchanged", "as declared",
 "as stored", "declared/recorded X") are prohibited — no mention means no
 change. Dataflow lines only; Contract guarantees may assert fidelity.
 Opaque values and open contents are named here.
 Persistence, termination, and atomicity commitments go in the Contract's
 component guarantees — do not repeat them here.>

## Contract

**The client configures the component with:**    # optional
- <one per line>

**For each <operation>, the client provides:**    # optional
- <one per line>

**The client may:**
- <one per line>

**The component guarantees:**
- <one fact per line; factor shared state effects>

**The component assumes:**
- <one per line>

## Non-concerns

- <one per line>
```

### Implementation spec

```
# <name>

fulfills: <interface>
imports: <dep> (purpose), <dep> (purpose)
terms (from <dep>): ...
terms (refined): <term> -> <concrete definition>

## Deltas beyond the <interface> contract

### Behavior               # optional — present only when there is a delta
- <one fact per line>

### Operation Boundaries   # optional
- ...

### Ordering               # optional
- ...

### State Management       # optional
- ...

### External Dependencies  # optional
- ...

### Error Handling         # optional
- ...

### Refined terms          # present iff terms (refined)
- <term> -> <concrete definition>

## Non-concerns

- <one per line>
```

## Writing Rules

### Language

- Active voice for component actions; passive for between-operation state.
- "iff" for meaningful equivalences; "must" for constraints; "may" for options; "when" for timing; "if" for conditions.
- **"Returns" is prohibited** — "provides", "signals", "delegates".
- **"Signals failure" includes state semantics** — "signals failure, leaving the queue unchanged and halting the operation", never "returns an error".
- No pseudo-code identifiers: code tokens — type names, literals (`item_id`, `True`), camelCase/snake_case variables that are not interface/component names. Outcomes are "continue", "complete the request", "reject the request", "invalid input"; a record ID; flags are "true"/"false"; absence is "none". Interface and component names (`order_service`, `dispatcher`) are exempt.
- Natural language is not pseudo-code: ordinary English words that happen to coincide with type names ("string", "number", "integer") are allowed — "a string addressed to a node", "the number of pending messages". Ordinary-English placeholders (`A`, `B`, "one node") are also fine; removing them must not remove meaning.
- The client appears only in Interface sections; implementation sections never mention "client".
- Every sentence passes the **AI Action Test**: "Can an LLM derive an interface usage constraint, an implementation behavior constraint, or a dependency requirement from this sentence? If not, remove it."

### Formatting

- One fact per bullet; subject first: `Snapshot = the committed state at call time`, not "The implementation snapshots the state...".
- Factor shared effects once: a failure clause shared by several triggers is written once, with the triggers as a sub-list beneath it.
- `->` abbreviates "if...then": `target outside the service area -> failure, halt, pending orders unchanged`.
- Front matter: `key: value` lines, one per line, interface names in backticks.
- No restating: an implementation does not restate the fulfilled interface; a consumer does not restate owned definitions.
- No mixing: one concern per line, per section, per file.

### Conformance editing

- Change only non-conforming content; leave conformant lines untouched.
- A rewrite preserving every fact is not a change; if the file already conforms, report no change.
- The claimed change must appear in the diff — verify output against input before reporting success.
- Walk the Validation Checklist against the edited file; every item must pass before succeeding.

## Validation Checklist

- [ ] Natural language throughout; no grammar invented beyond `->` shorthand
- [ ] Declarative: no internal steps, no mechanism, no sequencing except observable ordering constraints
- [ ] Every sentence passes the observability test (a client or downstream component can observe it)
- [ ] One fact per line; every line self-contained (survives truncation); one concern per line
- [ ] No tables except rectangular matrices with self-contained cells
- [ ] Every term used is owned or listed in `terms (from ...)`
- [ ] No term re-defined outside its owner; refinements narrow, never contradict
- [ ] Refinements declared in front matter and detailed in Deltas
- [ ] Opaque / open / hook withholdings explicit in interface definitions
- [ ] Implementation lists deltas only; does not restate the fulfilled contract
- [ ] No inherited constraint restated; effective constraint set = own lines + closure
- [ ] Dependency assumptions inherited; narrowing allowed, contradicting not
- [ ] Implementation concern sub-sections present only when a delta exists
- [ ] Every vague term (opaque/open/hook) names what is pinned: consequence, dataflow, or refinement site
- [ ] Every hook has a refinement site in the closure; every owned term is used or refined somewhere in the closure (absence of use within the file alone is not free-floating)
- [ ] Refinement chains terminate (strict narrowing, no cycles)
- [ ] Every guarantee testable from the specs alone; no guarantee about unobservable state
- [ ] One component per file; interface and implementation in separate specs
- [ ] File kind matches its name: no "impl" in the name → interface spec (no fulfills, no Deltas); "impl" in the name → implementation spec (fulfills + Deltas, no Contract)
- [ ] No types, signatures, or data structures (an implementation concern, not an HLS one)
- [ ] No concern mixing: guarantee in Assumptions, behavior in definitions, client action in an implementation spec — all errors
- [ ] Language rules: no "returns"; failure semantics stated; iff/must/may/when/if used precisely; no pseudo-code identifiers (code tokens only); client only in Interface sections
- [ ] AI Action Test passed for every sentence
- [ ] Observable dataflow specified: enters, exits, ordering
- [ ] No persistence/termination/atomicity fact duplicated between Observable dataflow and Contract guarantees — each fact appears once, in exactly one section
- [ ] Operation boundaries (atomicity) in the interface when client-visible
- [ ] Configuration vs per-operation inputs distinguished; assembler wiring confined to the implementation spec
- [ ] Non-concerns list only aspects that do not affect correctness or observable behavior
- [ ] Definition rewrites preserve all testable content; removals are marked withholdings with pinned consequences
- [ ] Dataflow lines each state one change; preservation lines ("unchanged", "as declared", "as stored") are absent — no mention means no change
- [ ] Only non-conforming content changed; every claimed change appears in the diff

## Common Pitfalls

Each pitfall is a self-contained item: Pitfall — Example — Fix.

- DSL drift — "atomicity(per-call)" — Say "atomic per call".
- Procedure as guarantee — "The component first validates, then executes, then writes." — "Execution occurs only when the request is valid; the result is observable only after execution completes."
- Mechanism — "It builds an index of all active orders before answering." — "Queries provide a consistent view of all active orders."
- Table for heterogeneous facts — guarantee rows with "—" filler cells — Convert to one-fact-per-line list.
- Header-dependent fragment — "| target outside service area | failure | halt" without the header — Self-contained line.
- Re-defining owned terms — *held* described in three specs — `terms (from order_service): held`.
- Refinement contradicting owner — implementation defines *receipt* differently than `order_service` — Narrow only; align.
- Vagueness without marking — "the value is passed along" — "Opaque; passes through unchanged".
- Restating parent contract — implementation repeats interface guarantees — Deltas only.
- Concern mixing — a guarantee stated inside Assumes; behavior inside Owned definitions — Move each fact to its owning section.
- "Returns" — "Returns true when in stock" — "Signals availability when in stock".
- Failure without state — "Signals failure" — "Signals failure, leaving messages unchanged".
- Pseudo-code identifiers — `item_id`, `True` — "record ID", "true".
- Unmarked hook — "held when flagged" — "held when payment is pending or custom conditions hold".
- Free-floating vagueness — "results are provided in a reasonable manner" — Mark opaque/open/hook and pin the observable consequence.
- Dangling hook — "custom conditions hold" with no refinement anywhere in the closure — Add a refinement site or declare the hook intentionally unrefined.
- Restated inherited constraint — repeating a dependency's guarantee in the dependent — Delete it; the constraint is already in the closure.
- Contradicting a dependency — dependent guarantees "may repeat" where the dependency says "at most once per call" — Align, or narrow explicitly.
- Unobservable guarantee — "maintains an internal cache" — Restate as an observable constraint or cut.
- Refinement cycle — A refines B's term and B refines A's term — Refinement must bottom out in a concrete definition.
- Precision-stripping rewrite — "A depends on B -> A has an outgoing edge to B." → "a relationship between two nodes" — Keep direction, cardinality, ordering; mark any withholding.
- Tautological dataflow — "Messages exit the store, unchanged" — preservation lines ("unchanged", "as declared", "as stored") are prohibited; no mention means no change. State only what changes ("messages are removed from the pending set when cleaned").
