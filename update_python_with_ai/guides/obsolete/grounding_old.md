# Guide: Specification Grounding and Custody

## Summary

The artifact is a high-level specification evaluated for grounding, input provenance, and state transition integrity. Every domain entity, input directive, factory configuration, and lifecycle transition in the specification must be grounded: every consumed input or directive traces to an explicit source, and every state advancement or completion outcome is gated on verifiable conditions.

Code and specifications fail when operations assume the existence of configuration, context, or instructions that were never produced, passed, or stored. An auditor evaluating a specification traces the chain of custody for all dynamic inputs and verifies that operational outcomes are strictly gated.

The section inventory is closed:
- ## Summary
- ## Input and directive grounding
- ## Factory and configuration custody
- ## State transition and outcome gating
- ## Common pitfalls

---

## Input and directive grounding

- [ ] Every input parameter, directive, instruction, or configuration consumed by an operation has an explicitly declared source in `## Behavior` (such as retrieved from a storage repository, extracted from an incoming record, or supplied as an argument)
- [ ] Operations that initialize execution contexts or session state explicitly specify the originating records, stored templates, or incoming payloads that populate the context
- [ ] Multi-attribute entity declarations maintain all declared fields across pipeline hops without dropping sub-attributes
- [ ] Standalone validators, analyzers, and interceptors have explicit consumers and callers in the operational pipeline, preventing disconnected verification logic
- [ ] No operational rule relies on floating inputs, implicit prompts, or phantom directives with no declared source
- [ ] When an entity is queried or manipulated by an identifier, the repository, catalog, or collection maintaining that entity is defined or imported
- [ ] Operations that resolve symbolic identifiers, external references, or metadata keys to storage entities or filesystem locations explicitly state the resolution and extraction mechanism
- [ ] Specifications consuming instructional sequences or milestone documents explicitly specify the complete pipeline from reference identifier to content extraction, milestone parsing, and delivery to the active context
- [ ] An HLS defining virtual identifiers or abstract resource representations explicitly specifies output sanitization rules ensuring all query results, discovery outputs, and diagnostic feedback use virtual identifiers rather than leaking concrete environment details
- [ ] An HLS resolving relative locations or environmental paths explicitly specifies base root anchoring to guarantee deterministic resolution across differing execution environments
- [ ] An HLS that seeds synthetic interaction history or pre-constructed event records explicitly specifies that every synthetic entry references a valid, defined schema operation rather than placeholder or phantom identifiers

## Factory and configuration custody

- [ ] Whenever a component is created dynamically through a factory operation, `## Behavior` explicitly declares the source of the configuration passed to the factory
- [ ] The entity providing the dynamic configuration is imported and wired to the consuming component
- [ ] Configuration parameters required by a factory operation are fully populated by the originating source without missing or undefined fields
- [ ] Factory creation operations never create components from floating or ungrounded configuration objects
- [ ] Storage repositories store and serve records populated by dedicated loaders, without conflating parsing responsibilities with storage management
- [ ] Coordinating components that instantiate shared dependencies explicitly forward them through all intermediate layers to the downstream components that consume them
- [ ] Virtual identifiers mapped to concrete resources define unambiguous resolution and disambiguation rules
- [ ] When a resource is managed through a progressive stage-by-stage delivery channel, the HLS explicitly partitions it from general direct-query collections and defines redirection feedback for direct access attempts

## State transition and outcome gating

- [ ] Every operation that advances a workflow stage, mutates a lifecycle state, or concludes execution explicitly states the gating conditions required for the transition
- [ ] Completion and advancement operations are gated on observable criteria (such as validated state modifications, non-empty outputs, or passing verification checks), preventing unverified no-op transitions
- [ ] Operations providing incremental stepping deliver remaining steps or corrective feedback rather than concluding execution prematurely
- [ ] Failure paths, cycle detections, and permission violations explicitly produce recovery feedback, emit error outcomes, or preserve unresolved state
- [ ] Operations that record events to an observer or sink explicitly specify the construction and dispatch of event records for each observed transition
- [ ] Workflows providing progressive milestone delivery explicitly define the interception mechanism that checks remaining milestones and delivers the next step before permitting final completion transitions

## Common pitfalls

- [ ] Floating directives — an operation executes a task based on an instruction or directive whose storage, extraction, and delivery are nowhere defined
- [ ] Ungrounded factory creation — calling a factory operation without specifying where the configuration data originates or how it was retrieved
- [ ] Ungated completion — providing an advancement or completion operation that terminates cleanly even when no work was performed or validation criteria were unmet
- [ ] Broken chain of custody — an input or dependency is received by an orchestrator but never forwarded to the sub-component that needs to consume it
- [ ] Disconnected validators — defining a validation or analysis component without specifying where and when it is invoked in the workflow
- [ ] Storage and loader conflation — a storage component claims to parse external formats directly instead of storing records populated by an imported loader
- [ ] Phantom context initialization — an execution context is initialized with empty or partial state because the loader failed to record necessary parameters
- [ ] Unresolved symbolic references — treating an external reference or symbolic key as a resolved resource without specifying its extraction and lookup mechanism
- [ ] Unintercepted milestone delivery — declaring a step-by-step guidance service without specifying how workflow advancement intercepts progression before concluding
- [ ] Unsanitized abstraction boundaries — an operation exposes concrete underlying resource paths in outputs or error feedback instead of mapping them to virtual identifiers
- [ ] Unanchored relative locations — an operation attempts to resolve relative resource paths without defining the root environment or base directory to anchor against
- [ ] Conflicting delivery channels — exposing a staged or progressive resource in general query collections without defining exclusive delivery and redirection rules
- [ ] Phantom protocol identifiers — seeding synthetic interaction history with placeholder operation names that do not correspond to valid defined protocol operations
