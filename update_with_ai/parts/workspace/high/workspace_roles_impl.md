<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:45:00Z
CHANGE: Define workspace_roles_impl implementation component
CODE_HASH: b0f6828adf80
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_roles_impl implementation component

imports: agent_session
implements: workspace_roles

## Purpose

The workspace_roles_impl implementation component realizes role configuration parsing, declarative constraint verification, and methodology-scoped role resolution.

Parsing role configuration declarations from diverse TOML and repository build files requires deterministic AST evaluation, schema normalization, and dependency rule enforcement. Without a unified implementation component, workspace provisioning and execution coordination risk duplicating parsing logic, bypassing auditor validation, and mishandling methodology inheritance. The workspace_roles_impl implementation component provides concrete algorithms to parse configuration documents, validate declaration constraints, normalize role patterns into glob filters, and discover package methodology bindings.

**Out of scope:** The workspace_roles_impl implementation component does not provision directory working trees, copy workspace files, or synchronize source changes; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

An agent session's *role resolver* realizes role configuration resolution and validation as a session service.

The role resolver parses role declarations from declarative configuration files or build file AST representations, normalizing source path patterns into writable and read-only glob patterns.

The role resolver validates declaration constraints across role dependencies, failing when feedback or star dependencies are duplicated in role dependencies, when dependencies are declared as both active and silent, or when auditor roles are declared outside silent role dependencies.

The role resolver discovers methodology configurations across directory scopes by inspecting package configuration files and parent package hierarchies, caching parsed role definitions against configuration file modification timestamps.

The role resolver resolves role definitions for unqualified role names and qualified role addresses, qualifying role definitions with their requested role addresses upon resolution.
