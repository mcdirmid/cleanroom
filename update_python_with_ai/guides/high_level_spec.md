# Guide: High-Level Specifications

## Summary

The artifact is a High-Level Specification (HLS) that defines a software component declaratively through literate prose under `high/<name>.md`. In a multi-node session, multiple high-level specifications are processed together; each target is identified by its file alias relative path, and each target is submitted individually via `submit(target="<target_file>", change_summary="...")` when complete (in single-target sessions, the target parameter may be omitted). The artifact conforms to this guide and the component architecture described in the design documents. Specifications define interface (`high/<name>.md`), implementation (`high/<name>_impl.md`), external boundary (`high/<name>_ext.md`), or assembly (`high/<name>_asm.md`) components without pseudo-code, bolding, nested bullet trees, or artificial parameter flags.

Specifications define domain concepts through a disciplined term ontology where each concept is represented by exactly one canonical term, avoiding synonym drift and avoiding introducing different terms for opposite sides of the same concept. Component visibility and lifetimes are governed by hierarchical lifecycle tiers (the root system tier and subordinate tiers defined by interface components) where services access each other directly without object type containment or factory plumbing. Specifications follow a closed two-section layout: a why-focused `## Purpose` section with an `**Out of scope:**` boundary disclaimer, and either a unified `## Types and Behavior` section expressed in literate prose with semantic italics strictly on term introductions (for interface, implementation, and assembly specifications), or a `## Grounding Gaps Covered` section in plain prose without semantic italics (for external boundary specifications).

> META: "High-level specifications establish declarative component architectures and disciplined term ontologies; synonym drift, dual-term divergence, and unmandated behaviors are avoided."

## Lint checks

- [ ] Header matches `# <name> <component_type> component` where `<component_type>` is `interface`, `implementation`, `external`, or `assembly`
- [ ] Front-matter ordering places `assembles:` (for assembly specifications) and `imports:` first, followed by `implements:`
- [ ] Implementation specifications (`high/<name>_impl.md`) and assembly specifications (`high/<name>_asm.md`) declare `implements: <components>` listing the interface component names closed
- [ ] Assembly specifications (`high/<name>_asm.md`) declare `assembles: <components>` listing constituent implementation and sub-assembly component names closed
- [ ] Front-matter `implements:` clause lists interface component names rather than type names or polymorphic types
- [ ] An interface or external boundary specification never declares `implements:`
- [ ] Front-matter `implements:` clause never contains entries that are also declared under `imports:` or `assembles:`
- [ ] An implementation component implements all singleton types defined in each interface component it lists under `implements:`
- [ ] An assembly component's `implements:` clause equals the union of all `implements:` clauses of its constituent components
- [ ] An assembly component's `imports:` clause contains all components imported by its constituents except those implemented by the assembly
- [ ] A root assembly component ready for execution implements all interface components in the binary and has no imports outside data types and external boundary components
- [ ] Front-matter never contains `instantiates:` or `types from <dep>:` statements
- [ ] Imported component names in `imports:` never appear in `## Types and Behavior`
- [ ] Section inventory is closed strictly to `## Purpose` and `## Types and Behavior` (or `## Grounding Gaps Covered` for external boundary specifications)
- [ ] Sub-headers (`###`) are strictly prohibited

## Document structure and front-matter

- [ ] The document consists exclusively of optional front-matter, `## Purpose`, and `## Types and Behavior` (or `## Grounding Gaps Covered` for external boundary specifications)
- [ ] An interface component (`high/<name>.md`) defines public object types, data types, and capabilities as the bill of sale for consumers and mock generation
- [ ] An implementation component (`high/<name>_impl.md`) refines capabilities into concrete naming, algorithms, preconditions, and failure feedback for realized types without repeating property catalogs or data fields already defined in implemented interface components
- [ ] An external boundary component (`high/<name>_ext.md`) describes external domain knowledge and grounding gaps covered without specifying an API or types, containing strictly `## Purpose` and `## Grounding Gaps Covered` sections, using zero semantic italics, and grounding to an external boundary stub without Python code
- [ ] An assembly component (`high/<name>_asm.md`) aggregates constituent implementation and sub-assembly components, closing their combined interface components and propagating unresolved dependencies
- [ ] Assembly components are purely structural aggregations of constituent components; no behavioral logic, tool installation, algorithmic branching, operational code, or runtime logic can occur at the assembly level
- [ ] Specifications without external dependencies omit `imports:` entirely
- [ ] `imports:` lists only component-level module names separated by commas
- [ ] Assembly specifications declare `assembles: <components>` listing constituent implementation and sub-assembly components separated by commas
- [ ] Implementation and assembly specifications declare `implements: <components>` listing closed interface component names separated by commas
- [ ] No component appears in both `imports:` and `implements:` within the same specification

## Purpose and boundaries

