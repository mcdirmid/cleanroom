# Guide: High-Level Specifications

## Summary

The artifact is a High-Level Specification (HLS) that defines a software component declaratively through literate prose under `high/<name>.md`. The artifact conforms to this guide and the component architecture described in the design documents. Specifications define interface (`high/<name>.md`), implementation (`high/<name>_impl.md`), external boundary (`high/<name>_ext.md`), or assembly (`high/<name>_asm.md`) components without pseudo-code, bolding, nested bullet trees, or artificial parameter flags.

Component visibility and lifetimes are governed by flat lifecycle tiers (system and agent session) where services access each other directly without object type containment or factory plumbing. Specifications follow a closed two-section layout: a why-focused `## Purpose` section with an `**Out of scope:**` boundary disclaimer, and either a unified `## Types and Behavior` section expressed in literate prose with semantic italics on concept introductions (for interface, implementation, and assembly specifications), or a `## Grounding Gaps Covered` section in plain prose without semantic italics (for external boundary specifications).

> META: "High-level specifications establish declarative component architectures and contracts; cycles and unmandated behaviors are avoided."

## Lint checks

- [ ] Header must match `# <name> <component_type> component` where `<component_type>` is `interface`, `implementation`, `external`, or `assembly`
- [ ] Front-matter ordering must place `assembles:` (for assembly specifications) and `imports:` first, followed by `implements:`
- [ ] Implementation specifications (`high/<name>_impl.md`) and assembly specifications (`high/<name>_asm.md`) must declare `implements: <components>` listing the interface component names closed
- [ ] Assembly specifications (`high/<name>_asm.md`) must declare `assembles: <components>` listing the constituent implementation and sub-assembly component names closed
- [ ] Front-matter `implements:` clause must list interface component names rather than type names or polymorphic types
- [ ] An interface or external boundary specification must never declare `implements:`
- [ ] Front-matter `implements:` clause must never contain entries that are also declared under `imports:` or `assembles:`
- [ ] An implementation component must implement all singleton types defined in each interface component it lists under `implements:`
- [ ] An assembly component's `implements:` clause must equal the union of all `implements:` clauses of its constituent components
- [ ] An assembly component's `imports:` clause must contain all components imported by its constituents except those implemented by the assembly
- [ ] A root assembly component ready for execution must implement all interface components in the binary and have no imports outside data types and external boundary components
- [ ] Front-matter must never contain `instantiates:` or `types from <dep>:` statements
- [ ] Imported component names in `imports:` must never appear in `## Types and Behavior`
- [ ] Section inventory is closed strictly to `## Purpose` and `## Types and Behavior` (or `## Grounding Gaps Covered` for external boundary specifications)
- [ ] Sub-headers (`###`) are strictly prohibited

## Document structure

- [ ] The document consists exclusively of optional front-matter, `## Purpose`, and `## Types and Behavior` (or `## Grounding Gaps Covered` for external boundary specifications)
- [ ] An interface component (`high/<name>.md`) defines public object types, data types, and capabilities as the bill of sale for consumers and mock generation
- [ ] An implementation component (`high/<name>_impl.md`) refines capabilities into concrete tool naming, algorithms, preconditions, and error feedback for realized types
- [ ] An external boundary component (`high/<name>_ext.md`) describes external domain knowledge and grounding gaps covered without specifying an API or types, containing strictly `## Purpose` and `## Grounding Gaps Covered` sections, using zero semantic italics, and grounding to an external boundary stub without Python code
- [ ] An assembly component (`high/<name>_asm.md`) aggregates constituent implementation and sub-assembly components, closing their combined interface components and propagating unresolved dependencies

## Front-matter and imports

- [ ] Specifications without external dependencies omit `imports:` entirely
- [ ] `imports:` lists only component-level module names separated by commas
- [ ] Assembly specifications declare `assembles: <components>` listing constituent implementation and sub-assembly components separated by commas
- [ ] Implementation and assembly specifications declare `implements: <components>` listing closed interface component names separated by commas
- [ ] An implementation component implements all singleton types defined by each interface component listed in `implements:`
- [ ] Front-matter `implements:` never lists polymorphic types or type names
- [ ] No component appears in both `imports:` and `implements:` within the same specification
- [ ] Assembly components aggregate constituent components, inheriting their implemented interface components and leaving only unresolved dependencies in `imports:`
- [ ] A ready-to-run root assembly component implements all interface components in the binary and declares no imports except data types and external boundary components

