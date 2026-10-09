<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T05:04:27Z
LAST_CHANGED: 2026-10-06T12:35:00Z
CHANGE: update planning structure with Grounding section, knowledge provisions, and sub-bullet resolution
CODE_HASH: dc3fad46fca6
-->

# Guide: High-Level to Planning Specification Alignment

## Summary

The artifact is a Planning specification (`planning/<name>.md` or `planning/<name>_impl.md`) extracting, factoring, grounding, and weaving behavioral contracts from a High-Level Specification (`high/<name>.md`), submitted via `submit(target="<target_file>", change_summary="...")` (in single-target sessions, target may be omitted). In multi-node sessions, multiple planning specs are processed together by package-relative alias path. The artifact conforms to this guide and `design-docs/planning_format.md`. When starting from a template, inline instructions guide creating a minimal artifact satisfying initial verification.

Planning specifications isolate design rationale into continuous prose (`## Intent`), organize static type signatures into typing requirements (`### Typing`), atomize behavioral contracts into single-sentence contract requirements with unique semantic slugs (`### Contracts`), and synthesize cross-cutting interactions into a flat bullet list of woven contracts (`### Woven Contracts`) under `## Factored Contracts`. Feasibility is established under `## Grounding` by pairing exported capabilities (`### Knowledge Provisions`) with consumer obligations (`### Knowledge Requirements`). External boundary components (`high/<name>_ext.md`) and assembly components (`high/<name>_asm.md`) do not define standalone planning specifications; external components provide grounding knowledge provisions directly and are never cited in woven contracts. Knowledge requirements contain an indented sub-bullet designating either grounding provenance (`  - Grounded: [...]`) via caller input or cited provision slugs, or implementation deferral (`  - Deferred: ...`). Implementation specifications (`planning/<name>_impl.md`) repeat inherited interface deferrals verbatim under `### Inherited Deferred Requirements`, grounding each one with at least one imported or local knowledge provision without open deferrals (the Zero-Deferred Invariant). All imported knowledge provisions are qualified with the exporting component name (`<component>: [<slug>]`). Internal grounding derivations form a strict Directed Acyclic Graph (DAG) with zero circularity. Grounding citations cite knowledge provisions, never factored contracts. Planning specifications exclude code syntax, AST expressions, and Datalog predicates. Verification is conducted by the `spec_qa` auditor role.

> META: "Planning specifications factor typing, contracts, and woven interactions under Factored Contracts, and prove constructive feasibility under Grounding using slug-based knowledge provisions and sub-bullet requirement resolutions without code syntax or circularity."

## Lint checks

- [ ] Header matches `# <name> <component_type> component` where `<component_type>` is `interface` or `implementation`
- [ ] Front-matter ordering places `imports:` first (if present), followed by `implements:` (for implementation components)
- [ ] In non-assembly specifications, front-matter `imports:` contains all imported modules declared in the corresponding high-level specification (`high/<name>.md`)
- [ ] Implementation specifications (`planning/<name>_impl.md`) declare `implements: <interface>` naming the implemented interface component
- [ ] Interface specifications (`planning/<name>.md`) never declare `implements:`
- [ ] Front-matter never contains `types from <dep>:` or `assembles:` statements
- [ ] In interface and implementation specifications, section inventory is closed strictly to canonical `##` headings in order: `## Intent`, `## Factored Contracts`, and `## Grounding`
- [ ] Sub-headers under `## Intent` are strictly prohibited (no lines starting with `###`)
- [ ] Sub-headers under `## Factored Contracts` are closed strictly to three headings in order: `### Typing`, `### Contracts`, and `### Woven Contracts` (unpopulated categories are omitted)
- [ ] External components (`_ext`) are strictly prohibited from citation in `### Woven Contracts`
- [ ] In interface specifications, sub-headers under `## Grounding` are closed strictly to two headings in order: `### Knowledge Provisions` and `### Knowledge Requirements`
- [ ] In implementation specifications (`planning/<name>_impl.md`), sub-headers under `## Grounding` are closed strictly to three headings in order: `### Knowledge Provisions`, `### Inherited Deferred Requirements`, and `### Knowledge Requirements` (unpopulated categories are omitted)
- [ ] Contract requirements under `### Contracts` consist of a single sentence ending with a period followed by its unique bracketed snake_case slug: `- <sentence>. [<slug>]`
- [ ] Items under `### Typing` define passive types and parameters without slugs: `- <sentence>.`
- [ ] Every bullet under `### Knowledge Provisions` ends with a period followed by its unique bracketed snake_case slug: `- <sentence>. [<slug>]`
- [ ] Bullets under `### Knowledge Requirements` are declarative sentences ending with a period without bracketed slugs: `- <sentence>.`
- [ ] Every bullet under `### Knowledge Requirements` is followed immediately by an indented sub-bullet: either `  - Grounded: [<slugs>]` or `  - Deferred: <rationale>`
- [ ] Grounding citations cite strictly knowledge provision slugs (under `### Knowledge Provisions`) or `caller input`; citing factored contract slugs is strictly prohibited
- [ ] In implementation specifications (`planning/<name>_impl.md`), every bullet under `### Inherited Deferred Requirements` repeats an interface deferral verbatim and is followed immediately by an indented `  - Grounded: [<slugs>]` sub-bullet citing at least one imported or local knowledge provision
- [ ] In implementation specifications (`planning/<name>_impl.md`), `  - Deferred:` sub-bullets are strictly prohibited; 100% of inherited and local knowledge requirements are grounded
- [ ] All imported knowledge provisions cited in `  - Grounded:` sub-bullets are qualified with their exporting component name: `<component>: [<slug>]`
- [ ] Bare provision slugs in `  - Grounded:` sub-bullets are strictly restricted to local provisions declared under `### Knowledge Provisions` or `caller input`
- [ ] Coordinating conjunctions (`and`, `or`), correlative conjunctions (`both ... and`), and compound conjunction phrases (`as well as`) are absent from factored contract sentences, except where expressing a set, union, or variant enumeration
- [ ] Markdown tables (`|`) are absent throughout the document, including under `### Woven Contracts`
- [ ] Every woven contract bullet terminates with its bracketed constituent contract slugs without parentheses or ceremony: `- <sentence>. [<citations>]`
- [ ] Local citations in woven contracts list bare slugs; imported citations group under their component name: `[<local_slugs>, <component>: [<imported_slugs>]]`
- [ ] Every woven contract sentence ends with a period (`.`)
- [ ] Python AST code expressions (`self._foo`, `.bar()`, type annotations, variable assignments) are strictly prohibited throughout the document
- [ ] Predicate definitions, Datalog rules, and Groundtalk clauses are strictly prohibited

