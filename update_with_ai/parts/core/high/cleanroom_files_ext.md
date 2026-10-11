<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T00:00:00Z
CHANGE: new file
CODE_HASH: 7fe87cd8ad60
-->

# cleanroom_files_ext external component

## Purpose

The cleanroom_files_ext external component defines the external filesystem schema, configuration file formats, and state marker conventions for Cleanroom workspaces.

Coordinating literate specifications, multi-role agent workspaces, and graph execution without monolithic build daemons requires reading and writing standardized configuration files and workspace state markers across directory hierarchies. Direct hardcoding of configuration file paths and schema structures in application logic couples domain code to ambient filesystem layouts and prevents uniform discovery. The cleanroom_files_ext external component encapsulates the layout conventions, file naming rules, and schema definitions for Cleanroom workspace files, providing external specification knowledge without coupling domain logic to file format implementations.

**Out of scope:** The cleanroom_files_ext external component does not parse TOML or JSON documents, locate files across directory hierarchies, or execute graph operations; these are handled by other components.

## Grounding Gaps Covered

The cleanroom_files_ext component provides external schema knowledge and naming conventions for Cleanroom configuration files, workspace descriptors, and execution state markers.

Grounding gaps covered include:

- Cleanroom methodology binding schema: Defines `cleanroom.toml`, containing the scoped `methodology` address attribute that binds a package hierarchy to its methodology specification package.

- Role definitions schema: Defines `cleanroom_roles.toml` and `cleanroom_python_roles.toml`, containing methodology metadata and the role definition table that specifies persona descriptions, source patterns, prompt templates, verification check templates, guide paths, step mode eligibility, component types, and role dependencies.

- Role workspace descriptor schema: Defines `.cleanroom_role.json`, containing provisioned role workspace attributes including role name, directory scope, and canonical repository root.

- Workspaces registry schema: Defines `.cleanroom_workspaces.json`, tracking active provisioned workspace directories and metadata records with file locking.

- Cleanroom event log schema: Defines `.cleanroom.log`, an append-only event log capturing recorded change descriptions and feedback messages within parts directories.
