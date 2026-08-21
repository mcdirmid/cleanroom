# Guide: High-Level Specifications (HLS)

## Purpose

An HLS states what a component does — concepts, behaviors, contracts — in natural language, with no implementation details. It is the single source of truth for design, implementation, and tests.

## The Five Pillars

1. **Natural language, not DSL.** Ordinary English; no formal grammar or invented vocabulary beyond naming. Structure removes duplication, never replaces prose.
2. **Declarative.** Constraints, invariants, and observable relationships — never procedures or mechanisms; no sequencing except observable ordering.
3. **One fact per line.** Every line is a complete, self-contained fact stating exactly one concern.
4. **Extreme separation of concerns.** One component per file; one concern per section, block, or line; deltas only.
5. **Terms defined once.** Each term is owned by exactly one interface; other specs reference it by name and never re-define it.

## The Reading Model

An LLM reads a spec as a token stream, with no memory of prior reads and no guarantee that the whole context is present.

- **Self-contained lines.** A line before a truncation cut must remain a complete, correct fact. Lists survive; table rows without their header do not.
- **Lists over tables.** Tables only for genuinely rectangular matrices where the grid is the information (logger events × fields), in sanctioned files.
- **No grammar beyond English.** `->` may abbreviate "if...then"; `[tag]` may name a Deltas line's dominant concern (see Deltas Tags).

## Declarative Writing

- **Constraints, not steps.** "The new record is persisted before the old record is deleted" is an ordering constraint; "the component persists the new record, then deletes the old" is a procedure. Only the former is declarative.
- **Sequencing language only for observable ordering.** "First/then/next" appear only for orderings clients or downstream components can observe.
- **No mechanism.** No "iterates", "builds", "calls", "stores in a hash map". State what clients can rely on and what state changes are visible.
- **The observability test.** For every sentence ask: "Can a client or downstream component observe this?" If only the implementation can, cut it or restate it as an observable constraint.
- **Failure is a semantic statement.** "Signals failure, leaving the queue unchanged and halting the operation" — never "raises an error", never "returns an error code".

## Separation of Concerns

The HLS separates the interface's usage contract from the implementation's specifics in different specs, enforced at four levels.

- **File level.** One component per file. An interface spec contains no implementation content; an implementation spec contains no interface content beyond what it fulfills. The split is enforced by the file system, not by prose discipline.
- **Naming.** A file whose name contains `impl` is an implementation spec; every other file is an interface spec. `dag_storage-high.md` is an interface; its implementation would be `dag_storage_impl-high.md`.
- **Section level.** The section inventory is closed: interfaces have `Purpose`, `Terms`, `Contract`, `Non-concerns`; implementations have `Deltas`, `Non-concerns`. No other section exists; mixing is an error.
- **Line level.** Each line states exactly one concern. Within a section, Contract blocks group a concern; Deltas tags name a line's dominant concern.

## Term Ownership

### Ownership rules

- Every term is owned by exactly one interface — the one that defines it in its Terms section.
- A spec that uses a term it does not own lists it in front matter: `terms (from order_service): held, receipt`.
- Re-defining a term owned elsewhere is an error; using a term without listing it is an error.
- **There is no global glossary.** Readers load the transitive closure of referenced specs; `terms (from ...)` lines are pointers (and lint anchors), not duplicates.

### Use-level definitions (interfaces)

An interface defines a term only as precisely as users need, withholding the rest — and saying so, in one of three ways:

- **Opaque** — meaning withheld: "an opaque value; passes through unchanged; the component does not inspect, transform, or interpret it."
- **Open** — content withheld: "the exact content is unspecified."
- **Hook** — conditions withheld: "or custom conditions hold"; the trigger is the interface's business.

Definition rewrites preserve all testable content — direction, cardinality, ordering, identity. Removing any is allowed only as a marked withholding (opaque/open/hook) with its consequence pinned; removing `->` or its fact is a precision loss, not a grammar fix.

Consumers take such terms for granted: they know *that* a held order blocks fulfillment, not *what* makes it held. A term may be unused in the owning file's own body yet required by specs that list it in `terms (from X):` — that is use; do not delete a term because the file itself never mentions it.

### Concrete definitions (implementations)

