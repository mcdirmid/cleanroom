<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T17:55:00Z
CHANGE: Define workspace_stub_impl planning specification
CODE_HASH: 8f4bbbdb8f4d
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_stub_impl implementation component

## Intent

Operating test subagents in hermetic role workspaces requires robust stub synthesis that parses Python interface and implementation typing stubs (.pyi), extracts class, method, function, and parameter signatures, strips type annotations for runtime compatibility, emits stub implementations raising NotImplementedError, and synchronizes stubs when specifications are modified. The workspace_stub_impl implementation component consolidates these AST and filesystem operations into a singleton service operating in the agent session lifecycle tier.

## Factored Contracts

### Typing

- The workspace stub synthesizer realization implements WorkspaceStubSynthesizer and operates in agent_session.

### Contracts

- The realization parses .pyi specification files into AST representations, extracts functions and classes, unparses parameters without type annotations, and emits valid test stub Python modules raising NotImplementedError with read-only permissions. [realize_stub_generation]
- The realization synchronizes test stubs across declared stub role dependencies for a workspace, comparing modification timestamps against source specifications and generating missing or updated stubs. [realize_stub_sync]
- The realization matches relative file paths against declared patterns of roles in stub role dependencies. [realize_stub_dep_matching]
- The realization inspects file headers to verify Cleanroom test stub marker headers. [realize_stub_validation]

### Woven Contracts

- When generating stubs, the realization parses AST trees and writes read-only stub files. [realize_stub_generation, workspace_stub: [generate_readonly_test_stub]]
- When synchronizing stubs, the realization scans dependencies, validates stubs, and regenerates out-of-date stubs. [realize_stub_sync, realize_stub_generation, realize_stub_validation, workspace_stub: [sync_all_stub_deps, is_valid_test_stub], workspace_registry: [resolve_role_definition]]
- When matching files, the realization evaluates role pattern globs. [realize_stub_dep_matching, workspace_stub: [is_stub_dep_file], workspace_registry: [resolve_role_definition]]

## Grounding

### Knowledge Provisions

- AST test stub generation and dependency synchronization realization. [workspace_stub_realization]

### Inherited Deferred Requirements

- AST parsing and file generation of test stubs on disk.
  - Grounded: [workspace_stub_realization, workspace_registry: [workspace_registry_service]]

### Knowledge Requirements

- Role definition resolution and stub dependency pattern matching.
  - Grounded: [workspace_registry: [workspace_registry_service]]
