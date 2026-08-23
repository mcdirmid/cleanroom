# Guide: High-Level Specifications (HLS)

## Summary

An HLS is a high-level specification: an artifact that states what a component does in natural language, with no implementation details. The artifact conforms to this guide. It is the single source of truth for design, implementation, and tests.

The spec is ordinary English and declarative: constraints, invariants, and observable relationships, never procedures or mechanisms; no sequencing except observable ordering. Every line is a complete, self-contained fact stating exactly one concern, and survives truncation. Five pillars:

1. Natural language, not DSL — no formal grammar or invented vocabulary beyond naming; structure removes duplication, never replaces prose.
2. Declarative — constraints, invariants, observable relationships; no procedures or mechanisms; no sequencing except observable ordering.
3. One fact per line — every line a complete, self-contained fact stating exactly one concern.
4. Extreme separation of concerns — one component per file; one concern per section, block, or line; deltas only.
5. Terms defined once — each term owned by exactly one interface; other specs reference it by name and never re-define it.

The section inventory is closed. An interface spec has exactly `Purpose`, `Terms`, `Contract`, `Non-concerns`; an implementation spec has exactly `Deltas`, `Non-concerns`. No other `##` section exists; no `###` headings. A file whose name contains `impl` is an implementation spec and declares `fulfills:`; every other file is an interface spec and never declares `fulfills:`.

## Document structure

- [ ] One component per file; interface and implementation in separate specs
- [ ] An interface spec contains no implementation content (no mechanism, no internal state, no refinements); an implementation spec contains no interface content (no Contract, no owned definitions)
- [ ] An implementation spec fulfills exactly one interface; editing preserves the kind (an interface never becomes an implementation or vice versa)
- [ ] An interface longer than its implementation signals misplaced detail: mechanism and procedure belong in the implementation spec
- [ ] The Purpose sells the component: it states what the component does and why it matters; benefits and reasons belong there, never as rationale clauses in Guarantees
- [ ] The interface hides how it is implemented: mechanisms, internal state, algorithms, and counts belong in the implementation spec, never in the interface

## Front matter

- [ ] Front matter is `key: value` lines, one per line, interface names in backticks
- [ ] Every dependency listed: `imports: <dep> (what it provides)`; every term used but not owned listed in `terms (from <dep>): ...`
- [ ] An implementation lists `fulfills: <interface>`, `imports:`, `terms (from ...):`, and `terms (refined): <names only>`
- [ ] `terms (refined):` lists names only; concrete definitions live in `[refines]` Deltas lines

## Terms

- [ ] Every term is owned by exactly one interface, defined in its `## Terms` section
- [ ] A spec that uses a term it does not own lists it in front matter; re-defining an owned term is an error; using a term without listing it is an error
- [ ] No global glossary: `terms (from ...)` lines are pointers, not duplicates
- [ ] An interface defines a term only as precisely as users need, marking withholdings: opaque (meaning withheld, the pass-through path pinned), open (content withheld), hook (conditions withheld)
- [ ] A term is defined by what it means to users, never by how it is achieved; mechanics inside a definition belong in the implementation's refinement
- [ ] A term may be unused in the owning file yet required by a consumer's `terms (from X:)` line — that is use, not a reason to delete it
- [ ] Refinements narrow (instantiate, fill, identify), never contradict; refinement chains terminate
- [ ] Refinement is local: it binds in the implementation and its dependents, never propagates back to the interface

## Contract blocks

- [ ] The Contract is a set of labeled blocks: `**Inputs**`, `**Operations**`, `**Guarantees**`, `**Assumptions**`, plus named blocks
- [ ] Inputs lists everything the client supplies, distinguishing "configured:" from "per call:"; present only when the client supplies something
- [ ] Operations lists the client-initiated behaviors; each becomes an operation in the LLS
- [ ] Guarantees lists the component's obligations; failure clauses shared by several triggers are factored once, with the triggers as a sub-list
- [ ] Assumptions lists preconditions the component relies on; assumptions are caller obligations, never failure conditions
- [ ] Named blocks group exactly one concern (4+ lines or a table); their lines are guarantees; no nesting
- [ ] Each fact appears in exactly one block and one section

## Deltas

