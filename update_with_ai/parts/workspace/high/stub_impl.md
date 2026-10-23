# stub_impl implementation component

imports: session, role_registry, stub
implements: stub

## Purpose

The stub_impl implementation component realizes AST-based test stub synthesis, dependency path matching, and stub synchronization from `.pyi` specifications for role workspaces.

Operating test subagents in hermetic role workspaces requires robust stub synthesis that parses Python interface and implementation typing stubs (`.pyi`), extracts class, method, function, and parameter signatures, strips type annotations for runtime compatibility, emits stub implementations raising `NotImplementedError`, and synchronizes stubs when specifications are modified. The stub_impl implementation component consolidates these AST and filesystem operations into a singleton service operating in the agent session lifecycle tier.

**Out of scope:** The stub_impl implementation component does not commission workspace directory structures or configure runner scripts; these are handled by provision_impl.

**Delegated:** Session tier scoping is delegated to agent_session; role definition resolution is delegated to role_registry.

## Types and Behavior

The workspace stub synthesizer realization implements AST stub synthesis and synchronization.

The realization:

- Parses `.pyi` specification files into AST representations, extracts functions and classes, unparses parameters without type annotations for compatibility, and emits valid test stub Python modules raising `NotImplementedError` with read-only permissions.

- Synchronizes test stubs across declared stub role dependencies for a workspace, comparing modification timestamps against source specifications and generating missing or updated stubs.

- Matches relative file paths against declared patterns of roles in stub role dependencies.

- Inspects file headers to verify Cleanroom test stub marker headers.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T17:55:00Z
CHANGE: Define stub_impl implementation specification
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
