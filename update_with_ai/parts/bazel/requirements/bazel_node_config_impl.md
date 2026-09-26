# bazel_node_config_impl implementation component

imports: bazel_manifest_loader, dag_storage, agent_file_alias, file_paths, agent_config, agent_node_config, tool_provider
implements: agent_node_config, agent_file_alias

## Assumptions and Requirements

### Requirements

1. The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.
2. The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.
3. Whether the node allows step mode resolved when the session contains exactly one node.
4. Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.
5. The session guide file and task guide from the single active node when guide step mode is active.
6. The session template parameters combining template parameters across the active nodes.
7. The session blame targets by node mapping each active node to its declared blame targets.
8. The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.
9. The session src file alias by node mapping each active node to the relative path of its declared source file alias.
10. The session verification success message from the active node when the session contains exactly one node.
11. The session feedback combining feedback messages retrieved from graph storage across the active nodes.
12. The session per node info by node mapping each active node to its per node info.
13. The alias manager converts relative paths to matching file aliases, producing unbound files when unmapped or ambiguous.
14. The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its relative path, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking, stripping workspace root path prefixes, and stripping execution root path prefixes.

## Grounding Facts

### Knowledge Needed

- Active nodes in session.
- Manifest data from `bazel_manifest_loader`.
- Step mode configuration from `agent_config`.
- Workspace root and execution root prefixes.
- Feedback messages from `dag_storage`.

### Actions Needed

- Aggregate read-only and read-write files across active nodes.
- Determine step mode activation and provide guide.
- Combine templates, parameters, and blame targets.
- Convert relative paths to file aliases and sanitize text via regex masks.
