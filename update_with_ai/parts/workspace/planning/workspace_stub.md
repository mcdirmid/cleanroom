<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T17:55:00Z
CHANGE: Define workspace_stub planning specification
CODE_HASH: cdda05c3db16
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_stub interface component

## Intent

Test authoring subagents require concrete Python module files to import when writing and executing unit tests without exposing real implementation details. Synthesizing read-only test stubs that reflect method signatures from .pyi specifications while raising NotImplementedError ensures that unit tests test against specification contracts without relying on implementation code. The workspace_stub interface component establishes contracts for stub synthesis, dependency path matching, and synchronization across role workspaces.

## Factored Contracts

### Typing

- An agent session's workspace stub synthesizer provides test stub generation and dependency synchronization.

### Contracts

- The workspace stub synthesizer generates read-only test stubs from companion typing specifications, preserving class, function, and method signatures while raising NotImplementedError, rewriting imports to isolate test dependencies, and injecting missing interface methods. [generate_readonly_test_stub]
- The workspace stub synthesizer synchronizes read-only test stubs for role workspaces declaring stub role dependencies, updating stubs when companion specifications change and purging orphaned stubs. [sync_all_stub_deps]
- The workspace stub synthesizer determines whether a relative file path matches any declared role in a role's stub role dependencies. [is_stub_dep_file]
- The workspace stub synthesizer checks whether an existing file on disk is a valid cleanroom test stub. [is_valid_test_stub]

### Woven Contracts

- When synchronizing stub dependencies, the synthesizer validates existing stubs, compares specification timestamps, and generates read-only test stubs. [generate_readonly_test_stub, sync_all_stub_deps, is_valid_test_stub]
- When checking candidate files, the synthesizer matches file paths against stub dependency roles. [is_stub_dep_file, workspace_registry: [resolve_role_definition]]

## Grounding

### Knowledge Provisions

- Test stub generation, AST parsing, and dependency synchronization services. [workspace_stub_service]

### Knowledge Requirements

- Role definition resolution and stub dependency pattern matching.
  - Grounded: [workspace_registry: [workspace_registry_service]]
- AST parsing and file generation of test stubs on disk.
  - Deferred: Provided by workspace stub synthesizer implementation.
