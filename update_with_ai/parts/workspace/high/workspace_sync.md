<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-08T18:30:00Z
CHANGE: document stub role dependencies synchronization in pull and refresh contracts
CODE_HASH: 6086606e94ff
-->

# workspace_sync interface component

imports: agent_session, workspace_registry, src_metadata

## Purpose

The workspace_sync interface component defines operational contracts for bi-directional file synchronization, two-phase atomic harvesting, and blame feedback flushing between canonical repositories and role workspaces.

Operating across isolated role workspaces requires atomic data movement to prevent partial updates, stale contract reads, and merge conflicts. Unsynchronized upstream changes leave agents writing against obsolete specifications, while uncoordinated writes to canonical repositories risk clobbering concurrent user edits. The workspace_sync interface component establishes contracts for pulling upstream changes and refreshed system files into role workspaces, harvesting modified targets and attested audit stamps back to the main repository via two-phase validation, and flushing buffered blame feedback into culprit files in-band.

**Out of scope:** The workspace_sync interface component does not parse AST grammar, compute topological task schedules, or execute Bazel test rules; these are handled by other components.

**Delegated:** Role configuration and workspace directory lookups are delegated to workspace_registry; in-band source metadata extraction, audit stamping, code hashing, and feedback appending are delegated to src_metadata.

## Types and Behavior

A *sync result* record encapsulates the outcome of a synchronization operation: a count of *pulled files*, a count of *harvested files*, a sequence of *stamped audits*, and a sequence of *flushed blames*.

A session's *workspace synchronizer* transfers files and in-band metadata between canonical repositories and role workspaces.

The workspace synchronizer:

- Pulls updated upstream contracts, guides, and source files from the canonical main repository into a role workspace, preserving read-only permissions on upstream contracts while generating, updating, or purging read-only test stubs for stub role dependencies without copying implementation code.

- Refreshes non-parts system files, including build macros, guide documents, tools, and linters, keeping role workspaces aligned with the canonical main repository and enforcing test stub integrity.

- Harvests modified writable files and attested audits from a role workspace back to the canonical main repository, validating in-band code hashes to ensure modifications are non-empty and non-conflicting before applying writes.

- Flushes buffered blame feedback recorded in local blame buffers into culprit contract files in the canonical main repository, appending unacted feedback blocks in-band and advancing last cleaned timestamps.
