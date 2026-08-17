# Guide: High-Level Specifications (HLS) — New Format

## Purpose

An HLS describes *what* a component does — concepts, behaviors, contracts — in natural language, without implementation details. It is the single source of truth for design, implementation, and tests: complete, unambiguous, and testable.

The defining trait of an HLS is **extreme separation of concerns**: it separates *what* a component does from *how* it does it; what clients must know from what implementations encapsulate; and each design concern into its own line, section, and file. Vague terms are **grounded**: meaning may be withheld, observability never is.

HLS files are read primarily by LLMs. Every sentence must be parseable by an LLM reading that file alone, with the specs it references loaded into context. The format is designed for that reader.

## The Five Pillars

1. **Natural language, not DSL.** Semantics are ordinary English. No formal grammar, no schema, no invented vocabulary beyond naming. Structure is used to remove duplication, never to replace prose.
2. **Declarative.** An HLS states constraints, invariants, and observable relationships — never procedures. No internal steps, no sequencing (except observable ordering), no mechanisms.
3. **One fact per line.** Guarantees, assumptions, and behaviors are self-contained lines. A line must be complete on its own: no header rows, no "as above", no fragments. Each line states exactly one concern.
4. **Extreme separation of concerns.** One component per file; one concern per section; one fact per line; deltas only. The interface's usage contract and the implementation's specifics live in different specs, in different ecosystems (HLS vs LLS).
5. **Terms defined once.** Each term is owned by exactly one interface. Other specs reference it by name and never re-define it.

## The Reading Model

An LLM reads a spec as a token stream, with no memory of prior reads and no guarantee that the whole file (or its whole context) is present. Consequences:

- **Self-contained lines.** If a read is truncated, every line before the cut must remain a complete, correct fact. A table row without its header row is a fragment; a list line is a fact.
- **Lists over tables.** Tables are used only for genuinely rectangular matrices where the grid pattern is the information (logger events × when × fields; outcome mappings). Most contracts are heterogeneous — some rows have conditions, some have effects, some have neither — and a table forces filler cells and header-dependent fragments. A list handles irregular shapes naturally, and shared effects are factored once instead of repeated per row. **This guide itself contains no tables**: a teaching document must not license the weaker form by example. Even in the allowed rectangular case, prefer a list when cells would depend on their header to be understood — lists cost a few percent more tokens but survive truncation, extraction, and quotation intact.
- **No grammar beyond English.** "If...then" may be abbreviated `->`, but that is shorthand, not syntax. If a rule cannot be expressed in ordinary English, it does not belong in an HLS.

## Declarative Writing

An HLS is declarative: it says what holds, not what happens.

- **Constraints, not steps.** A guarantee is a constraint on observable state: "the new record is persisted before the old record is deleted" is an *ordering constraint*; "the component persists the new record, then deletes the old record" is a *procedure*. Only the former is declarative.
- **Sequencing language only when the order is observable.** "First", "then", "next", "after that" appear only to state an ordering that clients or downstream components can observe — the order of client-visible effects, persistence, or delivery. They never describe internal steps.
- **No mechanism.** An HLS does not say *how* something is accomplished: no "it iterates over", "it builds a", "it calls", "it stores in a hash map". It says what clients can rely on and what state changes are visible.
- **The observability test.** For every sentence, ask: "Can a client or a downstream component observe this?" If only the implementation can observe it, the sentence is procedural detail — cut it, or restate it as an observable constraint.
- **Failure is a semantic statement.** "Signals failure, leaving the queue unchanged and halting the operation" — never "raises an error", never "returns an error code".
- **Declarative is not vague.** "or custom conditions hold" and "at most once per run" are declarative. Declarative is about *relationship* — precision is independent of it.

Worked pairs (synthetic):

- Procedural (rejected): "The component first validates the request, then executes the operation, and finally writes the result."
  Declarative (accepted): "Execution occurs only when the request is valid; the result is observable only after execution completes."
- Procedural (rejected): "It builds an index of all active orders before answering the query."
  Declarative (accepted): "Queries provide a consistent view of all active orders."
