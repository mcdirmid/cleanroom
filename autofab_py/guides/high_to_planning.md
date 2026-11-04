# Guide: High-Level to Planning Specification Alignment

## Summary

The artifact is a Planning specification (`planning/<name>.md` or `planning/<name>_impl.md`) extracting, factoring, grounding, and weaving behavioral contracts from a High-Level Specification (`high/<name>.md`), submitted via `submit(target="<target_file>", change_summary="...")`. Cleanroom metadata blocks under `<!-- CLEANROOM METADATA` are managed automatically by Cleanroom tooling upon `submit`; direct edits are prohibited. Planning specifications contain no front-matter (`imports:`, `implements:`), relying directly on `high/<name>.md`. When an HLS lacks an imported component required for grounding, or when contracts cannot be constructively grounded using declared imports, the planning agent attributes defect blame to `high/<name>.md` via `blame(...)` instead of fabricating provisions.

Planning specifications isolate design rationale into continuous prose (`## Intent`), organize static type signatures into typing requirements (`### Typing`), atomize behavioral contracts into single-sentence requirements with unique bracketed snake_case slugs (`### Contracts`), and synthesize cross-cutting interactions into a flat bullet list of woven contracts (`### Woven Contracts`) under `## Factored Contracts`. Every sentence of the High-Level Specification's *Types and Behavior* must be accounted for across failure modes, degenerate cases, state mutations, conditional branches, and trailing qualifiers. Feasibility is proven under `## Grounding` by pairing exported capabilities (`### Knowledge Provisions`) with consumer obligations (`### Knowledge Requirements`). External boundary components (`_ext`) and assembly components (`_asm`) do not define standalone planning specifications. Implementation specifications (`planning/<name>_impl.md`) resolve 100% of inherited interface deferrals under `### Inherited Deferred Requirements` without open deferrals.

> META: "Planning specifications factor typing, contracts, and woven interactions under Factored Contracts, and prove constructive feasibility under Grounding using slug-based knowledge provisions and sub-bullet requirement resolutions without code syntax or circularity."

## Lint checks

- [ ] Header matches `# <name> <component_type> component` where `<component_type>` is `interface` or `implementation`
- [ ] Planning specifications contain no front-matter (`imports:`, `implements:`, `types from`), relying directly on the high-level specification
- [ ] All imported components cited in `### Woven Contracts` and `## Grounding` are declared under `imports:` or `implements:` in `high/<name>.md`; phantom citations are absent
- [ ] Section inventory is closed strictly to canonical headings in order: `## Intent` (no sub-headers), `## Factored Contracts` (`### Typing`, `### Contracts`, `### Woven Contracts`), and `## Grounding`
- [ ] External components (`_ext`) are strictly prohibited from citation in `### Woven Contracts`
- [ ] In interface specifications, sub-headers under `## Grounding` are closed strictly to `### Knowledge Provisions` and `### Knowledge Requirements`
- [ ] In implementation specifications (`planning/<name>_impl.md`), sub-headers under `## Grounding` are closed strictly to `### Knowledge Provisions`, `### Inherited Deferred Requirements`, and `### Knowledge Requirements`
- [ ] In implementation specifications (`planning/<name>_impl.md`), every `Deferred:` requirement from all implemented interfaces is present verbatim under `### Inherited Deferred Requirements`
- [ ] Contract requirements under `### Contracts` consist of a single sentence ending with a period followed by its unique bracketed snake_case slug: `- <sentence>. [<slug>]`
- [ ] Items under `### Typing` define passive types and parameters without slugs: `- <sentence>.`
- [ ] Every bullet under `### Knowledge Provisions` ends with a period followed by its unique bracketed snake_case slug: `- <sentence>. [<slug>]`
- [ ] Bullets under `### Knowledge Requirements` are declarative sentences ending with a period followed immediately by an indented sub-bullet: either `  - Grounded: [<slugs>]` or `  - Deferred: <rationale>`
- [ ] In implementation specifications (`planning/<name>_impl.md`), `  - Deferred:` sub-bullets are strictly prohibited; 100% of requirements are grounded
- [ ] All imported knowledge provisions cited in `  - Grounded:` sub-bullets are qualified with their exporting component name: `<component>: [<slug>]`
- [ ] Markdown tables (`|`) and Python AST code expressions (`self._foo`, `.bar()`, type annotations, variable assignments) are strictly absent

