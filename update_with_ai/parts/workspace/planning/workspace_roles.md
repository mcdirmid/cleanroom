<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:45:00Z
CHANGE: Define workspace_roles planning specification
CODE_HASH: 4612414b158c
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_roles interface component

## Intent

Managing autonomous development roles requires consistent mapping between role configurations, declared dependencies, and methodology specifications. Without a dedicated role configuration interface, tools and orchestrators risk redundant parsing, uncoordinated dependency constraint validation, and inconsistent role address resolution. The workspace_roles interface component establishes standard models for role configuration and provides uniform operations to resolve role definitions, validate declaration constraints, and list declared roles across repository packages and methodologies.

## Factored Contracts

### Typing

- A role definition record encapsulates a role name, a role address when explicitly targeted, a guide path, a starter template path when defined, a template command when dynamic scaffolding applies, a source pattern, writable file patterns, read-only file patterns, role dependencies, star role dependencies, silent role dependencies, stub role dependencies, silent cross-role dependencies, feedback role dependencies, active component types, a verification template, a verification success message, a persona, workspace files, tools, an audit tag when the role performs auditing, and a task prompt when custom instructions apply.
- An agent session's role resolver resolves role specifications and validates role configurations.

### Contracts

- The role resolver resolves role definitions dynamically from repository role configuration files or build files. [resolve_role_definition]
- The role resolver lists all declared role definitions from repository role configuration files or build files. [list_all_role_definitions]
- The role resolver raises an explicit failure when a queried role is undeclared or violates a declaration constraint. [fail_on_undeclared_or_invalid_role]
- When resolving an unqualified role definition within a directory scope, the role resolver discovers the methodology configuration bound to that directory scope or its package hierarchy and loads the role definitions that methodology declares. [resolve_unqualified_role_via_methodology]
- When resolving a qualified role address, the role resolver loads the role definitions declared by the addressed package. [resolve_qualified_role_address]
- The role resolver rejects role definitions containing redundant role dependency declarations. [reject_redundant_role_dependencies]
- The role resolver rejects role definitions declaring a dependency as a role dependency and a silent role dependency. [reject_conflicting_silent_role_dependencies]
- The role resolver rejects role definitions declaring an auditor role in role dependencies, star role dependencies, or feedback role dependencies. [reject_auditor_role_dependencies]

### Woven Contracts

- When resolving or listing role configurations, the resolver loads role definitions dynamically from repository role configuration files or build files, resolving unqualified roles through their bound methodology and qualified role addresses through the addressed package, rejecting configurations with redundant role dependencies, conflicting silent role dependencies, or non-silent auditor role dependencies. [resolve_role_definition, list_all_role_definitions, resolve_unqualified_role_via_methodology, resolve_qualified_role_address, reject_redundant_role_dependencies, reject_conflicting_silent_role_dependencies, reject_auditor_role_dependencies]

## Grounding

### Knowledge Provisions

- Role definition resolution and constraint validation services. [role_resolution_service]

### Knowledge Requirements

- Parsing of declarative role configuration files and build files.
  - Deferred: Provided by workspace roles implementation.
