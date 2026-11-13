# autofab_files_ext external component

## Purpose

The autofab_files_ext external component defines the external filesystem schema, configuration file formats, and state marker conventions for Autofab workspaces.

Coordinating literate specifications, multi-role agent workspaces, and graph execution without monolithic build daemons requires reading and writing standardized configuration files and workspace state markers across directory hierarchies. Direct hardcoding of configuration file paths and schema structures in application logic couples domain code to ambient filesystem layouts and prevents uniform discovery. The autofab_files_ext external component encapsulates the layout conventions, file naming rules, and schema definitions for Autofab workspace files, providing external specification knowledge without coupling domain logic to file format implementations.

**Out of scope:** The autofab_files_ext external component does not parse TOML or JSON documents, locate files across directory hierarchies, or execute graph operations; these are handled by other components.

## Grounding Gaps Covered

The autofab_files_ext component provides external schema knowledge and naming conventions for Autofab configuration files, workspace descriptors, and execution state markers. [autofab_files_schema, autofab_configuration_schema]

Grounding gaps covered include:

- Autofab methodology binding schema: Defines `autofab.toml`, containing the scoped `methodology` address attribute that binds a package hierarchy to its methodology specification package. In an Autofab project, `autofab.toml` should be present in the `parts` directory (not workspace).

- Role definitions schema: Defines `autofab_roles.toml`, containing methodology metadata and the role definition table that specifies persona descriptions, source patterns, prompt templates, verification check templates, guide paths, step mode eligibility, component types, and role dependencies.

- Role workspace descriptor schema: Defines `.autofab_role.json`, containing provisioned role workspace attributes including role name, directory scope, and canonical repository root.

- Autofab event log schema: Defines `.autofab.log`, an append-only event log capturing recorded change descriptions and feedback messages within parts directories.

- Pending work sequence schema: Defines `.autofab_pending_work.json`, tracking pending target strings queued for execution within a workspace session.

- Blame buffer schema: Defines `.autofab_blame_buffer.json`, buffering unacted diagnostic feedback messages and critiques for synchronization across workspaces.

- Audit buffer schema: Defines `.autofab_audit_buffer.json`, buffering uncommitted audit records and verification timestamps for multi-workspace synchronization.

- In-band metadata headers schema: Defines comment conventions and serialization format for in-band metadata blocks embedded directly into Python source files (`# --- AUTOFAB METADATA ---` through `# --- END AUTOFAB METADATA ---`) and Markdown specifications (`<!-- AUTOFAB METADATA` through `-->`), specifying lifecycle timestamps (`LAST_CLEANED`, `LAST_CHANGED`, audit timestamps) and change descriptions (`CHANGE`).

<!-- AUTOFAB METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-29T17:14:00Z
CHANGE: Rename Cleanroom to Autofab and update workspace files schema
-->
