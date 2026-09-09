# grounding

## Summary
Constraints for ensuring High-Level Specifications (HLS) maintain a formally sound Knowledge Graph and chain of custody. Grounding is not about definitions; it is about the derivation of values for types. Defining a type in `## Types` does not ground it. A type, property, parameter, or dependency is grounded if and only if there is a concrete, sound derivation path to produce its value from in-scope knowledge, inputs, or known collaborators. If a value cannot be derived, it is ungrounded.

## Types and identifiers
- [ ] Every noun representing a configuration value, external dependency, operational parameter, or domain entity must map to a formally defined `## Types` entry
- [ ] Types must strictly represent abstract domain components or primitives, never in-memory data structures or host representations, unless defining an explicit wire boundary
- [ ] An HLS resolving relative locations or environmental paths must explicitly specify base root anchoring to guarantee deterministic resolution
- [ ] Table type signatures express union or sum types with English "or" rather than pipe characters to preserve markdown table column structure

## Knowledge Custody and Transitivity
- [ ] Grounding is value derivation: every property, parameter, or dependency required by a type or operation must have an explicit derivation path from known inputs, configurations, or collaborators; a type definition alone never grounds a value
- [ ] The knowledge required by an object must be explicitly provided by its creator or acquired via other bindings (e.g. knowing a factory that provides it)
- [ ] Operations requiring knowledge must explicitly define it as operational parameters, providing scoped knowledge exclusively for the duration of that execution
- [ ] Whenever a component is created dynamically through a factory, the specification must explicitly declare the source of the Knowledge passed to the factory
- [ ] The entity providing dynamic Knowledge must be imported and wired to the consuming component
- [ ] Any Knowledge required by a constructed object must be transitively satisfied by the client calling the factory, unless explicitly declared as being known by the factory itself
- [ ] A component that knows a factory and possesses the parameter knowledge required to construct a product type may satisfy requirements needing that product type through an explicit satisfaction check
- [ ] Factory creation operations must never create components from floating or ungrounded Knowledge
- [ ] Storage repositories must store and serve records populated by dedicated loaders, without conflating parsing responsibilities with storage management
- [ ] A component providing knowledge of an entity's properties grants query access across those properties, subject strictly to any explicit narrowing conditions or invariants declared in sub-bullets
- [ ] Visibility of constituents vs construction parameters: constituents declared using "has" are public and queryable by any consumer holding that type; dependencies supplied via "from" in factory definitions are parameters to the construction operation, remaining private by default to the constructed instance and not transitively accessible to consumers of that instance
- [ ] An implementation specification may introduce and know private collaborators, constructor parameters, or internal state not declared on its public interface specification, provided those private collaborators are grounded by the assembling factory or configuration that constructs the implementation
- [ ] An implementation requirement that fulfills a public contract is grounded by that contract, while implementation-private behaviors are grounded by the private collaborators and configuration the implementation knows
- [ ] Virtual identifiers mapped to concrete resources must define unambiguous resolution and disambiguation rules
- [ ] An HLS that seeds synthetic interaction history or pre-constructed event records must explicitly specify that every synthetic entry references a valid, defined schema operation
- [ ] An entity known exclusively to provide specialized recovery or redirection feedback in an implementation should avoid redundant behavioral prohibitions in the interface specification when already excluded from valid access sets
- [ ] Explicit caller intents, flags, and operational modes in implementation requirements must ground to formal domain types declared in the interface specification
- [ ] Transitive factory grounding: when a component knows factories capable of producing required intermediate dependencies and knows the arguments required by those factories (directly or via known configuration), the grounding process resolves the construction and argument wiring transitively without procedural dot-connecting or intermediate argument-passing descriptions
- [ ] Transitive connections must be near-reach: grounding resolves direct collaborator and factory dependencies within the component's immediate scope, rather than arbitrarily deep or disjoint transitive chains
- [ ] Avoid procedural parameter forwarding scripts: specifications must never dictate step-by-step intermediate factory invocations or argument forwarding (e.g. "constructs X, then passes X and Y to factory G to construct Z") when the wiring can be inferred from known factories and configuration types
- [ ] Requirements can include domain intent phrasing (such as adding pending messages "to communicate feedback" or "to communicate change") to explicitly ground mechanical operations to the collaborator's declared purpose
- [ ] Tool parameter schema optionality: grounding derives a parameter's schema optionality directly from presence conditions—a parameter is optional (required = false) if its specification conditions its presence (e.g. "X is only specified if [condition]"), and required (required = true) when introduced unconditionally

