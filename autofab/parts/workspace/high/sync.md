# sync interface component

imports: session, autofab_files_ext

## Purpose

The sync interface component defines operational contracts for bi-directional file synchronization, two-phase atomic harvesting, and blame feedback flushing between canonical repositories and role workspaces.

Operating across isolated role workspaces requires atomic data movement to prevent partial updates, stale contract reads, and merge conflicts. Unsynchronized upstream changes leave agents writing against obsolete specifications, while uncoordinated writes to canonical repositories risk clobbering concurrent user edits. The sync interface component establishes contracts for pulling upstream changes and refreshed system files into role workspaces, projecting metadata to expose only change, feedback, and ephemeral code hash attributes, harvesting modified targets and attested audit stamps back to the main repository via two-phase validation while stripping code hashes, and flushing buffered blame feedback into culprit files in-band.

**Out of scope:** The sync interface component does not parse AST grammar, compute topological task schedules, or execute test runners; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; workspace file conventions are delegated to autofab_files_ext.


## Types and Behavior

A *sync result* record encapsulates the outcome of a synchronization operation: a count of *pulled files*, a count of *harvested files*, a sequence of *stamped audits*, and a sequence of *flushed blames*.

An agent session's *workspace synchronizer* transfers files and in-band metadata between canonical repositories and role workspaces.

The workspace synchronizer:

- Pulls updated upstream contracts, guides, and source files from the canonical main repository into a role workspace only when those files have changed in the canonical main repository since the role workspace last pulled files from the canonical repository, tracking inbound pull baselines and never clobbering uncommitted edits or modifications made by the subagent within the role workspace, projecting in-band metadata to expose only change summary, unacted feedback, and code hash attributes while computing code body hashes on writable targets, failing fast only when upstream code changes conflict with uncommitted local code edits on writable targets, and preserving read-only permissions on upstream contracts while delegating test stub synchronization for stub role dependencies to ensure read-only test stub integrity without copying implementation code.

- Refreshes the non-parts system files, including build macros, guide documents, tools, and linters, delegating runner tool deployment, role guide regeneration, and test stub synchronization, while scoping tool configurations to the role workspace boundaries to keep role workspaces aligned and hermetic.


- Harvests modified writable files and attested audits from a role workspace back to the canonical main repository, validating in-band code hashes so that modifications are non-empty and non-conflicting before writes are applied, and stripping code hashes from target files when committing changes back to the canonical main repository.

- Flushes buffered blame feedback recorded in the local blame buffers into the culprit contract files in the canonical main repository, appending unacted feedback blocks in-band and advancing the last cleaned timestamps.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-11-05T11:45:00Z
CHANGE: Pull upstream files only when changed since last pull and prevent clobbering subagent edits
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
