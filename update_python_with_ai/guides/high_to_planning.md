# Guide: High-Level to Planning Specification Alignment

## Summary

The artifact is a Planning specification (`planning/<name>.md`) extracting, factoring, and weaving behavioral contracts from a High-Level Specification (`high/<name>.md`), submitted via `submit(target="<target_file>", change_summary="...")` (in single-target sessions, target may be omitted). In multi-node sessions, multiple planning specs are processed together by package-relative alias path. The artifact conforms to this guide and `design-docs/planning_format.md`. When starting from a template, inline instructions guide creating a minimal artifact satisfying initial verification.

Planning specifications purge intent and design rationale into continuous prose (`## Intent`), isolate static type signatures into typing requirements (`### Typing`), and atomize behavioral contracts into single-sentence contract requirements with zero coordinating or correlative conjunctions (except set definitions) terminated by unique semantic slugs (`### Contracts`) under `## Factored Contracts`. Polarity is not manually categorized in planning; polarity is inferrable from the contract's natural language. Cross-cutting interactions are synthesized into a flat list of woven contracts with bracketed slug citations (`## Woven Contracts`). Typing requirements are never woven. Grounding seeds and relational predicate definitions are excluded from planning specifications. Numbered lists, markdown tables, procedural execution recipes, and citation ceremonies are prohibited.

> META: "Planning specifications extract typing requirements and atomic contract requirements with unique semantic slugs without manual polarity assignment, and synthesize cross-cutting interactions into bracketed slug citations without tables, predicates, or ceremonies, cleanly separating design intent from low-level specification formalization."

## Lint checks

- [ ] Header matches `# <name> <component_type> component` where `<component_type>` is `interface` or `implementation`
- [ ] Front-matter ordering places `imports:` first (if present), followed by `implements:` (for implementation components)
- [ ] Implementation specifications (`planning/<name>_impl.md`) declare `implements: <interface>` listing the implemented interface component name
- [ ] Interface specifications (`planning/<name>.md`) never declare `implements:`
- [ ] Front-matter never contains `types from <dep>:` or `assembles:` statements
- [ ] Section inventory is closed strictly to canonical `##` headings in order: `## Intent`, `## Factored Contracts`, and `## Woven Contracts`
- [ ] Sub-headers under `## Intent` are strictly prohibited (no lines starting with `###`)
- [ ] Sub-headers under `## Factored Contracts` are closed strictly to two headings in order: `### Typing` and `### Contracts` (unpopulated categories are omitted)
- [ ] Sub-headers under `## Woven Contracts` are strictly prohibited; woven contracts are formatted strictly as a flat bullet list (`- `)
- [ ] Categories without entries are omitted under `## Factored Contracts` rather than left with empty headers
- [ ] Contract requirements under `### Contracts` consist of a single sentence ending with a period followed by its unique bracketed snake_case slug: `- <sentence>. [<slug>]`
- [ ] Items under `### Typing` define passive types and parameters without slugs: `- <sentence>.` (typing points do not participate in interaction weaving and are never cited)
- [ ] Factored contract slugs are unique snake_case identifiers within the component
- [ ] Coordinating conjunctions (`and`, `or`), correlative conjunctions (`both ... and`), and compound conjunction phrases (`as well as`) are absent from factored contract sentences, except where expressing a set, union, or variant enumeration
- [ ] Markdown tables (`|`) are absent throughout the document, including under `## Woven Contracts`
- [ ] Every woven contract bullet terminates with its bracketed constituent contract slugs without parentheses or ceremony: `- <sentence>. [<citations>]`
- [ ] Local citations in woven contracts list bare slugs; imported citations group under their component name: `[<local_slugs>, <component>: [<imported_slugs>]]`
- [ ] Every woven contract sentence ends with a period (`.`)
- [ ] Assembly components (`high/<name>_asm.md`) do not define standalone planning specifications
- [ ] Predicate definitions, fact declarations, and relational seeds are strictly prohibited

## Document structure and front-matter