- [ ] The Deltas section is a flat list
- [ ] Every Deltas line is a delta: it adds, narrows, or pins what the fulfilled contract left open
- [ ] At most one tag per line; untagged lines are behavior deltas
- [ ] Tags are lowercase bracketed prefixes with no colon; a line that is mostly behavior needs no tag
- [ ] The `terms (refined):` front-matter line lists names only

## Declarative writing

- [ ] Constraints, not steps: "The new record is persisted before the old record is deleted", never "the component persists the new record, then deletes the old"
- [ ] Sequencing language appears only for observable ordering
- [ ] No mechanism: no "iterates", "builds", "calls", "stores in a hash map"
- [ ] Every sentence passes the observability test: a client or downstream component can observe it
- [ ] Every interface line passes the client-need test: a client or downstream component needs it to use the interface correctly; a line only the implementation needs is mechanism and belongs in the Deltas
- [ ] A fact that requires "by" or "using" to state is mechanism — "by flushing the buffer" — and belongs in the Deltas; the interface states the outcome — "the record is persisted"
- [ ] The caller-change test: "would the caller need to change their code if this detail changed?" — yes → interface; no → implementation; a detail that affects the calling contract is interface even when it forces no code change
- [ ] Observability details appear in an interface only when a client consumes them; details only the implementation records belong in the implementation spec
- [ ] Concrete policy values (counts, thresholds) are pinned in the implementation spec; the interface states the guarantee abstractly
- [ ] Failure is a semantic statement: "signals failure, leaving the queue unchanged and halting the operation", never "raises an error", never "returns an error code"
- [ ] `->` abbreviates "if...then": `target outside the service area -> failure, halt, pending orders unchanged`

## Language

- [ ] "iff" for meaningful equivalences; "must" for constraints; "may" for options; "when" for timing; "if" for conditions
- [ ] No code tokens or type names (`item_id`); outcomes are "continue", "complete the request", "reject the request", "invalid input"; a record ID; flags are "true"/"false"; absence is "none"
- [ ] Exception class names are code tokens: the interface describes the failure; the implementation pins the class
- [ ] Interface and component names are exempt; ordinary English words that coincide with type names ("string", "number") are allowed
- [ ] The client appears only in Interface sections
- [ ] Every sentence passes the AI Action Test: it derives an interface usage constraint, an implementation behavior constraint, or a dependency requirement

## Formatting

- [ ] One fact per bullet; subject first: `Snapshot = the committed state at call time`
- [ ] One concern per line, block, section, file
- [ ] Contract blocks are bold lines (`**Guarantees**`) with no colon suffix; Deltas tags are lowercase bracketed prefixes with no colon
- [ ] An implementation does not restate the fulfilled interface; a consumer does not restate owned definitions

## Constraint inheritance

- [ ] The spec's effective constraint set is its own lines plus the transitive closure of its dependencies (`imports:`, `fulfills:`)
- [ ] References point only to dependencies: an interface never references a spec that depends on it — its implementation spec, downstream consumers, or derived artifacts such as the LLS — and never says where another spec pins a fact
- [ ] Inherited constraints are in effect without being restated; restating an inherited constraint is an error
- [ ] Dependencies' assumptions are inherited; a dependent adds precision only when it must establish a dependency's precondition
- [ ] Non-concerns propagate as "not guaranteed"; a dependent never relies on behavior a dependency declares out of scope
- [ ] Narrowing is allowed; contradicting is not

## Grounding

- [ ] Every withholding names what is pinned: opaque pins the pass-through path; open pins delivery and routing; hook pins the behavior it controls
- [ ] Every owned term is used or refined somewhere in the closure
- [ ] Every guarantee is testable from the specs alone
- [ ] Boundaries to the un-specified are declared: an external service or human operator is grounded by declaration, the integration point pinned in the implementation spec

## Conformance editing

- [ ] Only non-conforming content is changed; conformant lines untouched; a rewrite preserving every fact is reported as no change
- [ ] The claimed change appears in the diff; output is verified against input

## Lint checks

