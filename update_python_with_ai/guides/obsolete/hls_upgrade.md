# Guide: Upgrading High-Level Specifications (HLS)

## Summary

The artifact is an existing High-Level Specification (`high/<name>.md`) being upgraded to the new capability-driven modular format. The reader restructures the `## Behavior` section to group all operations under `### <Capability Name>` headings, and writes a natural language Grounding Declaration as the first prose block in each section.

No new behavior is invented, and no existing rules are dropped. The structural changes make grounding checks visually obvious and eliminate flat lists of ungrounded rules. The specification retains its declarative nature without relying on brackets or code tokens.

## Structural requirements

- [ ] Every behavioral rule in the artifact's `## Behavior` section is moved under a `### <Capability Name>` sub-heading
- [ ] No bare bullet points (`- `) are permitted directly under the main `## Behavior` heading
- [ ] The first non-empty line under each `### <Capability Name>` heading is a prose **Grounding Declaration** paragraph, never a bullet point
- [ ] Existing `## Purpose` and `## Types` sections are preserved and their contents are not moved to `## Behavior`

## Grounding Declarations

- [ ] The **Grounding Declaration** explicitly declares all inputs the capability consumes
- [ ] The declaration explicitly states the source or provenance of each consumed input (e.g., from the caller, extracted from a payload, retrieved from storage)
- [ ] The declaration explicitly states all primary outcomes or artifacts produced by the capability
- [ ] For operations that advance a workflow stage or conclude execution, the declaration states the explicit gating conditions required for the transition
- [ ] The declaration is written as plain English prose (e.g., "To execute a run, the *agent runner* consumes a *conversation history* from the caller and yields an *agent outcome*")
- [ ] The declaration references types using italics (`*type name*`) as per standard HLS rules

## Content preservation

- [ ] Every rule, constraint, and condition from the original `## Behavior` section is preserved in the new structure
- [ ] No original terms, capability names, or failure outcomes are dropped during the restructure
- [ ] If a rule does not cleanly fit into an obvious capability, it is placed in a logically related section or a dedicated section (e.g., `### Initialization`, `### Internal Invariants`) rather than being deleted

## Lint checks

- [ ] `###` headings are only permitted under the `## Behavior` section
- [ ] Behavioral rules (bullets starting with `- `) under `## Behavior` must reside within a `### <Capability Name>` section, never bare under the main heading
- [ ] The first block under a `### <Capability Name>` heading must be a prose block (not a bullet starting with `- `)
