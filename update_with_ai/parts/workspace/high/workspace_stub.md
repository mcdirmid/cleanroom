<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T17:55:00Z
CHANGE: Define workspace_stub interface specification
CODE_HASH: 8dba2c166cae
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_stub interface component

imports: agent_session, workspace_registry

## Purpose

The workspace_stub interface component defines operational contracts for synthesizing, synchronizing, and detecting read-only Python test stubs from `.pyi` interface and implementation specifications for test roles with stub role dependencies.

Test authoring subagents require concrete Python module files to import when writing and executing unit tests. However, providing real implementations to test authoring agents exposes implementation details, leading to tautological tests or cheating. Synthesizing read-only test stubs that reflect method signatures from `.pyi` specifications while raising `NotImplementedError` ensures that unit tests test against specification contracts without relying on implementation code. The workspace_stub interface component defines contracts for stub synthesis, dependency matching, and synchronization.

**Out of scope:** The workspace_stub interface component does not commission workspace directories or deploy runner executables; these are handled by workspace_provision.

**Delegated:** Execution phase context boundaries are delegated to agent_session. Role definitions and directory paths are delegated to workspace_registry.

## Types and Behavior

An agent session's *workspace stub synthesizer* provides test stub generation and dependency synchronization.

The workspace stub synthesizer:

- Synthesizes read-only test stubs raising `NotImplementedError` from companion `.pyi` specifications into destination Python files, preserving class, function, and method signatures while replacing bodies, rewriting top-level imports to point to local workspace library stubs, and injecting missing method definitions derived from upstream interfaces.

- Synchronizes read-only test stubs for role workspaces declaring stub role dependencies, updating stubs when companion specifications change and purging orphaned stubs.

- Determines whether a relative file path matches any declared role in a role's stub dependencies.

- Checks whether an existing file on disk is a valid Cleanroom test stub.
