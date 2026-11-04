# Guide: High-Level Specifications

## Summary

The artifact is a High-Level Specification (HLS) defining a software component declaratively through literate prose under `high/<name>.md`, submitted via `submit(target="<target_file>", change_summary="...")`. Metadata blocks (`<!-- CLEANROOM METADATA`) are managed automatically by Cleanroom tooling upon `submit`; direct edits are prohibited. Specifications define interface (`high/<name>.md`), implementation (`high/<name>_impl.md`), external boundary (`high/<name>_ext.md`), or assembly (`high/<name>_asm.md`) components without pseudo-code, bolding, nested bullet trees, or artificial parameter flags.

Specifications define domain concepts through a disciplined term ontology where each concept is represented by exactly one canonical term, avoiding synonym drift and dual-term divergence. Component visibility and lifetimes are governed by hierarchical lifecycle tiers where services access each other directly without object type containment or factory plumbing. Specifications follow a closed two-section layout: a why-focused `## Purpose` section with an `**Out of scope:**` boundary disclaimer and an optional `**Delegated:**` boundary statement, and either a unified `## Types and Behavior` section expressed in literate prose with semantic italics strictly on term introductions (for interface, implementation, and assembly specifications), or a `## Grounding Gaps Covered` section in plain prose without semantic italics (for external boundary specifications).

> META: "High-level specifications establish declarative component architectures and disciplined term ontologies; synonym drift, dual-term divergence, and unmandated behaviors are avoided."

## Lint checks

- [ ] Header matches `# <name> <component_type> component` where `<component_type>` is `interface`, `implementation`, `external`, or `assembly`
- [ ] Front-matter ordering places `assembles:` (for assembly specifications) and `imports:` first, followed by `implements:`
- [ ] Implementation specifications (`high/<name>_impl.md`) and assembly specifications (`high/<name>_asm.md`) declare `implements: <components>` listing the interface component names closed
- [ ] Assembly specifications (`high/<name>_asm.md`) declare `assembles: <components>` listing constituent implementation and sub-assembly component names closed
- [ ] Front-matter `implements:` clause lists interface component names rather than type names or polymorphic types; interface or external boundary specifications never declare `implements:`
- [ ] Front-matter `implements:` clause never contains entries that are also declared under `imports:` or `assembles:`
- [ ] An implementation component implements all singleton types defined in each interface component it lists under `implements:`
- [ ] An assembly component's `implements:` clause equals the union of all `implements:` clauses of its constituent components; its `imports:` contains all components imported by constituents except those implemented by the assembly
- [ ] Front-matter never contains `instantiates:` or `types from <dep>:` statements
- [ ] Imported component names in `imports:` never appear in `## Types and Behavior` or `**Out of scope:**`, appearing only in `**Delegated:**`
- [ ] Implementation import accountability: every component declared in `imports:` of `high/<name>_impl.md` must be utilized in AST signatures or cited in at least one `GROUNDING:` section of `low/<name>_impl.pyi`
- [ ] Host file names, serialization schemas, and repository marker conventions belong strictly in external boundary specifications (`high/<name>_ext.md`)
- [ ] Section inventory is closed strictly to `## Purpose` and `## Types and Behavior` (or `## Grounding Gaps Covered` for external boundary specifications); sub-headers (`###`) are strictly prohibited

## Document structure and front-matter

- [ ] An interface component (`high/<name>.md`) defines public object types, data types, and capabilities as the bill of sale for consumers and mock generation
- [ ] An implementation component (`high/<name>_impl.md`) refines capabilities into concrete naming, algorithms, preconditions, and failure feedback without repeating interface property catalogs or data fields
- [ ] An external boundary component (`high/<name>_ext.md`) describes domain knowledge and grounding gaps covered without specifying an API or types, containing strictly `## Purpose` and `## Grounding Gaps Covered` sections with zero semantic italics
- [ ] An assembly component (`high/<name>_asm.md`) aggregates constituent implementation and sub-assembly components structurally; behavioral logic, algorithmic branching, or runtime logic at the assembly level is prohibited
- [ ] Specifications without external dependencies omit `imports:` entirely; `imports:` lists only component-level module names separated by commas

## Purpose and boundaries

