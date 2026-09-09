# Guide: High-Level Specifications (HLS)

## Summary

The artifact is the HLS for a component: it conforms to the HLS structure this guide states and serves as the single source of truth for design, low-level specifications, implementations, and test suites. The spec is ordinary English, ontology-driven, and declarative. Every line is a complete, self-contained fact stating exactly one concern.

Five pillars:
1. Natural language ontology: Concepts are declared as natural language types in italics with plain-English definitions; no code tokens, type annotations, or formal DSLs.
2. Declarative behavior: Constraints, outcomes, and observable relationships; no internal mechanics, algorithms, or sequencing except observable ordering.
3. Operations and observable transformations: State operational capabilities and outcomes directly in ordinary English (e.g. "Initial records can initialize an index store", "Appending entries adds them in chronological order"); avoid making passive types sound like autonomous living entities.
4. Extreme separation of concerns: One component per file; value types, operations, and outcomes are cleanly separated; downstream concerns (such as caching or UI rendering) and implementation details (such as host paths) are never leaked.
5. Compounding implementation behaviors: Implementation specs (<name>_impl.md) and assembly specs (<name>_asm.md) declare implements: <type name> after header imports and types, indicating that the implemented type can only be instantiated and used in _asm components (statically created and initialized, one per system). In an implementation spec, implements implements the type in place (Widget protocol implemented as WidgetImpl class) and adds compounding concrete requirements (such as parameter schemas, formatting details, metadata stripping, and requirements on internal protocol implementations created by factory operations).

The section inventory is closed:
- Interface specs: ## Purpose, ## Types, ## Behavior
- Implementation specs: optional ## Purpose, ## Behavior (with ## Types restricted to constructor configuration types for dynamic initialization)

---

## Document structure

- [ ] File contains exactly one component
- [ ] Interface specs contain no implementation content (no internal state, no private algorithms, no data structures)
- [ ] Implementation specs and assembly specs import the interface module, list types from <module>: ..., and place implements: <type name> after type imports so the implemented type is strictly in scope; the implementing class can only be instantiated and used in _asm components
- [ ] Static component wiring and dependency injection belong in assembly components (_asm.md); dynamic initialization parameters and operations required per run or per target are interface concerns declared in interface specs
- [ ] When an object must be created dynamically with per-task or per-session configuration, a factory operation is declared on a factory type within the interface spec of the created type (e.g. "Creating a *<type>* through a *<type> factory* yields a *<type>* configured from a *<type> configuration*")
- [ ] In an implementation spec implementing a factory protocol, ## Behavior specifies requirements for the factory operation as well as requirements on the created protocol type's internal implementation
- [ ] Implementation specs (_impl.md) define no domain types; the only new types an implementation may define are constructor configuration types passed to construct that specific implementation
- [ ] Blockquotes (> ...) under ## Purpose provide architectural notes, design rationale, or clarify out-of-scope modes without polluting behavioral rules

## Purpose

- [ ] ## Purpose articulates the engineering rationale and failure modes being prevented (e.g. preventing path hallucination, eliminating discovery turns, avoiding tool confusion) rather than just paraphrasing behavioral rules
- [ ] Every type in ## Types and every major capability in ## Behavior has its motivating failure mode or purpose represented in ## Purpose; compressing for conciseness never drops coverage of an entire capability
- [ ] When condensing or refining a rationale, compare the shorter draft directly against the uncompressed version; if condensing drops essential motivating context that causes types or behaviors to become unjustified or orphaned, the concise draft is invalid and must be expanded to retain full coverage
- [ ] Leaf components explain the rationale for their specific domain mechanics; composite facade components explain the rationale for composition, isolation, and coordination without duplicating sub-component internals

## Types