- Procedural (rejected): "When the run finishes, it collects the transcript, writes the log, and notifies the client."
  Declarative (accepted): "The result carries the full transcript; the log is written before the result is provided."

## Separation of Concerns

The primary distinction of an HLS over an LLS is *extreme* separation of concerns. The LLS separates implementation-specification concerns (data types, configuration, behavior, failures, invariants); the HLS separates design concerns at a coarser grain — and, decisively, separates the interface's usage contract from the implementation's specifics so completely that they live in different specs, in different ecosystems (HLS vs LLS). This affects the format structurally, at three levels.

**File level.**

- One component per file. An interface spec contains no implementation content; an implementation spec contains no interface content beyond what it fulfills.
- An HLS contains no types, signatures, or data structures — those are the LLS's concern. If a sentence names a data type or a literal token, it belongs in the LLS.
- Interface specs and implementation specs are separate files: the interface/implementation separation is enforced by the file system, not by prose discipline.

**Section level.** Each fixed section owns exactly one concern; mixing is an error.

- *Purpose*: what the component provides. Nothing else.
- *Owned definitions*: term meanings only — no behavior, no guarantees.
- *Observable dataflow*: what enters and exits, ordering, persistence, termination — observable relationships only, never internal processing.
- *Contract*: client configuration, per-operation inputs, client actions, guarantees, assumptions — each in its own sub-section. A guarantee in Assumptions, or an assumption in Guarantees, is an error. Client-supplied configuration belongs in the Contract; assembler wiring (which implementations are chosen) belongs in the implementation spec.
- *Non-concerns*: scope exclusions only.
- *Implementation Deltas*: optional sub-sections, each present only when the component adds something beyond the fulfilled interface: Behavior, Operation Boundaries, Ordering, State Management, External Dependencies, Error Handling, Refined terms. A concern with no delta gets no section — separation without boilerplate.

**Line level.** One fact per line (Pillar 3) is a separation rule: each line states exactly one concern. A line that mixes a guarantee with an assumption, or behavior with mechanism, is an error.

## Term Ownership

### Ownership rules

- Every term is owned by exactly one interface — the one that defines it in its Owned definitions section.
- A spec that uses a term it does not own lists it in front matter: `terms (from order_service): held, receipt`.
- Re-defining a term owned elsewhere is an error. Using a term without listing it is an error.
- **There is no global glossary file.** A reader loads the transitive closure of referenced specs; the owning definition is always in that closure. Front-matter `terms (from ...)` lines are pointers (and lint anchors), not duplicates.

### Use-level definitions (interfaces)

An interface defines a term only as precisely as its users need. Where more precision would be needed to implement but not to use, the interface deliberately withholds it — and says so. Three ways to withhold:

- **Opaque:** the user does not need the meaning at all. Declare it: "an opaque value; the component does not inspect, transform, or interpret it; it passes through unchanged."
- **Open:** the user does not need the content. Declare it: "the exact content is unspecified."
- **Hook:** the user does not need the conditions. Declare it: "or custom conditions hold" — the trigger is the interface's business, not the user's.

Consumers take such terms for granted. They know *that* a held order blocks fulfillment, not *what* makes it held; *that* a payment token arrives, not *what* it means; *that* a receipt is delivered, not *what* it contains.

### Concrete definitions (implementations)

An implementation may refine a term it needs to make concrete — an interface hook it must implement, an opaque value it must produce, an open content it must fill. Refinements live in the implementation's Deltas section and are declared in front matter:

`terms (refined): held -> payment pending beyond the hold window or the fraud check flagged the order`

A specializing interface — one that fulfills another interface's contract with domain data — may refine inherited terms the same way (e.g., a storage interface specializing a generic graph's *node* to a workspace target). The refinement is declared in front matter and detailed in the specializing interface's Owned definitions or Observable dataflow.

Refinement rules:

