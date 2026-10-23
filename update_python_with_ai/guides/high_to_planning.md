# Guide: High-Level to Planning Specification Alignment

## Summary

The artifact is a Planning specification (`planning/<name>.md` or `planning/<name>_impl.md`) extracting, factoring, grounding, and weaving behavioral contracts from a High-Level Specification (`high/<name>.md`), submitted via `submit(target="<target_file>", change_summary="...")` (in single-target sessions, target may be omitted). Cleanroom metadata blocks at the bottom of the file (enclosed by `<!-- CLEANROOM METADATA` and `-->`) are managed automatically by Cleanroom tooling upon `submit(change_summary=...)`; direct edits to metadata blocks are prohibited and rejected by editing tools. Submitting an unchanged file rejects a change summary; modifying content requires one. Editing an upstream file initiates a star-dependency cascade, marking downstream dependents dirty for re-stamping. In multi-node sessions, multiple planning specs are processed together by package-relative alias path. The artifact conforms to this guide and `design-docs/planning_format.md`. When a High-Level Specification lacks an imported component required for grounding, or when contracts cannot be constructively grounded using declared imports, the planning agent does not fabricate provisions; it attributes defect blame to `high/<name>.md` via `blame(...)`.

Planning specifications isolate design rationale into continuous prose (`## Intent`), organize static type signatures into typing requirements (`### Typing`), atomize behavioral contracts into single-sentence requirements with unique semantic slugs (`### Contracts`), and synthesize cross-cutting interactions into a flat bullet list of woven contracts (`### Woven Contracts`) under `## Factored Contracts`. Every sentence of the High-Level Specification's Types and Behavior must be accounted for across five critical clause types: failure modes, degenerate/empty cases, side-effect state mutations, conditional branches, and trailing qualifiers. Feasibility is established under `## Grounding` by pairing exported capabilities (`### Knowledge Provisions`) with consumer obligations (`### Knowledge Requirements`). External boundary components (`_ext`) and assembly components (`_asm`) do not define standalone planning specifications. Implementation specifications (`planning/<name>_impl.md`) resolve 100% of inherited interface deferrals (the union of all `Deferred:` requirements from every interface named in `implements:`, verbatim, in `implements:` order) under `### Inherited Deferred Requirements` without open deferrals. Verification is conducted by the `spec_qa` auditor role.

> META: "Planning specifications factor typing, contracts, and woven interactions under Factored Contracts, and prove constructive feasibility under Grounding using slug-based knowledge provisions and sub-bullet requirement resolutions without code syntax or circularity."

## Lint checks

- [ ] Header matches `# <name> <component_type> component` where `<component_type>` is `interface` or `implementation`
- [ ] Planning specifications contain no front-matter (`imports:`, `implements:`, `types from`), relying directly on the high-level specification
- [ ] All imported components cited in `### Woven Contracts` and `## Grounding` are declared under `imports:` or `implements:` in `high/<name>.md`
- [ ] Phantom citations are absent: every cited slug exists in the declared knowledge provisions of the cited component
- [ ] In interface and implementation specifications, section inventory is closed strictly to canonical `##` headings in order: `## Intent`, `## Factored Contracts`, and `## Grounding`
- [ ] Sub-headers under `## Intent` are strictly prohibited (no lines starting with `###`)
- [ ] Sub-headers under `## Factored Contracts` are closed strictly to three headings in order: `### Typing`, `### Contracts`, and `### Woven Contracts`
- [ ] External components (`_ext`) are strictly prohibited from citation in `### Woven Contracts`
- [ ] In interface specifications, sub-headers under `## Grounding` are closed strictly to `### Knowledge Provisions` and `### Knowledge Requirements`
- [ ] In implementation specifications (`planning/<name>_impl.md`), sub-headers under `## Grounding` are closed strictly to `### Knowledge Provisions`, `### Inherited Deferred Requirements`, and `### Knowledge Requirements`
- [ ] In implementation specifications (`planning/<name>_impl.md`), every `Deferred:` requirement from all implemented interfaces is present verbatim under `### Inherited Deferred Requirements`
- [ ] Contract requirements under `### Contracts` consist of a single sentence ending with a period followed by its unique bracketed snake_case slug: `- <sentence>. [<slug>]`
- [ ] Items under `### Typing` define passive types and parameters without slugs: `- <sentence>.`
- [ ] Every bullet under `### Knowledge Provisions` ends with a period followed by its unique bracketed snake_case slug: `- <sentence>. [<slug>]`
- [ ] Bullets under `### Knowledge Requirements` are declarative sentences ending with a period without bracketed slugs: `- <sentence>.`
- [ ] Every bullet under `### Knowledge Requirements` is followed immediately by an indented sub-bullet: either `  - Grounded: [<slugs>]` or `  - Deferred: <rationale>`
- [ ] In implementation specifications (`planning/<name>_impl.md`), `  - Deferred:` sub-bullets are strictly prohibited; 100% of requirements are grounded
- [ ] All imported knowledge provisions cited in `  - Grounded:` sub-bullets are qualified with their exporting component name: `<component>: [<slug>]`
- [ ] Markdown tables (`|`) and Python AST code expressions (`self._foo`, `.bar()`, type annotations, variable assignments) are strictly absent

## Document structure and specification relationships