## State transition and outcome gating
- [ ] Every behavior that advances a workflow stage, mutates a lifecycle state, or concludes execution must explicitly state the gating conditions required for the transition
- [ ] Completion and advancement behaviors must be gated on observable criteria (such as validated state modifications, non-empty outputs, or passing verification checks)
- [ ] Operations providing incremental stepping must deliver remaining steps or corrective feedback rather than concluding execution prematurely
- [ ] Operational errors explicitly required by the specification must produce actionable recovery feedback
- [ ] Natural qualifiers on inputs (such as "an acyclic subgraph") define expected properties that operations assume without checking; non-conforming inputs are unexpected failures and must never be specified as operational gating or recovery paths unless checking is an explicit requirement
- [ ] Preconditions and assumed properties that result in undefined behavior when violated are partitioned into an Assumptions section, keeping the Requirements section strictly for binding behavioral guarantees and explicit failure handling
- [ ] Operations that record events to an observer or sink must explicitly specify the construction and dispatch of event records for each observed transition
- [ ] Workflows providing progressive milestone delivery must explicitly define the interception mechanism that checks remaining milestones and delivers the next step before permitting final completion transitions
- [ ] When a resource is managed through a progressive stage-by-stage delivery channel, the HLS must explicitly partition it from general direct-query collections and define redirection feedback for direct access attempts

## Common pitfalls
- [ ] Floating directives — a behavior executes a task based on an instruction whose storage and extraction are undefined
- [ ] Ungated completion — an advancement behavior terminates cleanly even when validation criteria were unmet
- [ ] Broken chain of custody — an input is received by an orchestrator but never forwarded to the sub-component that consumes it
- [ ] Unconfigured Conditionals — a component branches behavior on a condition (e.g. "fails if space laser is armed") that cannot be logically derived from its formally configured types
- [ ] Orphan Requirements — stating a requirement on an instantiated type that lacks the Knowledge grounding to enforce it, without supplying a collaborator that does
- [ ] Implicit State Ownership — a component guarantees mutating a state (e.g. "fuel level") that is not explicitly declared as part of its top-level Knowledge boundary
- [ ] Defensive checking anti-pattern — demanding validation checks for qualities an operation naturally expects of its inputs, when checking is not an explicit requirement
- [ ] Union output ambiguity — an operation yields an umbrella type leaving downstream callers unable to deterministically interact with the result
- [ ] Unnarrowed access violation — assuming unrestricted access to an entity whose access is explicitly narrowed or gated by sub-bullet requirements
- [ ] Redundant negative invariant — stating an explicit prohibition on an action that is already impossible by omission from the domain boundary
- [ ] Leaked implementation mechanic — specifying internal formatting, host-path sanitization, or string masking as domain requirements on an interface
- [ ] Redundant interface duplication — an implementation specification repeats baseline factory constructions, provided capabilities, or contracts already guaranteed by its interface specification
- [ ] Collaborator micromanagement — specifying the procedural invocation of an in-scope collaborator (such as "R using X") rather than stating the domain outcome R that the known collaborator grounds
- [ ] Redundant conjunct conflation — joining synonymous terms or subsets with conjunctions ("or", "and") where the second conjunct adds no new concept, creating false distinctions or implying phantom domain states (e.g. "unmapped or nonexistent")
- [ ] Fictitious dispatch layer — specifying an aggregator or composite provider as dispatching or proxying runtime operations when it merely combines or provisions items to a consumer that invokes them directly
- [ ] Procedural parameter forwarding — micromanaging step-by-step intermediate factory invocations and argument passing that can be transitively resolved by the component's known factories and configuration
- [ ] Definition-only phantom — declaring a type in `## Types` and listing it on a configuration or component without a concrete derivation path for how its runtime value is produced or resolved from available inputs