- A refinement **narrows**: it instantiates a hook, fills an open content, or identifies an opaque value's role. It never contradicts the interface definition.
- A refinement is written only when implementing requires the precision the interface withheld. If the implementation adds no precision, there is no refinement.
- A refinement is local: it binds in the implementation and its dependents (via their own `terms (from ...)` lines). It never propagates back to the interface.

This is how the format enforces the interface/implementation boundary: interfaces expose just enough "how to use" information; specifics are encapsulated in implementations — visibly, not implicitly.

### Worked examples (synthetic)

**Hook.** Interface `order_service` owns *held*: "an order is held when payment is pending or custom conditions hold." A consumer, `fulfillment`, uses the term — "an order is fulfilled only while none of its orders are held" — and never needs the custom conditions. Implementation `order_service_impl` refines: `terms (refined): held -> payment pending beyond the hold window or the fraud check flagged the order`. The refinement narrows the hook; the interface definition is untouched.

**Opaque.** `order_service` owns *payment token*: "an opaque value; the component does not inspect, transform, or interpret it; it enters with the order and exits with the receipt unchanged." The service neither knows nor cares what it means; a payment gateway produces it; the implementation passes it through. Each side needs only the pass-through contract.

**Open.** `order_service` owns *receipt*: "a record of the completed order; the exact content is unspecified." Consumers route or store it without reading it. The implementation that produces receipts fills the open content in its Deltas — and that content is its business alone.

## Constraint Inheritance

A spec's effective constraint set is its own lines plus the transitive closure of the constraints of every spec it depends on (`imports:` and `fulfills:`). Constraints from dependencies are **in effect in the current spec without being restated** — this is what makes "deltas only" sound: the delta is exactly the difference between the effective set and the inherited set.

- **Restating an inherited constraint is an error.** A constraint already in the closure appears in exactly one spec; duplicating it creates two sources of truth that can drift apart.
- **Dependencies' assumptions are inherited.** A dependency's precondition becomes the dependent's precondition. A dependent that must establish it says so only when it adds precision (e.g., "the store is loaded before any message is added").
- **Non-concerns propagate as "not guaranteed".** A dependent may not rely on behavior a dependency declares out of scope.
- **Narrowing is allowed; contradicting is not.** A spec may strengthen a dependency's guarantee ("at most once per call" becomes "exactly once per call") or refine its terms; it may never state the opposite.
- **Readers get this for free.** Because readers load the closure, an LLM that has loaded the dependencies sees the full constraint set without a single restated line in the current file.

## Grounding

An HLS accepts vague term definitions (opaque, open, hook) — but vagueness is grounded, never free-floating. The rule: **meaning may be withheld; observability never is.** A vague term must still anchor to something a client can observe, a designated refinement site, and eventually a test.

### Grounding levels

A term or constraint is grounded at the level where its meaning or effect is pinned:

- Use (interface) — the owning interface: observable dataflow — who produces it, who consumes it, what it triggers, what happens to it.
- Refinement (implementation) — the fulfilling implementation: the withheld part — hook instantiated, open content filled, opaque role identified.
- Form (LLS) — the low-level spec: types, signatures, and data structures.
- Behavior (tests) — the test suite: postconditions, invariants, and failure signals executed against the implementation.

The HLS's job is to be *groundable*, not fully grounded: it pins the use level and designates the refinement site; the LLS and tests provide the lower levels. A fully concrete HLS would be an LLS — grounding is not concreteness, and concreteness beyond the use level would violate encapsulation.

### Grounding rules

- **Every withholding names what *is* pinned.** Opaque: the pass-through path — enters, exits, unchanged; all observable. Open: the delivery and routing — who receives it, when. Hook: the behavior it controls — held orders are not fulfilled until released. A vague term with no pinned consequence is ungrounded.
- **Every hook has a refinement site in the closure.** If nothing refines "custom conditions hold", the term dangles. (A hook intentionally never refined must be declared as such.)
- **Every owned term is used or refined.** A definition no one references and no one concretizes is free-floating.
- **Refinement chains terminate.** Refinement is a strict narrowing; a cycle of mutual refinement grounds nothing.
- **Every guarantee is testable from the specs alone** — the AI Action Test at the line level, test-suite reachability at the contract level. A guarantee about something no client observes is ungrounded.
- **Boundaries to the un-specified are declared.** An external service, a human operator, or an opaque third-party value is grounded *by declaration*: the spec says it is external and out of scope, and the integration point is pinned in the LLS.