An implementation refines a term it must make concrete — instantiating a hook, filling open content, identifying an opaque role. Front matter lists only the names (`terms (refined): held, receipt`); the concrete definition lives in one place, as a `[refines]` Deltas line: `- [refines] held -> payment pending beyond the hold window or the fraud check flagged the order`.

Refinement rules:

- A refinement **narrows**: it instantiates, fills, or identifies; it never contradicts the interface definition.
- It exists only when implementing requires the precision the interface withheld — no precision, no refinement.
- It is **local**: it binds in the implementation and its dependents (via their own `terms (from ...)` lines); it never propagates back to the interface.

## Constraint Inheritance

A spec's effective constraint set is its own lines plus the transitive closure of every spec it depends on (`imports:`, `fulfills:`). Inherited constraints are **in effect without being restated**: the delta is the difference between the effective and the inherited set.

- **Restating an inherited constraint is an error** — the constraint appears in exactly one spec; a duplicate creates two sources of truth that can drift apart. An implementation's Deltas contains only deltas: a line pointing back at the fulfilled contract ("per the <interface> contract") is a restatement and is prohibited.
- **Dependencies' assumptions are inherited.** A dependent that must establish a dependency's precondition says so only when it adds precision.
- **Non-concerns propagate as "not guaranteed".** A dependent may not rely on behavior a dependency declares out of scope.
- **Narrowing is allowed; contradicting is not.** "At most once per call" may become "exactly once per call"; the opposite may not be stated.

## Grounding

Meaning may be withheld; observability never is.

- **Every withholding names what is pinned.** Opaque: the pass-through path (enters, exits, unchanged). Open: the delivery and routing (who receives it, when). Hook: the behavior it controls. A vague term with no pinned consequence is ungrounded.
- **Every owned term is used or refined somewhere in the closure** — its own body, a consumer's `terms (from X):`, or a refinement site. When in doubt, do not delete the term.
- **Every guarantee is testable from the specs alone** — the AI Action Test at line level, test-suite reachability at contract level.
- **Boundaries to the un-specified are declared.** An external service or human operator is grounded by declaration; the integration point is pinned in the implementation spec.
- **Ungrounded:** a vague term with no withholding marker and no observable consequence; a hook with no refinement site; a term unused and unrefined; a guarantee no test could check.

## Document Structure

### Interface vs. implementation

- One component can have two specs, in separate files: an interface (what clients rely on) and an implementation (how a concrete system fulfills it).
- Interface content: Purpose, Terms, Contract, Non-concerns. Implementation content: Deltas beyond the fulfilled contract, Non-concerns.
- An interface spec never contains implementation content — no mechanism, no internal state, no refinements, no `fulfills:`; an implementation spec never contains interface content — no `## Contract`, no owned definitions, no client language; it fulfills exactly one interface.
- Editing preserves the kind: never convert one kind into the other; a spec that declares `fulfills:` is an implementation, never a restatement.

### Interface spec

```
# <name>

imports: <dep> (what it provides)              # optional
terms (from <dep>): ...                        # optional
terms (owned): ...                             # optional

## Purpose

<what the component provides; may name its operation families>

## Terms                    # present iff terms (owned)

- <term>: <use-level definition>

## Contract

**Inputs**                  # optional; "configured:" vs "per call:"
- <client-supplied values>

**Operations**
- <what the client may do>

**Guarantees**
- <one fact per line; factor shared state effects>

**Assumptions**
- <one per line>

**<Named block>**           # optional; any single concern
- <one per line>            #   Logging, Events, Stubbing, ...
```

### Contract blocks

The Contract is a set of labeled blocks; four are standard, additional ones open-ended.

- **Inputs** — everything the client supplies: configured values and per-call inputs, distinguished inline ("configured: ...", "per call: ..."). Present only when the client supplies something.
- **Operations** — the client-initiated behaviors; each becomes an operation in the LLS.
- **Guarantees** — the component's obligations: what it provides, ordering, persistence, atomicity, failure semantics. Failure clauses shared by several triggers are factored once, with the triggers as a sub-list.
- **Assumptions** — preconditions the component relies on; caller obligations, never failure conditions.
- **Named block** — a sub-contract with exactly one concern, present when the concern warrants grouping (typically 4+ lines or a table): `**Logging**`, `**Events**`, `**Stubbing**`, `**Views**`. A named block's lines are guarantees; one concern per block; no nesting.