- [ ] Interface sections are exactly `Purpose`, `Terms`, `Contract`, `Non-concerns`; implementation exactly `Deltas`, `Non-concerns`; no other `##` section, in canonical order
- [ ] No `###` headings
- [ ] A file whose name contains `impl` declares `fulfills:` and `## Deltas` and has no `## Contract`; a file without `impl` never declares `fulfills:` and has no Deltas
- [ ] The `## Contract` contains **Operations**, **Guarantees**, and **Assumptions** blocks
- [ ] `terms (owned):` is present iff `## Terms` is present
- [ ] `terms (from X):` names an existing spec and a term `X` owns; a backticked import names an existing spec; the spec never references itself
- [ ] A multi-word term used in the body is owned, referenced, or refined
- [ ] `terms (refined):` appears only in implementation specs; a refined term is owned by the fulfilled interface or a listed owner; a `[refines]` Deltas line exists for every refined term
- [ ] No "returns" anywhere — "provides", "signals", "delegates"
- [ ] No pseudo-code literals (`` `True`/`False`/`None` ``)
- [ ] Implementation sections never mention "client"
- [ ] Deltas tags come from the known set: `[ordering]`, `[boundary]`, `[state]`, `[external]`, `[failure]`, `[refines]`
- [ ] No Deltas line restates the fulfilled contract ("per the `<interface>` contract")

## Common pitfalls

- [ ] No DSL drift — no invented syntax like `atomicity(per-call)` — plain words: "atomic per call"
- [ ] No procedure as guarantee — "the component first validates, then executes" — "Execution occurs only when the request is valid; the result is observable only after execution completes"
- [ ] No mechanism — "builds an index of all active orders" — "Queries provide a consistent view of all active orders"
- [ ] No outcome-as-mechanism — "the record is saved by flushing the buffer" — "the record is persisted"; the flush belongs in the Deltas
- [ ] No detail the caller cannot act on — "each entry is appended in arrival order" when the caller only reads the final list — "the final list reflects all entries"; the ordering belongs in the Deltas
- [ ] No mechanics in term definitions — "a quote: cached and refreshed hourly" — "a quote: the current price"; caching and refresh belong in the implementation
- [ ] No tables for heterogeneous facts, no header-dependent fragments — one fact per line, self-contained
- [ ] No re-defined owned terms — a term described in three specs — `terms (from order_service): held`
- [ ] No refinement contradicting the owner — narrow only; align
- [ ] No refinement detail in front matter — names only; details in a `[refines]` Deltas line
- [ ] No vagueness without marking — "the value is passed along" — "Opaque; passes through unchanged"
- [ ] No restated inherited constraint — "per the <interface> contract", a repeated guarantee, or a repeated owned term definition — deltas only; drop the restatement
- [ ] No policy values in interfaces — "locks the account after three failed attempts" — "repeated failed attempts lock the account"; the count is pinned in the implementation spec
- [ ] No exception class names — "signaled as `OrderNotFoundError`" — "signals an unexpected failure when the order is not found"; the class is pinned in the implementation spec
- [ ] No rationale clauses in Guarantees — "so the report is current when the reader opens it" — state the observable effect; the reason belongs in the Purpose
- [ ] No forward references — an interface never names a spec that depends on it (its implementation, downstream consumers, or the LLS); a fact only the implementation pins is withheld
- [ ] No concern mixing — a guarantee inside Assumptions, a behavior inside Terms — each fact in its owning block
- [ ] No "Returns" — "Returns true when in stock" — "Signals availability when in stock"
- [ ] No failure without state — "Signals failure" — "Signals failure, leaving messages unchanged"
- [ ] No pseudo-code identifiers — `item_id`, `True` — "record ID", "true"
- [ ] No dangling hook — "custom conditions hold" with no refinement in the closure — add a refinement site or declare it intentionally unrefined
- [ ] No contradicting a dependency — "may repeat" where the dependency says "at most once per call" — align, or narrow explicitly
- [ ] No unobservable guarantee — "maintains an internal cache" — restate as an observable constraint or cut
- [ ] No refinement cycle — A refines B's term and B refines A's — refinement bottoms out in a concrete definition
- [ ] No precision-stripping rewrite — "A depends on B" → "a relationship between two nodes" — keep direction, cardinality, ordering; mark any withholding
- [ ] No sub-heading in Deltas — "### Ordering" — use a `[ordering]` tag; Deltas is a flat list
- [ ] No fact duplicated across blocks — each fact appears in exactly one block
