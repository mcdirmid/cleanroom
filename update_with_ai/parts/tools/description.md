# Tools Part (`update_with_ai/parts/tools`)

## Purpose

The **tools** part implements the workspace command-line interface, work discovery manager, pending work queue, verification runners, dirtiness evaluators, and test coverage checkers designed for autonomous agents operating inside role workspaces.

When external subagents (e.g. running under Google Antigravity or DeepSeek Harness) operate within isolated role workspaces, they do not communicate via in-memory function calls. Instead, they interact with Cleanroom via explicit workspace shell binaries located in their workspace `bin/` directory (`bin/get-work`, `bin/check-files`, `bin/submit`, `bin/blame`, `bin/status`). The tools part provides these command handlers, evaluates directory-scoped task readiness by topological role tier depth, persists pending and blame queues, executes noise-scrubbed verification checks, and audits test statement coverage.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/tools/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high):

- [`workspace_commands.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_commands.md) & [`workspace_commands_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_commands_impl.md): Defines the core CLI command suite deployed into role workspaces:
  - `get-work`: Discovers and presents ready tasks within the directory scope, listing companion specifications, contracts, and unaddressed feedback.
  - `check-files`: Runs configured verification commands, scrubbed of compiler noise, and caches results.
  - `submit`: Concludes completed targets, validating change summaries and in-band metadata.
  - `blame`: Attributes defect feedback to upstream contract dependencies, recording critiques in blame buffers.
  - `status`: Displays current dirty, pending, and clean target counts across the directory scope.
- [`workspace_tool.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_tool.md) & [`workspace_tool_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_tool_impl.md): Dispatches command-line invocations matching arguments to the appropriate workspace command handler.
- [`workspace_work.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_work.md) & [`workspace_work_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_work_impl.md): Manages task discovery over directory scopes using dynamic role tier depth. Resolves companion upstream specification contracts, treats feedback and star role dependencies as implicit dependencies, materializes starter templates for missing files, tracks assigned work in `.cleanroom/pending_work.json`, and blocks new queries until pending work is resolved.
- [`workspace_check.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_check.md) & [`workspace_check_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_check_impl.md): Realizes verification check execution for role workspaces. Invokes compilers/linters/tests, strips banner noise, and reuses cached results when source file hashes match.
- [`workspace_dirtiness.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_dirtiness.md) & [`workspace_dirtiness_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_dirtiness_impl.md): Evaluates whether workspace units are dirty across local and canonical workspaces, checking source file existence, parseable in-band metadata, timestamps, and upstream contract modifications.
- [`workspace_pending.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_pending.md) & [`workspace_pending_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/workspace_pending_impl.md): Manages reading, writing, and updating `.cleanroom/pending_work.json` and `.cleanroom/blame.json` buffers.
- [`tool_coverage.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/tool_coverage.md) & [`tool_coverage_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/tool_coverage_impl.md): Evaluates statement test coverage for unit test targets against library implementations, comparing coverage ratios against configured thresholds and reporting missing line numbers.
- [`tools_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/high/tools_asm.md): Assembles all workspace commands, work managers, check runners, and coverage evaluators into the unified tools subsystem.

## How It Is Used by Other Parts

- **`subagent`**: After dispatching a subagent turn into a role workspace, `subagent_harness` inspects `workspace_pending` and `workspace_work` buffers (`pending_work.json`, `blame.json`) to compute which targets were submitted, blamed, or left uncompleted.
- **`dsh`**: DeepSeek Harness role agent documentation explicitly directs agents to call `tools` binaries (`bin/get-work`, `bin/check-files`, `bin/submit`, `bin/blame`, `bin/status`).
- **`workspace`**: Deploys the CLI binaries provided by `tools` into the `bin/` directory of newly provisioned role workspaces.
- **`systems`**: Aggregated into `uv_cleanroom_asm`.
- **Top-Level CLI & Support (`cleanroom_role_tool`)**: Entrypoints directly dispatch commands like `cleanroom get-work`, `cleanroom submit`, `cleanroom check-files` to `tools`.