**Each fact appears exactly once** — in exactly one block, in exactly one section. Fidelity assertions ("provided exactly as stored") belong in Guarantees; no mention means no guarantee.

### Implementation spec

```
# <name>

fulfills: <interface>
imports: <dep> (purpose), <dep> (purpose)
terms (from <dep>): ...
terms (refined): <term>, <term>                # names only

## Deltas

- <behavior delta>
- [ordering] <observable ordering constraint>
- [boundary] <atomicity, operation scope>
- [state] <internal state and its lifetime>
- [external] <external dependency>
- [failure] <failure handling delta>
- [refines] <term> -> <concrete definition>

## Non-concerns

- <one per line>
```

### Deltas tags

The Deltas section is a flat list; no sub-headings. A line's dominant concern is named by an optional tag prefix — shorthand, never content: `[ordering]` (observable ordering), `[boundary]` (atomicity, per-call scope), `[state]` (internal state and its lifetime), `[external]` (external systems), `[failure]` (failure handling), `[refines]` (concrete definition of a refined term). Untagged lines are behavior deltas.

- At most one tag per line; a line that is mostly behavior needs no tag even when it touches another concern.
- A `[refines]` line exists for every term named in `terms (refined):`; the front-matter line lists names only.
- Every Deltas line is a delta: it adds, narrows, or pins something the fulfilled contract left open. A line restating an inherited constraint ("per the <interface> contract") is an error.

## Writing Rules

### Language

- Active voice for component actions; passive for between-operation state.
- "iff" for meaningful equivalences; "must" for constraints; "may" for options; "when" for timing; "if" for conditions.
- **"Returns" is prohibited** — "provides", "signals", "delegates".
- **"Signals failure" includes state semantics** — "signals failure, leaving the queue unchanged and halting the operation", never "returns an error".
- No pseudo-code identifiers: code tokens — type names, literals (`item_id`, `True`), camelCase/snake_case variables that are not interface/component names. Outcomes are "continue", "complete the request", "reject the request", "invalid input"; a record ID; flags are "true"/"false"; absence is "none". Interface and component names (`order_service`, `dispatcher`) are exempt; ordinary English words that coincide with type names ("string", "number") are allowed.
- The client appears only in Interface sections; implementation sections never mention "client".
- Every sentence passes the **AI Action Test**: "Can an LLM derive an interface usage constraint, an implementation behavior constraint, or a dependency requirement from this sentence? If not, remove it."

### Formatting

- One fact per bullet; subject first: `Snapshot = the committed state at call time`, not "The implementation snapshots the state...".
- Factor shared effects once: a failure clause shared by several triggers is written once, with the triggers as a sub-list beneath it.
- `->` abbreviates "if...then": `target outside the service area -> failure, halt, pending orders unchanged`.
- Front matter: `key: value` lines, one per line, interface names in backticks.
- No restating, no mixing: an implementation does not restate the fulfilled interface; a consumer does not restate owned definitions; one concern per line, block, section, file.
- Contract blocks are bold lines (`**Guarantees**`) with no colon suffix; Deltas tags are lowercase bracketed prefixes (`[ordering] `) with no colon.

### Conformance editing

- Change only non-conforming content; leave conformant lines untouched. A rewrite preserving every fact is not a change — report no change.
- The claimed change must appear in the diff; verify output against input. Every Validation Checklist item must pass.

## Validation Checklist