- [ ] The `## Purpose` section begins with a single standalone summary sentence naming the component (`The <name> <component_type> component ...`) and articulating why the component exists rather than how it maintains state
- [ ] A single blank line follows the summary sentence, followed by one or two paragraphs of architectural rationale motivating the component from a system perspective
- [ ] The architectural rationale explains systemic friction, cascading risks, and workflow failure modes prevented, without overlapping or repeating behavioral details from `## Types and Behavior`
- [ ] The section ends with an out of scope paragraph qualified by the exact prefix `**Out of scope:** `
- [ ] The out of scope text identifies client workflow purpose, background intent, or caller motivations mentioned in `## Types and Behavior` rather than component obligations
- [ ] Out of scope never lists low-level technical operations that the component delegates to dependencies
- [ ] Out of scope never names specific external components, ending with `; these are handled by other components.`

## Term ontology and semantic italics

- [ ] Italics (`*term*`) are used strictly as semantic markers upon the first introduction of a newly defined entity, object type, data type, property or state, sub-type variant, or callable operation
- [ ] Common English words, adjectives, outcome descriptions, and structural descriptors remain in plain text without italics unless they constitute an introduced domain property
- [ ] Once introduced, all subsequent references to that term anywhere within the specification remain in plain text without italics
- [ ] Terms imported from upstream components remain in plain text without italics
- [ ] Built-in architecture constructs, lifecycle tiers, execution phases, and runtime framework concepts are not introduced by the specification and remain in plain text without italics
- [ ] Operation arguments are italicized upon introduction so that operation signatures and parameter names can be cleanly extracted
- [ ] Literal tokens, method names, and identifiers mentioned in message feedback or naming are enclosed in backticks
- [ ] External boundary specifications (`high/<name>_ext.md`) use zero semantic italics throughout the document
- [ ] No bolding (`**term**`) is used anywhere in the specification, except for the `**Out of scope:**` prefix

## Canonical language and dual-term elimination

- [ ] Every domain concept is represented by exactly one canonical term; introducing synonyms, alternative verbs, or interchangeable nouns for the same concept is prohibited
- [ ] Different sides or opposite polarities of a single concept are expressed using the canonical term with negation or boolean qualifiers rather than introducing opposing dual terms
- [ ] Exceptional and failure conditions are phrased around the exceptional state rather than negating the normal path
- [ ] Domain verbs are pinned to a single canonical action across the specification rather than alternating between competing synonyms for the same action
- [ ] Specifications consistently distinguish between configuration schema definitions and runtime invocation values using distinct, consistent terms rather than interchangeable synonyms
- [ ] Registration and lifecycle management actions use a single canonical verb throughout the specification rather than mixing interchangeable operational verbs
- [ ] Outcome and result payloads use a single canonical noun throughout the specification rather than alternating between interchangeable synonyms
- [ ] Conjunctions in prose pair distinct conceptual conditions and never pair synonyms that imply non-existent states or dualities
- [ ] Relationships between entities are expressed through natural possessive phrasing rather than spatial containment or artificial container nouns
- [ ] Redundant explanatory gloss is omitted when naming already conveys type or variant intent (e.g., state "is either a *synced document* or a *draft document*" rather than appending redundant descriptive clauses like "synchronized with repository storage, or a draft document pending update"); downstream enforcement rules belong in the components that enforce them

## Lifecycle tiers and architecture

- [ ] Every singleton service declares its lifecycle tier using natural possessive or containment phrasing rather than "is a" classification (e.g., "The *queue coordinator* of a render session ...", "A render session's *queue coordinator* ...", or "A system's *resource manager* ..." rather than "*queue coordinator* is a render session service ..."); because scoped lifecycle phases can be duplicated, singleton services may be referenced using indefinite ("a", "an") or definite ("the") phrasing in plain text without italics; polymorphic types do not specify a lifecycle tier
- [ ] Services do not form containment or ownership hierarchies; services within the same tier access each other directly without nested type definitions
- [ ] Aggregate services maintain collections via explicit operations, never as owned sub-types
- [ ] Lifecycle tiers form a hierarchy rooted at system with child tiers defined by interface components; descendant tiers may access ancestor tiers, but ancestor services never hold references to descendant services
- [ ] Subordinate lifecycle tiers are defined in interface components as child tiers of system or another ancestor tier, enabling dependent components to import and participate in that lifecycle
- [ ] Container and runner frameworks instantiate scoped phase services directly without factory objects
- [ ] Lifecycle phases are established as execution blocks where scoped services operate, without explicit start or stop operations; processing happens within a scoped lifecycle phase
- [ ] Lifecycle phase transitions are specified declaratively rather than procedurally, describing initial context provision rather than invocation sequences

## Capabilities and operational rules

