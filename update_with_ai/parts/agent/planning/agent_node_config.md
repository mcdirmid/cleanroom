<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T05:27:33Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 41ff7effe9e8
-->

# agent_node_config interface component

imports: agent_session, agent_file_alias, dag_storage

## Intent

Multi-step agent workflows execute under varying constraints—such as source isolation, dependency boundaries, starter templates, and blame tracking. If individual session tools and services each define independent configuration channels, orchestrators must duplicate initialization logic and risk parameter skew across interdependent components. The agent_node_config interface component establishes a unified configuration boundary that exposes file permissions, templates, guidance parameters, and defect attribution targets through a single ambient session service.

By centralizing role execution versions and providing structured representations for node guides, verification criteria, and template parameters, the component anchors all downstream session tools to a coherent operational state.

## Factored Contracts

### Typing

- A step section has an index.
- A step section has a title.
- A step section has content.
- A node guide provides a summary.
- A node guide provides sequential step sections.
- A node guide provides verification failure instructions.
- The role config provides the role of the session.
- The role config provides the sequence of nodes currently being cleaned.
- The role config provides an execution version.

### Contracts

- A verification check communicates whether verification passed. [verification_check_passed]
- A verification check communicates diagnostic feedback on failure. [verification_check_feedback]
- The role config sets the role of the session. [role_config_set_role]
- The role config sets the sequence of nodes currently being cleaned in the session. [role_config_set_nodes]
- Setting nodes in the role config increments the execution version. [set_nodes_increments_version]
- The session config provides the session read-only files. [session_config_read_only_files]
- The session config provides the session read-write files representing cleaned nodes. [session_config_read_write_files]
- The session config provides the session guide when step mode is active. [session_config_guide]
- The session config provides session templates mapping read-write files to initial file content. [session_config_templates]
- The session config provides session template parameters for template evaluation. [session_config_template_params]
- The session config provides session verification checks evaluated during verification. [session_config_verification_checks]
- The session config provides the session verification success message. [session_config_verification_success_msg]
- The session config provides session blame targets mapping read-write files to blame target read-only files. [session_config_blame_targets]
- The session config provides session messages mapping read-write files to incoming messages. [session_config_messages]

## Woven Contracts

- Configuring the role of the session in the role config sets the session role. [role_config_set_role]
- Setting the nodes being cleaned in the role config updates the active node sequence and increments the execution version. [role_config_set_nodes, set_nodes_increments_version]
- The session config exposes declared read-only and read-write bound files anchoring file permissions to active nodes. [session_config_read_only_files, session_config_read_write_files]
- When verification criteria fail, the verification check communicates diagnostic feedback describing the failure. [verification_check_passed, verification_check_feedback]