- [ ] Natural language throughout; no grammar invented beyond `->` and the Deltas tags
- [ ] Declarative: no internal steps, no mechanism, no sequencing except observable ordering constraints
- [ ] Every sentence passes the observability test (a client or downstream component can observe it)
- [ ] One fact per line; every line self-contained (survives truncation); one concern per line
- [ ] No tables except rectangular matrices with self-contained cells, in sanctioned files
- [ ] Section inventory closed: interfaces are exactly Purpose / Terms / Contract / Non-concerns; implementations exactly Deltas / Non-concerns; no other `##` section, no `###` headings
- [ ] Contract uses the standard blocks (Inputs, Operations, Guarantees, Assumptions) plus named blocks, one concern each; each fact appears in exactly one block
- [ ] Every term used is owned or listed in `terms (from ...)`; no term re-defined outside its owner
- [ ] Refinements narrow, never contradict, chains terminate; every refined term has one `[refines]` Deltas line
- [ ] Opaque / open / hook withholdings explicit in interface definitions, each naming what is pinned
- [ ] Implementation lists deltas only: no inherited constraint restated, no "per the <interface> contract" lines
- [ ] Deltas tags valid, at most one per line; untagged lines are behavior deltas
- [ ] Every owned term is used or refined somewhere in the closure; every hook has a refinement site
- [ ] Every guarantee testable from the specs alone; no guarantee about unobservable state
- [ ] One component per file; interface and implementation in separate specs
- [ ] File kind matches its name: no "impl" in the name → interface spec (no fulfills, no Deltas); "impl" in the name → implementation spec (fulfills + Deltas, no Contract)
- [ ] No types, signatures, or data structures (an implementation concern, not an HLS one)
- [ ] No concern mixing: guarantee in Assumptions, behavior in Terms, client action in an implementation spec
- [ ] Language rules: no "returns"; failure semantics stated; iff/must/may/when/if used precisely; no pseudo-code identifiers; client only in Interface sections
- [ ] AI Action Test passed for every sentence; operation boundaries (atomicity) in the interface when client-visible
- [ ] Configuration vs per-operation inputs distinguished inline in the Inputs block; assembler wiring confined to the implementation spec
- [ ] Non-concerns list only aspects that do not affect correctness or observable behavior
- [ ] Definition rewrites preserve all testable content; removals are marked withholdings with pinned consequences
- [ ] Only non-conforming content changed; every claimed change appears in the diff

## Common Pitfalls

Each pitfall is a self-contained item: Pitfall — Example — Fix.

- DSL drift — "atomicity(per-call)" — Say "atomic per call".
- Procedure as guarantee — "The component first validates, then executes, then writes." — "Execution occurs only when the request is valid; the result is observable only after execution completes."
- Mechanism — "It builds an index of all active orders before answering." — "Queries provide a consistent view of all active orders."
- Table for heterogeneous facts — guarantee rows with "—" filler cells — Convert to one-fact-per-line list.
- Header-dependent fragment — "| target outside service area | failure | halt" without the header — Make each line self-contained.
- Re-defining owned terms — *held* described in three specs — `terms (from order_service): held`.
- Refinement contradicting owner — implementation defines *receipt* differently than `order_service` — Narrow only; align.
- Refinement detail in front matter — `terms (refined): dirty -> pending messages...` — Names only; details in a `[refines]` Deltas line.
- Vagueness without marking — "the value is passed along" — "Opaque; passes through unchanged".
- Restating parent contract — a Deltas line says "per the <interface> contract" — Deltas only; drop the pointer.
- Concern mixing — a guarantee stated inside Assumes; behavior inside Terms; a named Contract block holding two concerns — Move each fact to its owning block or section.
- "Returns" — "Returns true when in stock" — "Signals availability when in stock".
- Failure without state — "Signals failure" — "Signals failure, leaving messages unchanged".
- Pseudo-code identifiers — `item_id`, `True` — "record ID", "true".
- Unmarked hook — "held when flagged" — "held when payment is pending or custom conditions hold".
- Free-floating vagueness — "results are provided in a reasonable manner" — Mark opaque/open/hook and pin the observable consequence.
- Dangling hook — "custom conditions hold" with no refinement anywhere in the closure — Add a refinement site or declare it intentionally unrefined.
- Restated inherited constraint — repeating a dependency's guarantee in the dependent — Delete it; the constraint is already in the closure.
- Contradicting a dependency — dependent guarantees "may repeat" where the dependency says "at most once per call" — Align, or narrow explicitly.
- Unobservable guarantee — "maintains an internal cache" — Restate as an observable constraint or cut.
- Refinement cycle — A refines B's term and B refines A's term — Refinement must bottom out in a concrete definition.
- Precision-stripping rewrite — "A depends on B" → "a relationship between two nodes" — Keep direction, cardinality, ordering; mark any withholding.
- Sub-heading in Deltas — "### Ordering" — Use a `[ordering]` tag; Deltas is a flat list.
- Fact duplicated across blocks — a guarantee stated in both Guarantees and a named block — Each fact appears in exactly one block.