- [ ] An interface planning specification (`planning/<name>.md`) defines typing requirements, public behavioral contracts, exported knowledge provisions, and deferred implementation obligations
- [ ] An implementation planning specification (`planning/<name>_impl.md`) specifies concrete algorithmic contracts and resolves 100% of inherited interface deferrals without duplicating interface contracts
- [ ] Assembly components (`high/<name>_asm.md`) and external boundary components (`high/<name>_ext.md`) do not define standalone planning specifications
- [ ] Free-floating `#` comments are prohibited; narrative rationale belongs exclusively in `## Intent`
- [ ] Slugs serve as immutable citation ABIs: once published and cited by other components, slug identifiers remain stable even if requirement wording is refined

## Clause-by-clause contract derivation

- [ ] Every sentence in the High-Level Specification's *Types and Behavior* section is accounted for in factored contracts
- [ ] Explicit failure modes and error conditions in high-level prose are factored into distinct contracts with observable diagnostic feedback
- [ ] Degenerate and empty cases (such as empty inputs, zero matches, or missing optional keys) are preserved as distinct contracts
- [ ] Side-effect state mutations and lifecycle transitions are preserved as distinct contracts
- [ ] Conditional branches ("when ... applies", "if ... then") are preserved as distinct contracts
- [ ] Trailing qualifiers and conditional clauses in high-level sentences represent normative obligations and are never discarded as decorative prose
- [ ] The lifecycle tier possessive in the High-Level Specification ("a system's X" vs "an agent session's X") defines the tier, and planning contracts preserve the exact possessive phrasing

## Intent specification

- [ ] The `## Intent` section contains continuous prose capturing high-level design rationale, domain background, and operational context
- [ ] Sub-headers (`###`) are strictly prohibited under `## Intent`
- [ ] Rationale clauses naming observable behavior (such as creating skeleton files when missing) are factored into contracts rather than retained in Intent

## Factored contracts and typing

- [ ] Factored contracts decompose the High-Level Specification into static type signatures under `### Typing`, atomic behavioral contracts under `### Contracts`, and synthesized interactions under `### Woven Contracts`
- [ ] The `### Typing` section contains structural facts expressible solely in type signatures, such as record fields, dataclass properties, and variant sets
- [ ] The `### Contracts` section lists atomic behavioral contracts, operational requirements, invariants, and failure rules
- [ ] The conjunction ban (`and`, `or`, `as well as`) applies strictly to distinct obligations; enumerations of fields, parameters, or outcomes of a single operation are permitted within a single contract
- [ ] When a conjunction expresses a closed set, union, or variant enumeration, the conjunction is preserved as a single atomic set definition
- [ ] One-way conditionals ("A if B") are preserved strictly as one-way conditionals ("A when B"); synthesizing the converse is prohibited

## Woven contracts and interaction synthesis

- [ ] The `### Woven Contracts` section synthesizes cross-cutting interactions between multiple factored contracts and imported collaborator contracts as a flat bullet list
- [ ] Facts from `### Typing` are never woven into interaction contracts
- [ ] Each woven contract bullet is a complete declarative English sentence ending with a period followed by its bracketed citation list: `- <sentence>. [<citations>]`
- [ ] Local citations in woven contracts list bare slugs; imported citations group under their component name: `[<local_slugs>, <component>: [<imported_slugs>]]`
- [ ] External components (`_ext`) are omitted from woven contracts

## Grounding, provisions, and deferral coverage

- [ ] `### Knowledge Provisions` declares values, states, or capabilities exposed by the component, each terminating with a period and bracketed slug
- [ ] `### Knowledge Requirements` lists information or actions required to fulfill contracts, written as declarative sentences without slugs
- [ ] Every bullet under `### Knowledge Requirements` contains exactly one indented sub-bullet: either `  - Grounded: [...]` or `  - Deferred: <rationale>`
- [ ] In implementation specifications (`planning/<name>_impl.md`), inherited deferrals represent the exact union of all `Deferred:` requirements from all implemented interfaces in `implements:` order
- [ ] In implementation specifications, every inherited deferral is repeated verbatim and grounded with at least one provision slug
- [ ] Internal grounding derivations form a strict Directed Acyclic Graph (DAG) with zero circularity

## Upstream defect diagnosis and blame feedback

- [ ] Delivering defect attribution to `high/<name>.md` is strictly restricted to cases where the high-level specification lacks an import necessary for grounding or contains ungroundable contracts
- [ ] Blame feedback string is strictly a single paragraph containing no newline characters, identifying the missing import or ungroundable contract
- [ ] Blame feedback is strictly non-prescriptive: it identifies the gap without prescribing narrative text

## Common pitfalls

- [ ] Dropping trailing clauses — omitting trailing qualifiers ("when configured", "otherwise empty") from factored contracts
- [ ] Incomplete deferral inheritance — failing to inherit the complete union of deferred requirements from all implemented interfaces
- [ ] Phantom citations — citing non-existent provision slugs or citing components not declared in `high/<name>.md`
- [ ] Inventing local provisions — fabricating provisions to bypass missing imports instead of delivering blame to `high/<name>.md`
- [ ] Breaking slug ABIs — renaming published slugs and breaking dependent component citations
- [ ] Conjunction leakage — combining independent behavioral obligations into a single compound sentence
- [ ] Front-matter in planning — declaring `imports:` or `implements:` in planning files
- [ ] Open deferrals in implementations — leaving `  - Deferred:` sub-bullets in `_impl.md`

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T05:04:27Z
LAST_CHANGED: 2026-10-10T21:54:00Z
CHANGE: Clarify that cleanroom metadata headers are managed automatically by submit
CODE_HASH: 5e62bf07cb81
-->