## Document structure and specification relationships

- [ ] An interface planning specification (`planning/<name>.md`) defines typing requirements, public behavioral contracts, exported knowledge provisions, and deferred implementation obligations
- [ ] An implementation planning specification (`planning/<name>_impl.md`) specifies concrete algorithmic contracts and resolves 100% of inherited interface deferrals without duplicating interface contracts
- [ ] Assembly components (`high/<name>_asm.md`) and external boundary components (`high/<name>_ext.md`) do not define standalone planning specifications
- [ ] Slugs serve as immutable citation ABIs: published slug identifiers remain stable even if requirement wording is refined

## Clause-by-clause contract derivation

- [ ] Every sentence in the High-Level Specification's *Types and Behavior* section is accounted for in factored contracts
- [ ] Explicit failure modes and error conditions in high-level prose are factored into distinct contracts with observable diagnostic feedback
- [ ] Degenerate and empty cases (such as empty inputs, zero matches, or missing optional keys) are preserved as distinct contracts
- [ ] Side-effect state mutations and lifecycle transitions are preserved as distinct contracts
- [ ] Conditional branches and trailing qualifiers in high-level sentences represent normative obligations and are preserved as distinct contracts
- [ ] The lifecycle tier possessive in the High-Level Specification ("a system's X" vs "an agent session's X") defines the tier, and planning contracts preserve the exact possessive phrasing

## Factored contracts and typing

- [ ] The `### Typing` section contains structural facts expressible solely in type signatures, such as record fields, dataclass properties, and variant sets
- [ ] The `### Contracts` section lists atomic behavioral contracts, operational requirements, invariants, and failure rules
- [ ] The conjunction ban (`and`, `or`, `as well as`) applies strictly to distinct obligations; enumerations of fields, parameters, or outcomes of a single operation are permitted within a single contract
- [ ] One-way conditionals ("A if B") are preserved strictly as one-way conditionals ("A when B"); synthesizing the converse is prohibited

## Woven contracts and interaction synthesis

- [ ] The `### Woven Contracts` section synthesizes cross-cutting interactions between multiple factored contracts and imported collaborator contracts as a flat bullet list
- [ ] Facts from `### Typing` are never woven into interaction contracts
- [ ] Each woven contract bullet is a complete declarative English sentence ending with a period followed by its bracketed citation list: `- <sentence>. [<citations>]`
- [ ] Local citations in woven contracts list bare slugs; imported citations group under their component name: `[<local_slugs>, <component>: [<imported_slugs>]]`

## Grounding, provisions, and deferral coverage

- [ ] `### Knowledge Provisions` declares values, states, or capabilities exposed by the component, each terminating with a period and bracketed slug
- [ ] `### Knowledge Requirements` lists information or actions required to fulfill contracts, written as declarative sentences without slugs
- [ ] In implementation specifications, inherited deferrals represent the exact union of all `Deferred:` requirements from all implemented interfaces in `implements:` order, repeated verbatim and grounded
- [ ] Internal grounding derivations form a strict Directed Acyclic Graph (DAG) with zero circularity

## Upstream defect diagnosis and blame feedback

- [ ] Delivering defect attribution to `high/<name>.md` is strictly restricted to cases where the high-level specification lacks an import necessary for grounding or contains ungroundable contracts
- [ ] Blame feedback string is strictly a single paragraph containing no newline characters, identifying the missing import or ungroundable contract without prescribing narrative text
