# roles interface component

imports: session

## Purpose

The roles interface component defines data types and operational contracts for resolving role definitions and validating role configuration declarations.

Managing autonomous development roles requires consistent mapping between role configurations, declared dependencies, and methodology specifications. Without a dedicated role configuration interface, tools and orchestrators risk redundant parsing, uncoordinated dependency constraint validation, and inconsistent role address resolution. The roles interface component establishes standard models for role configuration and provides uniform operations to resolve role definitions, validate declaration constraints, and list declared roles across repository packages and methodologies.

**Out of scope:** The roles interface component does not compute workspace directory paths, provision filesystem working trees, or synchronize source files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *role definition* record encapsulates configuration for an autonomous development role: a *role name*, a *role address* when explicitly targeted, a *guide path*, a starter *template* path when defined, a *template command* when dynamic scaffolding applies, a *source pattern*, *writable file patterns*, *read-only file patterns*, *role dependencies*, *star role dependencies*, *silent role dependencies*, *stub role dependencies*, *silent cross-role dependencies*, *feedback role dependencies*, *common specification roles*, *active component types*, a *verification template*, a *verification success message*, a *persona*, *workspace files*, *tools*, an *audit tag* when the role performs auditing, and a *task prompt* when custom instructions apply.

An agent session's *role resolver* resolves role specifications and validates role configurations.

Role definitions obey three declaration constraints. Feedback role dependencies and star role dependencies are implicitly role dependencies, so neither is declared again under role dependencies, and a dependency is never declared as both a role dependency and a silent role dependency. An auditor role is declared only as a silent role dependency, never as a role dependency, a star role dependency, or a feedback role dependency.

The role resolver resolves a role definition and lists every declared role definition from declarative role configuration files or repository build files, raising an explicit failure when a queried role is undeclared or when a role definition violates a declaration constraint. When resolving an unqualified role definition within a directory scope, the resolver discovers the methodology configuration bound to that directory scope or its package hierarchy and loads the role definitions declared by that methodology. When resolving a qualified role address, the resolver loads role definitions declared by the addressed package.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-29T00:40:00Z
CHANGE: Add common specification roles to role definition record
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