- [ ] An interface planning specification (`planning/<name>.md`) defines typing requirements and public behavioral contracts for the interface
- [ ] An implementation planning specification (`planning/<name>_impl.md`) specifies concrete algorithmic contracts, validation boundaries, and model boundary defenses without duplicating interface contracts; `### Typing` is omitted unless declaring internal data types
- [ ] Implementation specifications declare `implements: <interface>` naming the interface component implemented
- [ ] Front-matter `imports:` lists only imported component names separated by commas referencing types, services, or concepts used in contracts
- [ ] Assembly components (`high/<name>_asm.md`) do not define standalone planning specifications; assembly logic is structural
- [ ] External boundary components (`high/<name>_ext.md`) define planning specifications restricted to given behavioral contracts without internal algorithmic decomposition
- [ ] Free-floating `#` comments outside the front-matter are prohibited; narrative rationale belongs exclusively in `## Intent`

## Intent specification

- [ ] The `## Intent` section contains continuous prose paragraphs capturing high-level design rationale, domain background, conversational UX motivations, token budget economics, and context management
- [ ] Sub-headers (`###`) are strictly prohibited under `## Intent`
- [ ] Design trade-offs, conversational turn minimization, deduplication, suppression keys, and context-window preservation logic are absorbed exclusively into `## Intent`
- [ ] Factored contracts and woven contracts are completely purged of intent clauses, justification phrases ("in order to", "so that", "to indicate"), and background explanations

## Factored contracts

- [ ] Factored contracts decompose the High-Level Specification into static type signatures under `### Typing` and atomic behavioral contracts under `### Contracts`
- [ ] The `### Typing` section contains structural facts expressible solely in type signatures, such as record fields, dataclass properties, parameter models, type parameters, and closed variant sets
- [ ] Typing facts are never woven into interaction contracts
- [ ] The `### Contracts` section lists atomic behavioral contracts, operational requirements, invariants, and failure rules without manual polarity partitioning
- [ ] Polarity of each contract requirement (precondition, assumption, invariant, postcondition) is inferrable from its natural language rather than encoded in section headers
- [ ] Caller assumptions and environmental invariants are formulated using caller-obligation syntax (e.g. "A caller supplies an acyclic graph", "A caller guarantees that targets exist") so downstream low-level and grounding phases distinguish caller assumptions from callee postconditions
- [ ] Every factored contract is deterministically satisfiable by the component using only declared collaborators, configuration, and inputs in scope
- [ ] Factored contracts never assume external capabilities or custody of data without an explicit derivation path from declared inputs or dependencies
- [ ] One-way conditionals ("A if B") are preserved strictly as one-way conditionals ("A when B"); translating "if" into "if and only if" or synthesizing the uncontracted converse ("not A when not B") is strictly prohibited unless the source specification explicitly states a biconditional ("if and only if", "if, but only if")

## The Zero-Conjunction Rule and atomization

- [ ] Each contract requirement item ends with a period and bracketed slug: `- <sentence>. [<slug>]`; typing items omit slugs and numbered lists are prohibited
- [ ] Coordinating conjunctions (`and`, `or`), correlative conjunctions (`both ... and`), and compound conjunction phrases (`as well as`) are strictly prohibited in factored contracts when combining multiple independent truths or distinct obligations
- [ ] When a conjunction expresses a closed set, union, or variant enumeration rather than a repetition of truth, the conjunction is preserved as a single atomic set definition
- [ ] Multi-part conversions converting keys, elements, or distinct types are split into separate atomic sentences
- [ ] Operations accepting composite parameters, alternative parameter states, or conditional branches are factored into distinct monotonic sentences rather than compound clauses
- [ ] Compound failure contracts combining trigger conditions with diagnostic reporting are decomposed into atomic trigger rules and diagnostic reporting guarantees
- [ ] Prioritized failure ladders declare failure conditions monotonically and define failure dispatch as distinct atomic decision statements
- [ ] Sentences state observable behavioral outcomes rather than procedural execution recipes or step-by-step algorithms
- [ ] Sentences employ canonical domain terminology established in the High-Level Specification without introducing competing synonyms

## Woven contracts and interaction synthesis