## Document structure and front-matter

- [ ] An interface planning specification (`planning/<name>.md`) defines typing requirements, public behavioral contracts, exported knowledge provisions, and deferred implementation obligations
- [ ] An implementation planning specification (`planning/<name>_impl.md`) specifies concrete algorithmic contracts and resolves 100% of inherited interface deferrals without duplicating interface contracts
- [ ] Implementation specifications declare `implements: <interface>` naming the interface component implemented
- [ ] Front-matter `imports:` lists only imported component names separated by commas referencing types, services, or concepts used in contracts or grounding
- [ ] Assembly components (`high/<name>_asm.md`) and external boundary components (`high/<name>_ext.md`) do not define standalone planning specifications; assembly logic is structural, and external boundary capabilities are defined directly in High-Level and Low-Level specifications
- [ ] External components (`_ext`) provide knowledge provisions for grounding without defining planning specifications, and are strictly prohibited from citation in `### Woven Contracts`
- [ ] Free-floating `#` comments outside the front-matter are prohibited; narrative rationale belongs exclusively in `## Intent`

## Intent specification

- [ ] The `## Intent` section contains continuous prose paragraphs capturing high-level design rationale, domain background, conversational UX motivations, token budget economics, and context management
- [ ] Sub-headers (`###`) are strictly prohibited under `## Intent`
- [ ] Design trade-offs, conversational turn minimization, deduplication, suppression keys, and context-window preservation logic are absorbed exclusively into `## Intent`
- [ ] Factored contracts, grounding specifications, and woven contracts are completely purged of intent clauses, justification phrases ("in order to", "so that", "to indicate"), and background explanations

## Factored contracts and typing

- [ ] Factored contracts decompose the High-Level Specification into static type signatures under `### Typing`, atomic behavioral contracts under `### Contracts`, and synthesized interactions under `### Woven Contracts`
- [ ] The `### Typing` section contains structural facts expressible solely in type signatures, such as record fields, dataclass properties, parameter models, type parameters, and closed variant sets
- [ ] Typing facts are never woven into interaction contracts and omit bracketed slugs
- [ ] The `### Contracts` section lists atomic behavioral contracts, operational requirements, invariants, and failure rules without manual polarity partitioning
- [ ] Polarity of each contract requirement (precondition, assumption, invariant, postcondition) is inferrable from its natural language rather than encoded in section headers
- [ ] Caller assumptions and environmental invariants are formulated using caller-obligation syntax (e.g. "A caller supplies an acyclic graph", "A caller guarantees that targets exist") so downstream low-level stubs distinguish caller assumptions from callee postconditions
- [ ] Coordinating conjunctions (`and`, `or`), correlative conjunctions (`both ... and`), and compound conjunction phrases (`as well as`) are strictly prohibited in factored contracts when combining multiple independent truths or distinct obligations
- [ ] When a conjunction expresses a closed set, union, or variant enumeration rather than a repetition of truth, the conjunction is preserved as a single atomic set definition
- [ ] One-way conditionals ("A if B") are preserved strictly as one-way conditionals ("A when B"); translating "if" into "if and only if" or synthesizing the uncontracted converse ("not A when not B") is strictly prohibited unless explicitly contracted

## Woven contracts and interaction synthesis