### What is ungrounded

- A vague term with no withholding marker and no observable consequence: "results are provided in a reasonable manner".
- A hook with no refinement site in the closure.
- A term defined but used by no one and refined by no one.
- A guarantee no test could check (internal mechanism, unobservable state).
- A refinement chain that loops or never narrows.
- A constraint with no trigger, no state effect, and no failure semantics.

## Document Structure

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

<short prose: what enters, what exits, ordering, persistence, termination.
 Opaque values and open contents are named here.>

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
- Declarative over procedural (see Declarative Writing): constraints and observable relationships only.
- No pseudo-code identifiers: outcomes are "continue", "complete the request", "reject the request", "invalid input"; a record ID; flags are "true"/"false"; absence is "none". Type names and literal tokens belong to the LLS. Interface and component names (`order_service`, `dispatcher`) are exempt.
- The client appears only in Interface sections. Implementation sections never mention "client".
- Every guarantee is testable. Every sentence passes the **AI Action Test**: "Can an LLM derive an interface usage constraint, an implementation behavior constraint, or a dependency requirement from this sentence? If not, remove it."

### Formatting

- One fact per bullet. Subject first: `Snapshot = the committed state at call time`, not "The implementation snapshots the state...".
- Factor shared effects once: a failure clause shared by several triggers is written once, with the triggers as a sub-list beneath it.
- `->` abbreviates "if...then": `target outside the service area -> failure, halt, pending orders unchanged`.
- Tables only for rectangular matrices; cells self-contained (no "see header"). The guide itself uses no tables — it models the discipline it prescribes; specs may use tables only when token economy clearly justifies them.
- Front matter: `key: value` lines, one per line, interface names in backticks.
- No restating: an implementation does not restate the fulfilled interface; a consumer does not restate owned definitions.
- No mixing: one concern per line, per section, per file.

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
- [ ] Every hook has a refinement site in the closure; every owned term is used or refined
- [ ] Refinement chains terminate (strict narrowing, no cycles)
- [ ] Every guarantee testable from the specs alone; no guarantee about unobservable state
- [ ] One component per file; interface and implementation in separate specs
- [ ] No types, signatures, or data structures (LLS concern)
- [ ] No concern mixing: guarantee in Assumptions, behavior in definitions, client action in an implementation spec — all errors
- [ ] Language rules: no "returns"; failure semantics stated; iff/must/may/when/if used precisely; no pseudo-code identifiers; client only in Interface sections
- [ ] AI Action Test passed for every sentence
- [ ] Observable dataflow specified: enters, exits, ordering, persistence, termination
- [ ] Operation boundaries (atomicity) in the interface when client-visible
- [ ] Configuration vs per-operation inputs distinguished; assembler wiring confined to the implementation spec
- [ ] Non-concerns list only aspects that do not affect correctness or observable behavior

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
- Untestable — "Handles errors gracefully" — Define the state effect of failure.
- Unmarked hook — "held when flagged" — "held when payment is pending or custom conditions hold".
- Free-floating vagueness — "results are provided in a reasonable manner" — Mark opaque/open/hook and pin the observable consequence.
- Dangling hook — "custom conditions hold" with no refinement anywhere in the closure — Add a refinement site or declare the hook intentionally unrefined.
- Restated inherited constraint — repeating a dependency's guarantee in the dependent — Delete it; the constraint is already in the closure.
- Contradicting a dependency — dependent guarantees "may repeat" where the dependency says "at most once per call" — Align, or narrow explicitly.
- Unobservable guarantee — "maintains an internal cache" — Restate as an observable constraint or cut.
- Refinement cycle — A refines B's term and B refines A's term — Refinement must bottom out in a concrete definition.
