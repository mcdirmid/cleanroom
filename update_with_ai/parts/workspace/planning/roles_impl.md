# roles_impl implementation component

## Intent

The roles_impl implementation component provides concrete algorithms to parse configuration documents, validate declaration constraints, normalize role patterns into glob filters, and discover package methodology bindings.

## Factored Contracts

### Contracts

- The role resolver parses role declarations from declarative TOML configuration files, in-memory cache, or bundled runner zipapps, extracting common specification roles. [parse_role_toml_files]
- The role resolver parses fused role declarations combining constituent roles, unioning writable and readonly patterns, and associating constituent role names. [parse_fused_role_declarations]
- The role resolver evaluates role declarations from repository build file AST structures when TOML files are absent. [evaluate_build_file_ast]
- The role resolver enforces declaration rules rejecting redundant, conflicting, or non-silent auditor dependencies. [validate_dependency_declarations]
- The role resolver discovers package methodology and pipeline configurations across directory scope hierarchies, filtering listed roles according to active pipeline bindings. [discover_package_methodologies]
- The role resolver qualifies resolved role definitions with requested target role addresses. [qualify_resolved_role_address]
- The role resolver caches parsed role definitions against file modification timestamps. [cache_parsed_role_definitions]

### Woven Contracts

- When resolving role definitions, the resolver evaluates TOML or build file AST declarations, discovers methodologies, parses fused role declarations, validates dependency constraints, qualifies role addresses, and caches results. [parse_role_toml_files, parse_fused_role_declarations, evaluate_build_file_ast, discover_package_methodologies, validate_dependency_declarations, qualify_resolved_role_address, cache_parsed_role_definitions, roles: [resolve_role_definition, list_all_role_definitions, resolve_unqualified_role_via_methodology, resolve_qualified_role_address, reject_redundant_role_dependencies, reject_conflicting_silent_role_dependencies, reject_auditor_role_dependencies]]

## Grounding

### Knowledge Provisions

- AST evaluation, TOML parsing, and dependency validation mechanics. [role_declaration_evaluation]

### Inherited Deferred Requirements

- Parsing of declarative role configuration files and build files.
  - Grounded: [role_declaration_evaluation]

### Knowledge Requirements

- Declarative role configurations and package build files on disk.
  - Grounded: [role_declaration_evaluation]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T20:38:00Z
LAST_CHANGED: 2026-10-29T00:40:00Z
CHANGE: Parse and extract common specification roles in role resolver
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