- [ ] Defines every primary subject, collection, message, output artifact, and outcome that participates in operations
- [ ] Every domain noun referenced in ## Behavior is defined in ## Types or imported from a declared dependency; no untyped floating concepts
- [ ] Parenthetical clarifying examples are included in type definitions to clarify common roles without creating unnecessary subtype ontology (e.g. "- A *item entry* is an entry in an *inventory manifest* (such as a serialized stock item, a temporary placeholder, or a batch receipt)")
- [ ] Types are declared in ## Types as natural language sentences: - A *<type name>* is <definition>
- [ ] No colons (:) in type definition bullets
- [ ] No code tokens, camelCase names, or type annotations in type definitions
- [ ] Types categorize rather than act; active capabilities and operations belong strictly in ## Behavior
- [ ] Value concepts (metadata, content, outcomes) are separated from operational entities (providers, handlers)
- [ ] Type definitions describe what a type is and what it does or carries, distinguishing its role by its nature: an entity that performs actions or holds state is defined by what it does (e.g. "is a provider that..."); a value that communicates or stores information is defined by what it carries (e.g. "is a structured record carrying..."); an identifier or bound is defined by what it addresses or measures (e.g. "is a path addressing...")
- [ ] When a type is an open value consumed across boundaries, its definition explicitly states its consumption and production roles
- [ ] No types for host-level or internal implementation concepts that are never directly observed or manipulated by the interface
- [ ] No unnecessary intermediate invocation records or wrapper types

- [ ] Every parameter or field declared in a configuration type has a corresponding behavioral rule describing how the component directly reads or enforces it; pass-through configuration fields are prohibited
- [ ] Composite components do not accept configuration fields on behalf of sub-systems; sub-components receive their configuration directly during assembly
- [ ] When responsibilities shift between components, configuration parameters and requirements whose original purpose no longer exists are pruned

## Behavior

- [ ] Behavioral rules are grouped into logical operations using `### <Capability Name>` sub-headings; no bare bullets (`- `) are permitted directly under `## Behavior`
- [ ] The first block under every `### <Capability Name>` heading is a prose **Grounding Declaration** (never a bullet) that explicitly declares what the operation consumes and from where (provenance), what it produces (outcomes), and any required gating conditions for state transitions
- [ ] Operational capabilities and transformations are expressed in direct active form (e.g. "A *tree balancer* can rebalance an acyclic subtree rooted at a target *item*")
- [ ] Passive contortions and gerund fragments are avoided
- [ ] Capabilities are stated directly without conversational placeholders
- [ ] Operational restrictions, permission breaches, and invalid inputs explicitly produce recovery feedback (e.g. *tool failure*)
- [ ] Ordering constraints and atomicity boundaries are explicitly stated
- [ ] Natural qualifiers on capability sentences (such as "an acyclic subgraph" or "a unique identifier") express expected input properties; operations assume inputs conform and define no checks, recovery logic, or error handling unless checking is an explicit requirement
- [ ] **Cross-Specification Terminology Consistency**: When an HLS references operations, transformations, or states established by its imported dependencies (e.g. "allocating", "indexing", "partitioning", "resolving"), it uses the exact phrasing and terminology established by those dependencies rather than inventing local synonyms or paraphrases
- [ ] **Grounding and Provenance**: Operations and transitions are grounded: dynamic inputs, directives, and factory configurations state their declared source, and stage advancements or completion outcomes state their gating conditions
- [ ] Implementation specs declare compounding concrete metadata (tool names, argument schemas, format strings) and do not repeat invariants already established by the interface

## Lint checks
 
 - [ ] Header must match the file stem (`# <name>`)
 - [ ] Front-matter ordering must place `imports:` first, followed by `types from <dep>:`, followed by `implements: <type>`
 - [ ] Non-assembly specifications (`<name>.md`, `<name>_impl.md`) must not import `*_impl` or `*_asm` specifications
 - [ ] Assembly specifications (`*_asm.md`) may import interface, implementation (`*_impl`), or assembly (`*_asm`) specifications
 - [ ] Every `types from <dep>:` line must correspond to a module declared in `imports:`
 - [ ] Implementation specifications (`*_impl.md`) and assembly specifications (`*_asm.md`) must declare `implements: <type>` in front-matter
 - [ ] Section inventory is closed strictly to `## Purpose`, `## Types`, and `## Behavior`
 - [ ] `###` headings are only permitted under the `## Behavior` section
 - [ ] Behavioral rules (bullets starting with `- `) under `## Behavior` must reside within a `### <Capability Name>` section, never bare under the main heading
 - [ ] The first block under a `### <Capability Name>` heading must be a prose block (not a bullet starting with `- `)
