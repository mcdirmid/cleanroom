# roles_impl implementation component

imports: session
implements: roles

## Purpose

The roles_impl implementation component realizes role configuration parsing, declarative constraint verification, and methodology-scoped role resolution.

Parsing role configuration declarations from diverse TOML and repository build files requires deterministic AST evaluation, schema normalization, and dependency rule enforcement. Without a unified implementation component, workspace provisioning and execution coordination risk duplicating parsing logic, bypassing auditor validation, and mishandling methodology inheritance. The roles_impl implementation component provides concrete algorithms to parse configuration documents, validate declaration constraints, normalize role patterns into glob filters, and discover package methodology bindings.

**Out of scope:** The roles_impl implementation component does not provision directory working trees, copy workspace files, or synchronize source changes; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

An agent session's *role resolver* realizes role configuration resolution and validation as a session service.

The role resolver parses role declarations from declarative configuration files (`cleanroom_roles.toml`), in-memory cache, bundled runner zipapp archives, or build file AST representations, normalizing source path patterns into writable and read-only glob patterns, extracting declared common specification roles, and decoupling tool execution from workspace root configuration files. It parses fused role declarations combining multiple constituent roles, deriving unioned writable file patterns, unioned readonly file patterns, and unioned tools from the constituent roles while preserving constituent role identifiers.

The role resolver validates declaration constraints across role dependencies, failing when feedback or star dependencies are duplicated in role dependencies, when dependencies are declared as both active and silent, or when auditor roles are declared outside silent role dependencies.

The role resolver discovers methodology and pipeline configurations across directory scopes by inspecting package configuration files and parent package hierarchies, caching parsed role definitions against configuration file modification timestamps, and filtering listed roles according to the scope's active pipeline (e.g. pretense vs standard).

The role resolver resolves role definitions for unqualified role names and qualified role addresses, qualifying role definitions with their requested role addresses upon resolution.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T20:38:00Z
LAST_CHANGED: 2026-10-29T00:40:00Z
CHANGE: Parse and extract common specification roles in role resolver
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
