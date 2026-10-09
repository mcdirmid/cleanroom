<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: 48fd2f167ae1
-->

# uv_manifest_ext external component

## Purpose

The uv_manifest_ext external component defines the external TOML role manifest schema and file layout conventions for Cleanroom Python workspaces.

Executing multi-role tasks without monolithic build system daemons requires reading declarative role definitions and package filesystem structures. Workspaces express methodology configurations through structured TOML files detailing role personas, source patterns, verification templates, and dependency chains. The uv_manifest_ext external component encapsulates the schema parsing and layout conventions for role configuration files and Cleanroom package directories, providing external deserialization knowledge without coupling domain logic to TOML parser internals.

**Out of scope:** The uv_manifest_ext external component does not locate files across directory hierarchies, resolve dependency closures, or populate graph storage; these are handled by other components.

## Grounding Gaps Covered

The uv_manifest_ext component provides external schema knowledge and deserialization mechanics for Cleanroom role definition TOML files and package file conventions.

Grounding gaps covered include:

- Role definition deserialization: Parses role manifest TOML files, exposing methodology metadata, role names, personas, source path patterns, prompt templates, guide target paths, step mode permissions, role dependency lists, star role dependency lists, silent role dependency lists, feedback role dependency lists, active component types, and verification check templates.

- Unit component type classification: Identifies unit component types from specification headers and front-matter clauses across interface, implementation, external boundary, and assembly categories.

- Package directory conventions: Maps canonical unit addresses to expected source locations within standardized Cleanroom package directory trees.