- [ ] The `## Purpose` section begins with a single standalone summary sentence naming the component (`The <name> <component_type> component ...`) and articulating why the component exists
- [ ] A single blank line follows the summary sentence, followed by one or two paragraphs of architectural rationale motivating the component from a system perspective without repeating behavioral details
- [ ] The section ends with an out-of-scope paragraph prefixed by `**Out of scope:** `, optionally followed by a delegated paragraph prefixed by `**Delegated:** `
- [ ] The out-of-scope text identifies workflow purpose outside the component, ending with `; these are handled by other components.`; it never lists operations delegated to imported dependencies
- [ ] The delegated text identifies responsibilities coordinated by this component that are explicitly delegated to imported collaborator components; collaborator component names in `imports:` appear only in `**Delegated:**`

## Term ontology and semantic italics

- [ ] Italics (`*term*`) are used strictly as semantic markers upon the first introduction of a newly defined entity, object type, data type, property or state, sub-type variant, or callable operation
- [ ] Once introduced, all subsequent references to that term anywhere within the specification remain in plain text without italics; terms imported from upstream components remain in plain text without italics
- [ ] Built-in architecture constructs, lifecycle tiers, execution phases, and runtime framework concepts are not introduced by the specification and remain in plain text without italics
- [ ] Formal parameters of callable tools are italicized only upon initial introduction; general service capabilities express inputs in natural plain text without artificial parameter italics
- [ ] Literal tokens, method names, and identifiers mentioned in message feedback or naming are enclosed in backticks; no bolding (`**term**`) is used anywhere except the `**Out of scope:**` and `**Delegated:**` prefixes
- [ ] External boundary specifications (`high/<name>_ext.md`) use zero semantic italics throughout the document

## Canonical language and dual-term elimination

- [ ] Every domain concept is represented by exactly one canonical term; introducing synonyms, alternative verbs, or interchangeable nouns for the same concept is prohibited
- [ ] Different sides or opposite polarities of a single concept are expressed using the canonical term with negation or boolean qualifiers rather than introducing opposing dual terms
- [ ] Exceptional and failure conditions are phrased around the exceptional state rather than negating the normal path
- [ ] Domain verbs, lifecycle actions, and outcome payloads are pinned to a single canonical term across the specification rather than alternating between competing synonyms
- [ ] Relationships between entities are expressed through natural possessive phrasing rather than spatial containment or artificial container nouns

## Lifecycle tiers and architecture

- [ ] Every singleton service declares its lifecycle tier using natural possessive phrasing rather than "is a" classification (e.g., "The *queue coordinator* of a render session..." or "A system's *resource manager*..."); polymorphic types do not specify a lifecycle tier
- [ ] Services do not form containment hierarchies; services within the same tier access each other directly without nested type definitions or factory objects
- [ ] Lifecycle tiers form a hierarchy rooted at system with child tiers defined by interface components; descendant tiers may access ancestor tiers, but ancestor services never hold references to descendant services
- [ ] Lifecycle phases are established as execution blocks where scoped services operate; phase transitions are specified declaratively rather than via procedural start/stop operations

## Capabilities and operational rules

- [ ] Content is written in literate prose paragraphs, using selective single-level bullets separated by blank lines to enumerate parallel items; nested bullets are strictly prohibited
- [ ] Bullets are preceded by a complete sentence ending with a period, followed by a separate sentence fragment header ending with a colon (`:`); every bullet point grammatically completes the preceding fragment lead-in into a coherent English sentence
- [ ] Pseudo-code jargon is avoided: the term "optional" is never used, "flag" is avoided, and features express purpose rather than enablement (avoiding "enabled"/"disabled" phrasing)
- [ ] Requirements state capabilities and invariants declaratively, avoiding procedural step-by-step recipes or chronological narratives
- [ ] Prose paragraphs are concise and focused on a single responsibility, containing at most three sentences; paragraphs never aggregate four or more sentences into dense prose blocks
- [ ] Every property, operational parameter, and dependency must have an explicit derivation path from known inputs, process environment, or collaborators in scope
- [ ] Operational feedback, error messages, and reminders communicate declaratively and impersonally without second-person pronouns ("you", "your")