- [ ] The `## Woven Contracts` section synthesizes cross-cutting interactions between multiple factored contracts and imported collaborator contracts as a flat bullet list
- [ ] Sub-headers (`###`) are strictly prohibited under `## Woven Contracts`
- [ ] Facts from `### Typing` are never woven into interaction contracts
- [ ] Woven contracts articulate concrete operational behaviors, default parameter substitutions, validation triggers, and failure dispatch outcomes resulting from interacting contracts
- [ ] Within `## Woven Contracts`, formatting is strictly a flat bullet list (`- `); markdown tables (`|`) are strictly prohibited
- [ ] Each woven contract bullet is a complete declarative English sentence ending with a period followed by its bracketed citation list: `- <sentence>. [<citations>]`
- [ ] Local citations in woven contracts list bare slugs; imported citations group under their component name: `[<local_slugs>, <component>: [<imported_slugs>]]`
- [ ] Parentheses, 'woven from', and other citation ceremonies are prohibited in woven contracts
- [ ] When an operation fails under multiple conditions, each condition maps to an explicit woven contract stating the concrete diagnostic feedback string or message template
- [ ] Woven contracts specify observable system outcomes rather than internal procedural control flow or private implementation states
- [ ] Caller assumptions are never woven into callee failure ladders or defensive exception branches; caller assumption violations represent undefined behavior rather than handled failure outcomes


## Scope attribution and boundary filtering

- [ ] Operational contracts attribute responsibilities to active singletons or polymorphic services in scope
- [ ] Passive data types define only operator-like behaviors intrinsic to values themselves, such as string formatting, display representations, or structural comparisons
- [ ] Property derivation, field calculation, and validation constraints belong to active services managing the data type; unbound property formation contracts are omitted
- [ ] Record field enumerations, static type relationships, type bounds, and algebraic definitions belong under `### Typing` and are excluded from behavioral contracts
- [ ] Domain purpose explanations and clauses explaining what a flag or field indicates belong exclusively under `## Intent` and are excluded from contracts
- [ ] Trivial state setters and mechanical registration are omitted when lookup and discovery requirements already cover availability

## Common pitfalls

- [ ] Conjunction leakage — using `and`, `or`, `as well as`, or `both ... and` to combine distinct facts or obligations in factored contracts
- [ ] Splitting set conjunctions — breaking a closed set or variant enumeration into fragmented partial statements that falsify the set definition
- [ ] Weaving typing contracts — including typing facts in woven contracts instead of keeping them purely in `### Typing`
- [ ] Manual polarity headers — organizing factored or woven contracts under `Antecedents`, `Assumptions`, `Implements`, `Provisions`, or `Requirements` sub-headers instead of `### Contracts` and flat `## Woven Contracts`
- [ ] Citation ceremony — adding 'woven from', parentheses, or prose wrappers around bracketed citation slugs
- [ ] Sub-headers under Intent — introducing `###` subsections under `## Intent` instead of continuous prose paragraphs
- [ ] Sub-headers under Woven Contracts — introducing `###` subsections under `## Woven Contracts` instead of a flat bullet list
- [ ] Intent in contracts — embedding architectural rationale, UX explanations, or context-window preservation notes inside factored or woven contracts
- [ ] Markdown tables — using tabular grids under `## Woven Contracts` instead of flat bullet lists
- [ ] Missing citations — omitting bracketed factored contract citations on woven contract bullets
- [ ] Predicates or seeds in planning — defining relational predicates, Datalog facts, or grounding seeds in planning specifications
- [ ] Structural duplication — listing dataclass fields or property types under `### Contracts` instead of `### Typing`
- [ ] Imperative algorithms — phrasing contracts as chronological execution recipes instead of declarative guarantees
- [ ] Passive entity derivation — assigning operational derivation or validation responsibilities to passive data records instead of active services
- [ ] Trivial setter clutter — writing standalone contract items for basic property setters or registration when retrieval contracts already cover availability
- [ ] Numbered contract lists — using integer numbers for factored contracts instead of immutable bracketed semantic slugs
- [ ] Formula notation — using mathematical symbols, pseudo-code, or AST variables (`v_call`, `v_param`) instead of clear natural language sentences
- [ ] Fabricated failures — adding failure-handling contracts for operations whose interface specifies no failure behavior
- [ ] Translating if to if and only if — turning a one-way conditional ("A if B") into a biconditional ("if and only if", "and false otherwise") or inventing the uncontracted converse ("not A when not B")
- [ ] Missing period — terminating a factored contract or woven contract sentence without a period
