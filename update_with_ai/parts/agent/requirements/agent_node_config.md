# agent_node_config interface component

imports: agent_session, agent_file_alias, dag_storage

## Assumptions and Requirements

### Requirements

1. A step section is a milestone section within a guide having an index, a title, and content.
2. A node guide provides structured instructional text containing a summary, sequential step sections, and verification failure instructions.
3. A verification check can verify session criteria, communicating whether verification passed and diagnostic feedback on failure.
4. The role config provides the role of the session.
5. The role config provides the sequence of nodes currently being cleaned.
6. The role config provides an execution version that increments whenever the cleaned nodes change.
7. The role config can set nodes to configure the nodes currently being cleaned in the agent session and increment the execution version.
8. The session config provides the session read-only files, restricting bound files to read.
9. The session config provides the session read-write files representing the nodes in the session, permitting bound files for read and write.
10. When step mode is active, the session config provides the session guide.
11. The session config provides the session templates, mapping read-write files to initial file content.
12. The session config provides the session template parameters, providing parameter bindings for template evaluation.
13. The session config provides the session verification checks evaluated during session verification.
14. The session config provides the session verification success message that is used to communicate feedback when verification passes.
15. The session config provides the session blame targets, mapping each read-write file to its eligible blame target read-only files.
16. The session config provides the session messages, mapping each read-write file to incoming messages explaining why it requires cleaning.

## Grounding Facts

### Knowledge Needed

- Session role and cleaned nodes sequence.
- Execution version counter.
- Read-only and read-write bound file sets.
- Session guide and step sections.
- Session templates and template parameters.
- Verification checks and success messages.
- Blame targets and incoming cleaning messages.

### Actions Needed

- Set cleaned nodes on role config and increment execution version.
- Provide session files, guides, templates, and verification checks.
- Resolve blame targets and messages for read-write files.