- [ ] The `### Woven Contracts` section synthesizes cross-cutting interactions between multiple factored contracts and imported collaborator contracts as a flat bullet list
- [ ] Facts from `### Typing` are never woven into interaction contracts
- [ ] Woven contracts articulate concrete operational behaviors, default parameter substitutions, validation triggers, and failure dispatch outcomes resulting from interacting contracts
- [ ] Each woven contract bullet is a complete declarative English sentence ending with a period followed by its bracketed citation list: `- <sentence>. [<citations>]`
- [ ] Local citations in woven contracts list bare slugs; imported citations group under their component name: `[<local_slugs>, <component>: [<imported_slugs>]]`
- [ ] External components (`_ext`) are omitted from woven contracts; external components provide knowledge provisions for grounding, not behavioral contracts for weaving
- [ ] Parentheses, 'woven from', and other citation ceremonies are prohibited in woven contracts
- [ ] When an operation fails under multiple conditions, each condition maps to an explicit woven contract stating the concrete diagnostic feedback string or message template
- [ ] Caller assumptions are never woven into callee failure ladders or defensive exception branches; caller assumption violations represent undefined behavior rather than handled failure outcomes

## Grounding and knowledge reachability

- [ ] The `## Grounding` section proves constructive feasibility by establishing knowledge provisions and resolving knowledge requirements against verified sources
- [ ] `### Knowledge Provisions` declares values, states, or operational capabilities exposed by the component, each terminating with a period and bracketed slug: `- <sentence>. [<slug>]`
- [ ] `### Knowledge Requirements` lists information, observations, or actions required to fulfill contracts, written as declarative sentences without slugs: `- <sentence>.`
- [ ] Every bullet under `### Knowledge Requirements` contains exactly one indented sub-bullet: either `  - Grounded: [<slugs>]` or `  - Deferred: <rationale>`
- [ ] Requirements grounded via caller arguments or provision slugs cite sources inside brackets: `  - Grounded: [<local_slugs>, <component>: [<imported_slugs>]]`
- [ ] All imported knowledge provisions cited in `  - Grounded:` sub-bullets are qualified with their exporting component name: `<component>: [<slug>]`
- [ ] Bare provision slugs in `  - Grounded:` sub-bullets are strictly restricted to local provisions declared under `### Knowledge Provisions` or `caller input`
- [ ] Grounding citations strictly cite knowledge provision slugs or `caller input`; citing factored contract slugs is prohibited
- [ ] Requirements depending on concrete backing state, disk storage, or environment access in an interface component declare `  - Deferred: <rationale>`
- [ ] In implementation specifications (`planning/<name>_impl.md`), every requirement marked `- Deferred:` in the implemented interface is repeated verbatim under `### Inherited Deferred Requirements`, followed by an indented `  - Grounded: [<slugs>]` sub-bullet citing at least one imported or local knowledge provision
- [ ] Implementation specifications (`planning/<name>_impl.md`) satisfy the Zero-Deferred Invariant: open deferrals under `  - Deferred:` are strictly prohibited
- [ ] Composite requirements requiring multiple capabilities cite all necessary slugs in bracketed citations: `  - Grounded: [slug_1, slug_2, component: [slug_3]]`
- [ ] Internal grounding derivations form a strict Directed Acyclic Graph (DAG): self-grounding ($[P] \to [P]$) and cyclic grounding dependencies among provisions are strictly prohibited
- [ ] Python AST syntax, code snippets, method invocations, and class identifiers are strictly excluded from grounding declarations; grounding is expressed purely in literate prose and slugs

## Common pitfalls

- [ ] Code syntax in planning — inserting Python statements, method calls (`.convert()`), or field declarations (`self._foo`) into planning grounding
- [ ] Slugs on requirements — appending bracketed slugs to `### Knowledge Requirements` bullets instead of keeping them purely on `### Knowledge Provisions` and `### Contracts`
- [ ] Conjunction leakage — using `and`, `or`, `as well as`, or `both ... and` to combine distinct facts or obligations in factored contracts
- [ ] Splitting set conjunctions — breaking a closed set or variant enumeration into fragmented partial statements that falsify the set definition
- [ ] Weaving typing contracts — including typing facts in woven contracts instead of keeping them purely in `### Typing`
- [ ] Citing external components in woven contracts — citing `_ext` components in `### Woven Contracts` instead of using them purely for grounding
- [ ] Bare imported provisions — citing imported knowledge provision slugs without component qualification (`<component>: [<slug>]`)
- [ ] Open deferrals in implementations — leaving `  - Deferred:` sub-bullets in `planning/<name>_impl.md`
- [ ] Paraphrasing inherited deferrals — altering the wording of deferred interface requirements under `### Inherited Deferred Requirements` instead of repeating them verbatim
- [ ] Circular grounding — grounding a provision using itself or creating cyclic dependencies among local provisions
- [ ] Phantom imports — citing `component: [slug]` in grounding or woven contracts without declaring `component` in front-matter `imports:`
- [ ] Markdown tables — using tabular grids anywhere in the document instead of flat bullet lists
- [ ] Missing period — terminating a factored contract, woven contract, provision, or requirement sentence without a period
- [ ] Sub-headers under Intent or Woven Contracts — introducing unauthorized `###` sub-headers
