<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T01:25:00Z
CHANGE: eliminate cleanroom_workspaces.json workspace registry file
CODE_HASH: 35d8c4f624c1
-->

# cleanroom_files_ext external component

## Purpose

The cleanroom_files_ext external component defines the external filesystem schema, configuration file formats, and state marker conventions for Cleanroom workspaces.

Coordinating literate specifications, multi-role agent workspaces, and graph execution without monolithic build daemons requires reading and writing standardized configuration files and workspace state markers across directory hierarchies. Direct hardcoding of configuration file paths and schema structures in application logic couples domain code to ambient filesystem layouts and prevents uniform discovery. The cleanroom_files_ext external component encapsulates the layout conventions, file naming rules, and schema definitions for Cleanroom workspace files, providing external specification knowledge without coupling domain logic to file format implementations.

**Out of scope:** The cleanroom_files_ext external component does not parse TOML or JSON documents, locate files across directory hierarchies, or execute graph operations; these are handled by other components.

## Grounding Gaps Covered

The cleanroom_files_ext component provides external schema knowledge and naming conventions for Cleanroom configuration files, workspace descriptors, and execution state markers.

Grounding gaps covered include:

- Cleanroom methodology binding schema: Defines `cleanroom.toml`, containing the scoped `methodology` address attribute that binds a package hierarchy to its methodology specification package. In a Cleanroom project, `cleanroom.toml` should be present in the `parts` directory (not workspace).

- Role definitions schema: Defines `cleanroom_roles.toml` and `cleanroom_python_roles.toml`, containing methodology metadata and the role definition table that specifies persona descriptions, source patterns, prompt templates, verification check templates, guide paths, step mode eligibility, component types, and role dependencies.

- Role workspace descriptor schema: Defines `.cleanroom_role.json`, containing provisioned role workspace attributes including role name, directory scope, and canonical repository root.

- Cleanroom event log schema: Defines `.cleanroom.log`, an append-only event log capturing recorded change descriptions and feedback messages within parts directories.

- Pending work sequence schema: Defines `.cleanroom_pending_work.json`, tracking pending target strings queued for execution within a workspace session.

- Blame buffer schema: Defines `.cleanroom_blame_buffer.json`, buffering unacted diagnostic feedback messages and critiques for synchronization across workspaces.

- Audit buffer schema: Defines `.cleanroom_audit_buffer.json`, buffering uncommitted audit records and verification timestamps for multi-workspace synchronization.

- In-band metadata headers schema: Defines comment conventions and serialization format for in-band metadata blocks embedded directly into Python source files (`# --- CLEANROOM METADATA ---` through `# --- END CLEANROOM METADATA ---`) and Markdown specifications (`<!-- CLEANROOM METADATA` through `-->`), specifying lifecycle timestamps (`LAST_CLEANED`, `LAST_CHANGED`, audit timestamps), change descriptions (`CHANGE`), and content hashes (`CODE_HASH`).