## Purpose and boundaries

- [ ] The `## Purpose` section begins with a single standalone summary sentence naming the component (`The <name> <component_type> component ...`) and articulating why the component exists rather than how it maintains state
- [ ] A single blank line follows the summary sentence, followed by one or two paragraphs of architectural rationale motivating the component from a system perspective
- [ ] The architectural rationale explains systemic friction, cascading risks, and workflow failure modes prevented, without overlapping or repeating behavioral details from `## Types and Behavior`
- [ ] The section ends with an out of scope paragraph qualified by the exact prefix `**Out of scope:** `
- [ ] The out of scope text identifies client workflow purpose, background intent, or caller motivations mentioned in `## Types and Behavior` rather than component obligations
- [ ] Out of scope never lists low-level technical operations that the component delegates to dependencies
- [ ] Out of scope never names specific external components, ending with `; these are handled by other components.`

## Types and Behavior structure

- [ ] The section heading is strictly `## Types and Behavior`
- [ ] Content is written in literate prose paragraphs, using selective single-level bullets separated by blank lines to enumerate parallel items or constituent collections
- [ ] Bullets are never nested; at most one level of bullet points exists
- [ ] Complete sentences terminate with a period (`.`) and never terminate with a colon (`:`)
- [ ] Bullets are preceded by a complete sentence ending with a period, followed by a separate sentence fragment header ending with a colon (`:`)
- [ ] Every bullet point grammatically completes the preceding fragment lead-in into a coherent English sentence
- [ ] No bolding (`**term**`) is used anywhere in the specification, except for the `**Out of scope:**` prefix
- [ ] Pseudo-code jargon is avoided: the term "optional" is never used, and parameters state their purpose directly
- [ ] The term "flag" is avoided; boolean choices express domain actions or conditions directly
- [ ] Features, modes, and options express purpose rather than enablement (e.g. "whether the agent should use step mode to communicate a guide to the agent progressively" rather than "whether step mode is enabled")
- [ ] Requirements state capabilities and invariants declaratively, avoiding procedural step-by-step recipes or chronological narratives

## Semantic italics and typography

- [ ] Italics (`*term*`) are used strictly as semantic markers upon introduction of an entity, object type, data type, property or state, sub-type variant, or callable operation
- [ ] If a property, state, or operation is introduced for a concept, it is italicized upon introduction for that concept, even if that word was previously introduced for another concept
- [ ] Once introduced, all subsequent references to that term anywhere within the specification remain in plain text without italics
- [ ] Terms imported from upstream components remain in plain text without italics
- [ ] Built-in architecture constructs, lifecycle tiers, execution phases, and runtime framework concepts are not introduced by the specification and remain in plain text without italics
- [ ] Common scalar attributes (such as `*name*` and `*description*`) are italicized whenever they represent introduced properties of an entity
- [ ] Operation arguments are italicized upon introduction so that operation signatures and parameter names can be cleanly extracted
- [ ] Literal tokens, method names, and identifiers mentioned in message feedback or naming are enclosed in backticks
- [ ] External boundary specifications (`high/<name>_ext.md`) use zero semantic italics throughout the document

## Lifecycle tiers and architecture

- [ ] Every singleton service declares its lifecycle tier in natural language in plain text without italics, as lifecycle tiers are built-in architectural constructs rather than terms introduced by the specification; polymorphic types do not specify a lifecycle tier
- [ ] Services do not form containment or ownership hierarchies; services within the same tier access each other directly without nested type definitions
- [ ] Aggregate services maintain collections via explicit operations, never as owned sub-types
- [ ] Shorter-lived tiers may access longer-lived tiers, but long-lived services never hold references to short-lived session services
- [ ] Container and runner frameworks instantiate session phase services directly without factory objects
- [ ] Lifecycle phases are established as execution blocks where session services operate, without explicit start or stop operations; cleaning happens within an agent session phase
- [ ] Lifecycle phase transitions are specified declaratively rather than procedurally, describing initial context provision rather than invocation sequences

## Knowledge custody and value derivation

