# dsh_ext external component

## Purpose

The dsh_ext external component defines the external DeepSeek Harness platform boundary for role agent documentation, Cordis overlay patches, headless execution CLI parameters, and session telemetry records.

Direct coupling between canonical Cleanroom orchestration and platform-specific environment conventions impairs portability across diverse execution hosts. The dsh_ext external component encapsulates the filesystem structures, schema definitions, overlay patch mechanics, and session storage formats required for integrating Cleanroom role workspaces with the DeepSeek Harness autonomous agent runtime.

**Out of scope:** The dsh_ext external component does not generate project files, schedule workflows, or execute agent rounds; these are handled by other components.

## Grounding Gaps Covered

The dsh_ext component provides external domain knowledge and format mechanics for the DeepSeek Harness CLI and session execution environment.

Grounding gaps covered include:

- DeepSeek Harness CLI execution interface: Defines the command-line options and parameters for executing DeepSeek Harness headlessly via `dsh --profile headless`, including overlay patch flags (`--patch`), event streaming flags (`--json`), session resumption flags (`--session-id`), and workspace directory execution context.

- Cordis overlay patch conventions: Defines the structure and syntax of targeted YAML patch files placed in `.cleanroom/dsh_patch.yml`, configuring `@deepseek-ai/dsh-agent-default-model` to dynamically select the active model and provider, setting high reasoning effort for DeepSeek providers, disabling the `@deepseek-ai/todo` plugin, and configuring `@deepseek-ai/dsh-user-approval` and `@deepseek-ai/dsh-permission-presets` with `danger-full-access` and `never` approval policy for unattended subagent execution.

- Role agent documentation conventions: Defines the structure and discovery of `AGENTS.md` files placed within role workspace roots, loaded by `@deepseek-ai/dsh-agent-instructions`, instructing DeepSeek Harness subagents never to access or mutate files outside their provisioned workspace root, permitting in-workspace shell commands and harness tools, and mandating round resolution through prescribed Cleanroom role binaries.

- Session storage and streaming telemetry schema: Defines the session archive structure discovered under DSH_SESSIONS_DIR, DSH_HOME, or platform application support directories (`~/Library/Application Support/dsh-desktop/harness/sessions` on macOS or `~/.config/dsh-desktop/harness/sessions` on Linux, storing `<dir-slug>/<session-id>/session.v4.jsonl.zstd` and uncompressed fallback `session.v4.jsonl`), non-blocking session locking via `session.lock`, active session identifier persistence in `.cleanroom/dsh_session_id.txt` (reset upon failed rounds), and the newline-delimited JSON run event stream from `dsh --profile headless --json`, specifying token usage objects with `inputTokens`, `outputTokens`, `cacheReadTokens`, `cacheWriteTokens`, and `totalTokens`.

- DeepSeek Harness JSON-RPC wire protocol and server discovery: Defines the JSON-RPC wire protocol served by DeepSeek Harness runtimes and Desktop instances, discovering active server listening ports and authentication cookies from application support `Cookies` SQLite databases, supporting client requests over local HTTP RPC endpoints (`/api/...`) with client-request envelopes, including server session listing (`session/list`), workspace registration (`workspace/create`), session creation (`session/create`, supporting standard agent presets), prompt execution dispatch (`session/prompt`), session projection querying (`session/projections`), and session deletion (`session/delete`).

- Subagent delegation depth limits: Defines the `maxDepth` configuration format supported by `@deepseek-ai/dsh-tool-subagent`, accepting arbitrary natural numbers or provider-managed delegation for recursive in-process subagent execution when backed by providers supporting depth limits.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-20T22:50:00Z
LAST_CHANGED: 2026-10-20T22:50:00Z
CHANGE: Specify active session identifier reset only upon failed rounds
-->