- [ ] Content is written in literate prose paragraphs, using selective single-level bullets separated by blank lines to enumerate parallel items or constituent collections
- [ ] Bullets are never nested; at most one level of bullet points exists
- [ ] Complete sentences terminate with a period (`.`) and never terminate with a colon (`:`)
- [ ] Bullets are preceded by a complete sentence ending with a period, followed by a separate sentence fragment header ending with a colon (`:`)
- [ ] Every bullet point grammatically completes the preceding fragment lead-in into a coherent English sentence
- [ ] Pseudo-code jargon is avoided: the term "optional" is never used, and parameters state their purpose directly
- [ ] The term "flag" is avoided; boolean choices express domain actions or conditions directly
- [ ] Features, modes, and options express purpose rather than enablement; phrasing requirements around whether a feature is "enabled" or "disabled" is prohibited
- [ ] Requirements state capabilities and invariants declaratively, avoiding procedural step-by-step recipes or chronological narratives
- [ ] Prose paragraphs are concise and focused on a single responsibility or concept, containing at most three sentences; paragraphs never aggregate four or more sentences into dense prose blocks
- [ ] Multi-sentence branching conditions, operational rules, parameter catalogs, or parallel behavioral constraints are decomposed into single-level bullet lists rather than compressed into narrative paragraphs
- [ ] Every property, operational parameter, and dependency must have an explicit derivation path from known inputs, process environment, CLI flags, build manifests, upstream node data, or collaborators in scope
- [ ] Failure content provides actionable diagnostic messages and guidance on how to call the service correctly
- [ ] Operational feedback, error messages, and reminders communicate declaratively and impersonally without second-person pronouns ("you", "your")
- [ ] Injected model reasoning communicates thoughts from a first-person perspective ("I", "let me")

## Common pitfalls

- [ ] Dual-term divergence — using different terms for different sides or polarities of the same concept instead of a single canonical term with negation
- [ ] Synonym drift — alternating between competing verbs or nouns for the same concept
- [ ] Over-italicization — italicizing common descriptive adjectives or outcome states that do not represent newly introduced domain concepts
- [ ] Re-italicizing references — italicizing terms on subsequent mentions or when imported from upstream components
- [ ] Italicizing built-in constructs — italicizing lifecycle tiers, execution phases, or framework concepts that are built-in rather than introduced by the component
- [ ] Definition-only phantoms — introducing an entity, property, or configuration without a concrete derivation path for its runtime value
- [ ] Omitted edge-case branches — leaving non-standard outcomes, empty inputs, or boundary cases unhandled in the specification, forcing downstream implementations to guess behavior
- [ ] Floating directives — specifying that a component loads or resolves data without identifying the source or the mechanism that binds it
- [ ] Tier custody violations — an ancestor tier service holding direct references to descendant tier services without parameter passing
- [ ] Pseudo-code jargon — using "optional", "flags", or procedural method signatures instead of declarative literate prose
- [ ] Enablement phrasing — writing "whether X is enabled" instead of stating the purpose or domain action of the feature
- [ ] Listing type names or polymorphic types in implements — including type names or polymorphic types rather than concrete interface component names in front-matter
- [ ] Incomplete interface closure — declaring an interface in implements without implementing all of its singleton types
- [ ] Overlapping imports and implements — listing an implemented interface component in imports
- [ ] Procedural recipes — describing chronological step-by-step algorithms or start/stop imperatives instead of declarative invariants
- [ ] Dangling lead-ins — writing bullets that clash grammatically with the introductory fragment lead-in
- [ ] Colon after complete sentence — ending a complete sentence with a colon before a bullet list
- [ ] Nested bullets — creating multi-level bullet trees instead of flat single-level bullet paragraphs
- [ ] Naming collaborators in out of scope — naming specific components instead of using "other components"
- [ ] Implementation delegation in out of scope — listing delegated technical tasks rather than distinguishing client workflow intent from component obligations
- [ ] Bolding types — using `**term**` instead of `*term*` for introductions
- [ ] Spatial containment — writing "inside service X" instead of peer tier membership
- [ ] "Is-a" lifecycle classification — writing "service X is a system service" or "coordinator Y is a render session service" instead of natural possessive or containment phrasing ("A system's service X...", "The coordinator Y of a render session...", "A render session's coordinator Y...")
- [ ] Redundant gloss — appending wordy explanatory clauses that merely restate what a self-evident type or variant name already conveys (e.g., adding "synchronized with repository storage" to "synced document") or anticipating downstream component enforcement rules
- [ ] Second-person feedback — specifying failure feedback, error diagnostics, or reminders using second-person pronouns ("you", "your") instead of declarative, impersonal constraints
- [ ] Monolithic narrative paragraphs — packing multiple responsibilities, branching conditions, or operational outcomes into dense prose paragraphs of four or more sentences instead of decomposing them into concise paragraphs or declarative bullet points
- [ ] Assembly-level logic — placing operational behavior, extension registration, or algorithm logic inside an assembly component instead of delegating to constituent implementation components