- [ ] Every property, operational parameter, and dependency must have an explicit derivation path from known inputs, process environment, CLI flags, build manifests, upstream node data, or collaborators in scope
- [ ] System services live for the process duration and must never assume access to per-node or session-specific metadata unless explicitly passed as operation parameters or stored in an ambient system store
- [ ] Specifications must never introduce floating directives or hand-wavy resolution logic without specifying what provides the source identity or how it is bound
- [ ] Passive data types have value-based structural equality and are strictly closed within the component that introduces them; importing components cannot subtype or extend imported data types
- [ ] Data types can be specified as constructed exclusively through an authorized service operation rather than directly by callers, precluding arbitrary direct construction from primitive values
- [ ] Every capability or invariant required of an implementation must be deterministically satisfiable using only the component's declared in-scope collaborators, inputs, and configuration

## Capabilities and behavioral constraints

- [ ] Requirements state callable operations and behavioral constraints declaratively around domain entities without micromanaging collaborator routing
- [ ] Tool execution produces a structured response indicating whether execution succeeded (if not, failed), whether the session should terminate, and output content
- [ ] Tool failure content provides actionable diagnostic messages and guidance on how to execute the tool correctly
- [ ] Behavioral requirements state explicit handling for all operational outcome branches, input variants, and termination conditions without leaving unhandled edge cases to implementation guesswork
- [ ] Architectural intent, purpose, and operational notes declared in dependent specifications are inspected during alignment, ensuring all stated operational boundaries and constraints are preserved in requirements
- [ ] Dual or complementary constraints on an entity are combined into a cohesive sentence rather than fragmented into separate bullets
- [ ] Conjunctions in requirements introduce distinct conditions and avoid pairing synonymous terms that create false distinctions or imply phantom states

## Common pitfalls

- [ ] Definition-only phantoms — introducing an entity, property, or configuration without a concrete derivation path for its runtime value
- [ ] Omitted edge-case branches — leaving non-standard responses, empty inputs, or boundary cases unhandled in the specification, forcing downstream implementations to guess behavior
- [ ] Floating directives — specifying that a component loads or resolves data without identifying the source or the mechanism that binds it
- [ ] Tier custody violations — a system service holding references to session services or assuming per-node context without parameter passing
- [ ] Syntactic verification illusions — treating passing surface formatting or table parsers as proof of architectural grounding
- [ ] Pseudo-code jargon — using "optional", "flags", or procedural method signatures instead of declarative literate prose
- [ ] Enablement phrasing — writing "whether X is enabled" instead of stating the purpose or domain action of the feature
- [ ] Listing type names or polymorphic types in implements — including type names or polymorphic types rather than concrete interface component names in front-matter
- [ ] Incomplete interface closure — declaring an interface in implements without implementing all of its singleton types
- [ ] Overlapping imports and implements — listing an implemented interface component in imports
- [ ] Incomplete root assembly — leaving unresolved imports other than external boundary components or data types in a ready-to-run root assembly
- [ ] Procedural recipes — describing chronological step-by-step algorithms or start/stop imperatives instead of declarative invariants
- [ ] Procedural lifecycle blocks — specifying step-by-step lifecycle phase setup instead of declaratively stating session creation and context provision
- [ ] Lexical de-duplication — failing to italicize an operation or property upon introduction for a concept because the same word was introduced on another concept
- [ ] Re-italicizing references — italicizing terms when referring back to already-introduced concepts or imported dependencies
- [ ] Italicizing built-in constructs — italicizing lifecycle tiers, execution phases, or framework concepts that are built-in rather than introduced by the component
- [ ] Dangling lead-ins — writing bullets that clash grammatically with the introductory fragment lead-in
- [ ] Colon after complete sentence — ending a complete sentence with a colon before a bullet list
- [ ] Nested bullets — creating multi-level bullet trees instead of flat single-level bullet paragraphs
- [ ] Naming collaborators in out of scope — naming specific components instead of using "other components"
- [ ] Implementation delegation in out of scope — listing delegated technical tasks rather than distinguishing client workflow intent from component obligations
- [ ] Bolding types — using `**term**` instead of `*term*` for introductions
- [ ] Spatial containment — writing "in a <service>" instead of recognizing that tools and services are independent peer services in the session tier
