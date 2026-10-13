<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-13T11:20:00Z
CHANGE: update goose_ext to remove recipes and use AGENTS.md conventions
CODE_HASH: 0a734f891418
-->

# goose_ext external component

## Purpose

The goose_ext external component defines the external Goose platform boundary for role agent documentation, subagent CLI invocation conventions, and SQLite session telemetry records.

Direct coupling between canonical Cleanroom orchestration and platform-specific environment conventions impairs portability across diverse execution hosts. The goose_ext external component encapsulates the filesystem structures, schema definitions, and session database formats required for integrating Cleanroom role workspaces with the Goose autonomous agent runtime.

**Out of scope:** The goose_ext external component does not generate project files, schedule workflows, or execute agent turns; these are handled by other components.

## Grounding Gaps Covered

The goose_ext component provides external domain knowledge and format mechanics for the Goose CLI and session execution environment.

Grounding gaps covered include:

- Goose CLI execution interface: Defines the command-line options and parameters for executing Goose non-interactively via `goose run`, including instructions path flags (`-i`, `--instructions`), session naming flags (`--name`), maximum turn limits (`--max-turns`), and workspace directory execution context.

- Role agent documentation conventions: Defines the structure and discovery of `AGENTS.md` files placed within role workspace roots, instructing Goose agents never to access or mutate files outside their provisioned workspace root and restricting shell execution strictly to prescribed Cleanroom role binaries.

- SQLite session telemetry database schema: Defines the database tables in `~/.local/share/goose/sessions/sessions.db`, specifying the `sessions` table with session identifier, name, working directory, input tokens, output tokens, cache read tokens, and accumulated cost, together with the `usage_ledger` table recording turn-level token and cost transactions.
