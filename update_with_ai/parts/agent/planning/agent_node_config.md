<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-11T03:01:17Z
CHANGE: Align role and session config typing and canonicalize bound file, blame target, and message terminology; drop planning front-matter
CODE_HASH: 414587ff3962
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# agent_node_config interface component

## Intent

Multi-step agent workflows execute under varying constraints—such as source isolation, dependency boundaries, starter templates, and blame tracking. If individual session tools and services each define independent configuration channels, orchestrators must duplicate initialization logic and risk parameter skew across interdependent components. The agent_node_config interface component establishes a unified configuration boundary that exposes file permissions, templates, guidance parameters, and defect attribution targets through a single ambient session service.

By centralizing role execution versions and providing structured representations for node guides, verification criteria, and template parameters, the component anchors all downstream session tools to a coherent operational state.

## Factored Contracts

### Typing

- A step section is a milestone section within a guide having an index, a title, and content.
- A node guide provides structured instructional text containing a summary, sequential step sections, and verification failure instructions.
- A verification check evaluates session criteria.
- A verification check communicates whether verification passed together with diagnostic feedback for a failed verification.
- An agent session's role config maintains the active session role.
- An agent session's role config maintains the sequence of nodes currently being cleaned.
- An agent session's role config maintains an execution version that increments whenever the cleaned nodes change.
- An agent session's session config provides the resolved configuration parameters of the active session.

### Contracts

- A verification check communicates whether verification passed. [verification_check_passed]
- A verification check communicates diagnostic feedback on failure. [verification_check_feedback]
- The role config sets the role of the session. [role_config_set_role]
- The role config sets the sequence of nodes currently being cleaned in the session. [role_config_set_nodes]
- Setting nodes in the role config increments the execution version. [set_nodes_increments_version]
- The session config provides the session read-only files restricting bound files to read access. [session_config_read_only_files]
- The session config provides the session read-write files permitting bound files for read and write access. [session_config_read_write_files]
- The session config provides the session guide when step mode is active. [session_config_guide]
- The session config provides session templates mapping read-write files to initial file content. [session_config_templates]
- The session config provides session template parameters for template evaluation. [session_config_template_params]
- The session config provides session verification checks evaluated during verification. [session_config_verification_checks]
- The session config provides the session verification success message. [session_config_verification_success_msg]
- The session config provides session blame targets mapping each read-write file to the read-only files eligible for blame. [session_config_blame_targets]
- The session config provides session messages mapping each read-write file to incoming messages explaining why the file requires cleaning. [session_config_messages]

### Woven Contracts

- Configuring the role of the session in the role config sets the session role. [role_config_set_role]
- Setting the nodes being cleaned in the role config updates the active node sequence and increments the execution version. [role_config_set_nodes, set_nodes_increments_version]
- The session config exposes declared read-only and read-write bound files anchoring file permissions to active nodes. [session_config_read_only_files, session_config_read_write_files]
- When verification criteria fail, the verification check communicates diagnostic feedback describing the failure. [verification_check_passed, verification_check_feedback]

## Grounding

### Knowledge Provisions

- Session-scoped node configuration, file permissions, guides, templates, and verification checks. [node_configuration_service]

### Knowledge Requirements

- Session role configuration and active cleaned nodes.
  - Deferred: Provided by session orchestrator in implementation.
- Read-only and read-write bound file declarations for active session nodes.
  - Deferred: Derived from graph storage targets in implementation.
