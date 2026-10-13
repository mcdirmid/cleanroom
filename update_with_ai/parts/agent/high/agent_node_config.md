<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Replace the session config fragment lead-in with a declarative parameter inventory and canonicalize session terminology
CODE_HASH: 4a49596edaf5
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# agent_node_config interface component

imports: agent_session, agent_file_alias, dag_storage

## Purpose

The agent_node_config interface component defines session-level environment and configuration parameters for target nodes in agent sessions.

Multi-step agent workflows execute under varying constraints, such as source isolation, dependency boundaries, starter templates, and blame tracking. If individual session tools and services each define independent configuration channels, orchestrators must duplicate initialization logic and risk parameter skew across interdependent components. The agent_node_config interface component establishes a unified configuration boundary that exposes file permissions, templates, guidance parameters, and defect attribution targets through a single ambient session service.

**Out of scope:** The agent_node_config interface component does not parse build manifests, validate file permissions, or initialize session services; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; bound file kinds are delegated to agent_file_alias; node addressing is delegated to dag_storage.

## Types and Behavior

A *step section* is a milestone section within a guide having an index, a title, and content.

A *node guide* provides structured instructional text containing a summary, sequential step sections, and verification failure instructions.

A *verification check* evaluates session criteria and communicates whether verification passed together with diagnostic feedback for a failed verification.

An agent session's *role config* maintains the active session role, the sequence of nodes currently being cleaned, and an execution version that increments whenever the cleaned nodes change. The role config sets the role and updates the sequence of nodes being cleaned.

An agent session's *session config* provides the resolved configuration parameters of the active session.

The session config provides the read-only files restricting bound files to read, the read-write files permitting bound files for read and write, the session guide when step mode is active, the templates mapping read-write files to initial file content, the template parameters binding values for template evaluation, the verification checks evaluated during session verification, and the verification success message communicating feedback when verification passes.

The session config also provides the blame targets mapping each read-write file to the read-only files eligible for blame, and the session messages mapping each read-write file to incoming messages explaining why the file requires cleaning.
