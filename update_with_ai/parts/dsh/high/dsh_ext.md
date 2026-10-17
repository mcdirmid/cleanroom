<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_ext external specification
CODE_HASH: 9ac3fa4e54e5
-->

# dsh_ext external component

## Purpose

The dsh_ext external component defines the external DeepSeek Harness platform boundary for role agent documentation, Cordis overlay patches, headless execution CLI parameters, and session telemetry records.

Direct coupling between canonical Cleanroom orchestration and platform-specific environment conventions impairs portability across diverse execution hosts. The dsh_ext external component encapsulates the filesystem structures, schema definitions, overlay patch mechanics, and session storage formats required for integrating Cleanroom role workspaces with the DeepSeek Harness autonomous agent runtime.

**Out of scope:** The dsh_ext external component does not generate project files, schedule workflows, or execute agent turns; these are handled by other components.

## Grounding Gaps Covered

The dsh_ext component provides external domain knowledge and format mechanics for the DeepSeek Harness CLI and session execution environment.

Grounding gaps covered include:

- DeepSeek Harness CLI execution interface: Defines the command-line options and parameters for executing DeepSeek Harness headlessly via `dsh --profile headless`, including overlay patch flags (`--patch`), event streaming flags (`--json`), session resumption flags (`--session-id`), and workspace directory execution context.

- Cordis overlay patch conventions: Defines the structure and syntax of targeted YAML patch files placed in `.cleanroom/dsh_patch.yml`, configuring `@deepseek-ai/dsh-agent-default-model` to dynamically select the active model and provider, setting high reasoning effort for DeepSeek providers, disabling the `@deepseek-ai/todo` plugin, and configuring `@deepseek-ai/dsh-user-approval` and `@deepseek-ai/dsh-permission-presets` with `danger-full-access` and `never` approval policy for unattended subagent execution.

- Role agent documentation conventions: Defines the structure and discovery of `AGENTS.md` files placed within role workspace roots, loaded by `@deepseek-ai/dsh-agent-instructions`, instructing DeepSeek Harness subagents never to access or mutate files outside their provisioned workspace root and restricting shell execution strictly to prescribed Cleanroom role binaries.

- Session storage and streaming telemetry schema: Defines the session archive structure under `~/Library/Application Support/dsh-desktop/harness/sessions/<dir-slug>/<session-id>/session.v4.jsonl.zstd` and uncompressed fallback `session.v4.jsonl`, non-blocking session locking via `session.lock`, active session identifier persistence in `.cleanroom/dsh_session_id.txt`, and the newline-delimited JSON run event stream from `dsh --profile headless --json`, specifying token usage objects with `inputTokens`, `outputTokens`, `cacheReadTokens`, `cacheWriteTokens`, and `totalTokens`.
