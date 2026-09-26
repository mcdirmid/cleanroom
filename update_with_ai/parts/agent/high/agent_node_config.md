# agent_node_config interface component

imports: agent_session, agent_file_alias, dag_storage

## Purpose

The agent_node_config interface component defines session-level environment and configuration parameters for target nodes in agent sessions.

Multi-step agent workflows execute under varying constraints—such as source isolation, dependency boundaries, starter templates, and blame tracking. If individual session tools and services each define independent configuration channels, orchestrators must duplicate initialization logic and risk parameter skew across interdependent components. The agent_node_config interface component establishes a unified configuration boundary that exposes file permissions, templates, guidance parameters, and defect attribution targets through a single ambient session service.

**Out of scope:** The agent_node_config interface component does not parse build manifests, validate file permissions, or initialize session services; these are handled by other components.

## Types and Behavior

A *step section* is a milestone section within a guide having an index, a title, and content.

A *node guide* provides structured instructional text containing a summary, sequential step sections, and verification failure instructions.

A *verification check* can verify session criteria, communicating whether verification passed and diagnostic feedback on failure.

The *role config* of an agent session provides the role of the session, the sequence of nodes currently being cleaned, and an execution version that increments whenever the cleaned nodes change. The role config can set nodes to configure the nodes currently being cleaned in the agent session and increment the execution version.

The *session config* of an agent session service provides resolved configuration parameters for the active session. The session config provides:

- The session read-only files, restricting bound files to read.

- The session read-write files representing the nodes in the session, permitting bound files for read and write.

- When step mode is active, the session guide.

- The session templates, mapping read-write files to initial file content.

- The session template parameters, providing parameter bindings for template evaluation.

- The session verification checks evaluated during session verification.

- The session verification success message that is used to communicate feedback when verification passes.

- The session blame targets, mapping each read-write file to its eligible blame target read-only files.

- The session messages, mapping each read-write file to incoming messages explaining why it requires cleaning.
