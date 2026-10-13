<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_coordinator interface specification
CODE_HASH: 987d185fc071
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# antigravity_coordinator interface component

imports: agent_session, subagent_coordinator

## Purpose

The antigravity_coordinator interface component defines data types and operational contracts for generating, installing, and formatting zero-execution Cleanroom coordinator skills and subagent dispatch directives for Google Antigravity.

Coordinating multi-agent workflows inside an interactive desktop IDE requires specialized skills and dispatch formats that prevent context pollution and enforce physical workspace boundaries. The antigravity_coordinator interface component formalizes coordinator skill generation, subagent invocation payload synthesis, and reactive completion notification parsing.

**Out of scope:** The antigravity_coordinator interface component does not directly execute subagent subprocesses or mutate source files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; role dispatch definitions and turn result models are delegated to subagent_coordinator.

## Types and Behavior

A *subagent dispatch specification* captures the parameters required to invoke an Antigravity subagent, including the subagent type name, role identifier, task prompt, pinned workspace directory, and model tier.

A *coordinator skill document* encapsulates the generated YAML frontmatter and instructional markdown content of the Cleanroom coordinator skill.

A *wake notification message* captures structured turn results parsed from a subagent completion message, including action status, role name, submitted targets, blamed targets, and failure diagnostics.

A system's *antigravity coordinator generator* creates coordinator skills and formats subagent dispatch payloads.

When generating the coordinator skill:

- The antigravity coordinator generator produces skill content that instructs the coordinator subagent to inspect DAG work queues for ready nodes and dispatch or message role workers via subagent invocation.

- The antigravity coordinator generator embeds requirements that strictly forbid inheriting the supervisor workspace and require pinning the workspace directory to the provisioned role workspace.

- The antigravity coordinator generator formats subagent dispatch specifications for ready roles identified in an execution wave, instructing workers to drain ready nodes and resolve them via submission, blame attribution, or failure diagnostics.

- The antigravity coordinator generator parses wake notification messages received from subagent turns to extract completed, blamed, and failed targets.
