# Autofab Behavioral Constraints & Guide References

## Workspace Boundaries & File Locations

- **NEVER modify or rely on the `staging/` directory**: The `staging/` directory is an ephemeral test consumer directory that can be deleted or wiped at any time. Running `bin/sync_staging.sh` counts as modifying the `staging/` directory.
- **Canonical Codebase**: All production specifications, library implementations, and builds live exclusively in:
  - `autofab/`
  - `autofab_py/`
  - `pretense/`
- **Pure Monorepo Architecture**: For local development, testing, and benchmarking, the repository operates strictly as a pure monorepo governed by the root `pyproject.toml`. Never configure `[tool.uv.workspace]` or `[tool.uv.sources]` with non-editable package dependencies for local development. Full details are documented in [`docs/build.md`](file:///Users/seanmcdirmid/projects/cleanroom/docs/build.md).

## Strict Prohibition on Hardcoding Specific Paths, Directory Names, and Role Names

- **NO Hardcoded Directory Names or Paths**: Specific directory names, package scopes, or ephemeral workspace paths (such as `staging`, `autofab`, `autofab_py`, `pretense`, `autofab_role_workspaces`, `role_workspaces`, or temporary directories) must NEVER be hardcoded into tools, linters, runners, verifiers, test assertions, or library implementations.
- **NO Hardcoded Role Names**: Role names (such as `high`, `planning`, `low`, `spec_qa`, `lib`, `test`, `qa`, `coverage`, `scenario`, `pretense`, `pretense_qa`, `pretense_coverage`, etc.) must NEVER be hardcoded into core tools, workspace provisioners, runners, orchestrators, or library logic. Roles must be discovered dynamically from the active methodology configuration (e.g., `autofab_roles.toml`, `cleanroom_roles.toml`, `autofab.toml`, `cleanroom.toml`) and target definitions.
- **Dynamic Scoping and Target Derivation**: Package scopes, workspace roots, role definitions, and directory paths must always be derived dynamically from the target address (e.g., `//<scope>/parts/...#<role>`), active configuration files (e.g., `autofab.toml`, `autofab_roles.toml`), environment variables (e.g., `BUILD_WORKSPACE_DIRECTORY`), or passed explicitly as arguments without hardcoded directory or role defaults.
- **Agnostic Linters, Runners, and Verifiers**: Linters, runners, and verification tools must verify imports, package structures, and role execution relative to the active target's resolved package root, methodology manifest, and declared dependencies, rather than asserting against hardcoded directory strings or static role enumerations.

## Mandatory Specification-First (HLS-First) Rule

- **ALWAYS start with HLS changes when changing code in a parts directory**: Never make stealth changes to library code (`lib/*.py`) or unit tests (`tests/*_test.py`) without first authoring and aligning the corresponding High-Level Specification (`high/*.md`).
- **Every Bug or Defect is a Specification Defect**: Do NOT treat bug fixing, troubleshooting, or runtime failures as an excuse to jump directly to patching `lib/*.py` or `tests/*_test.py`. If code behaved incorrectly, determine what high-level behavioral contract was omitted or violated, author the change in `high/*.md` first, and cascade down.
- **Automatic Downstream Alignment**: Whenever changes are made to HLS files (`high/*.md`), immediately and automatically cascade alignment across the entire downstream pipeline: `HLS` (`high/*.md`) $\to$ `Planning` (`planning/*.md`) $\to$ `Scenarios` (`scenarios/*.md`) $\to$ `Low` (`low/*.pyi`) $\to$ `Spec QA` $\to$ `Library` (`lib/*.py`) $\to$ `Unit Tests` (`tests/*_test.py`). Do not stop after editing HLS files or wait for separate prompts to complete downstream alignment.
- **Pre-Edit Gate (STOP before touching `lib/` or `tests/`)**: Before editing any file under `parts/*/lib/` or `parts/*/tests/`, verify:
  1. Has the corresponding `high/*.md` been authored first, with planning, scenarios, and low specifications aligned?
  2. Or are you specifically dealing with preexisting uncontracted code?
  If neither, **STOP**. Author the HLS change first.

## Handling Uncontracted Code

- **Permitted to Delete**: When specifically discovering preexisting uncontracted code in `lib/` or `tests/`, you are fully permitted to delete it if it is unneeded, redundant, or uncontracted fallback logic.
- **Retrofitting Contracts is Discouraged but Permitted**: Retrofitting contracts backwards from code to spec is discouraged, but is sometimes the only way to deal with essential uncontracted code that must be preserved. When retrofitting, author the missing contracts up the ladder (`low/`, `scenarios/`, `planning/`, `high/`) so the functionality is no longer uncontracted. Once retrofitted, all subsequent changes must follow the strict HLS-first rule.

## Semantic Analysis Over Syntactic Checking (Anti-Mechanistic Rule)

- **Mechanistic Checking is Only 1%**: Passing linters, type checkers, or verifiers with zero errors is merely a baseline mechanical sanity check. It does NOT mean the specification or implementation is correct or meaningful. Stop treating tasks as syntactic constraint-satisfaction games.
- **Mandatory Deep Semantic Analysis**: Every specification, implementation, contract, and test must be derived by analyzing the actual behavioral semantics and contracts in upstream artifacts rather than shallow mechanistic checks.

## Standard Terminology: Step vs Round (Strict Prohibition on "Turn")

- **STRICT PROHIBITION ON "TURN"**: The term "turn" is ambiguous (historically conflated between a single tool-call step and a full role dispatch wave) and is strictly deprecated and prohibited in documentation, guides, design docs, specifications, prompts, and code. Use **step** or **round** explicitly.
- **Step**: A single prompt $\leftrightarrow$ tool-call interaction cycle between an agent/model and the runtime/harness (e.g., model prompt $\to$ internal reasoning $\to$ tool call(s) $\to$ tool response).
- **Round**: A full Autofab role dispatch wave or execution pass across assigned targets (from role dispatch into a role workspace until completion, submission, blame, or exhaustion). A round encompasses all model steps executed within that role dispatch pass. Re-entry of a role (e.g. after downstream rejection or loop propagation) initiates a subsequent round.

## Mandatory Tool Execution and Round Conclusion (Prohibition on Conversational Halting)

- **Ground Truth First (Anti-Speculation Rule)**: Always run `bin/check_files <target>` immediately as the first action after `bin/get_work` to obtain deterministic error diagnostics. Never guess, infer, or speculate about defects from reading prose before checking the actual oracle output.
- **Continuous Tool Execution While Work Remains**: While ready targets remain unresolved, role workers operate exclusively via tool execution. Producing conversational commentary, explanations, or announcing actions in prose (such as ending a message with a colon or promising a tool call) without invoking tools in the same step is strictly prohibited and causes runtime harnesses to terminate rounds prematurely.
- **Targeted Reads Over Repeated Dumps**: Never repeatedly read entire files when output is pruned. Use grep to locate symbols, or read narrow line ranges with offset and limit.
- **Strict Prohibition on Runtime Testing and Inline Test Scripts**: Role workers are strictly prohibited from executing ad-hoc tests, runtime sanity checks, test assertions, or injecting exploratory probe code / exceptions into target files to probe runtime behavior at import time. You are NOT allowed to execute the test suite or run ad-hoc probes. Target verification relies exclusively on `bin/check_files`. Submit your work with `bin/submit` so a downstream QA auditor can execute the test suite on your behalf. Runtime execution and test validation are performed solely by downstream auditor roles (QA/Pretense); role workers must never attempt to pre-test implementation code to avoid blame.
- **Mandatory Round Conclusion When Work is Done**: When a role worker has no outstanding work to do and `bin/get_work` does not give it more work to do (all assigned ready targets have been resolved via `bin/check_files <target>` followed by `bin/submit`, `bin/blame`, or `bin/fail`, or only blocked targets remain), the worker can and MUST conclude the round immediately. The worker must output its concise summary text WITHOUT invoking any further tools (`ls`, `bin/get_work`, dummy commands). Delivering text with zero tool calls is the expected mechanism that cleanly concludes the round in autonomous harnesses. Leaving assigned targets unresolved without tool execution triggers coordinator reminders and trips the impasse circuit breaker.

## Guide Editing & Meta-Rules

- **Editing Guides**: ALWAYS read and maintain in context `autofab/guides/meta_guide.md` before creating, updating, or editing any guide.

## Required Guides for Alignments & Tasks

Always read and maintain in context the relevant guide from `autofab_py/guides/` when modifying specs, implementations, tests, or doing alignments:

- **High-Level Specs (HLS)**: `autofab_py/guides/high_level_spec.md`
- **HLS to Planning Alignment**: `autofab_py/guides/high_to_planning.md`
- **Planning to Low Alignment**: `autofab_py/guides/planning_to_low.md`
- **Spec QA Arbiter**: `autofab_py/guides/spec_qa.md`
- **Low-Level Specification to Library Code Alignment**: `autofab_py/guides/low_to_lib.md`
- **Low-Level Specification to Unit Tests Alignment**: `autofab_py/guides/low_to_test.md`
- **QA Verification**: `autofab_py/guides/qa.md`
- **Coverage Arbiter**: `autofab_py/guides/coverage.md`

## Test Execution (bin/test)

- **Required Test Runner**: Use `bin/test` to run repo verification and tests cleanly.
- **NO bin/test for Design Doc Changes**: When authoring, updating, or reviewing design documentation (`design-docs/*.md`), guides, or markdown files without modifying executable code or production specifications in `parts/`, you do NOT need to run `bin/test`. Only invoke `bin/test` when code, specifications, or harness configurations are actually modified.

## Local Python Linter Invocations (test_lint.py)

- **Required PYTHONPATH**: When running `test_lint.py` directly (such as during dry-run collection verification), ensure `PYTHONPATH` includes `autofab_py`, `pretense`, and all constituent library directories (`autofab/parts/*/lib`, `pretense/parts/*/lib`, or package roots) to prevent cross-package `ModuleNotFoundError` during test module dry runs.

## DO NOT EDIT pyrightconfig.json to fix type problems!

If a test doesn't matter, don't run the test! Do not edit pyrightconfig.json to make the test not matter anymore. If you have a type error that you can't fix, don't edit pyrightconfig.json to make the type error go away. Etc...

## Direct Command Execution

- **Immediate Execution of Explicit Shell Commands**: When the user provides an explicit shell command to run (e.g., `uv run ...`, `bin/...`, `pytest ...`), execute `run_command` immediately in the very first step. Do NOT inspect source code, read files, second-guess, or perform pre-flight research before running the command.

## Git Operations

- **NO Unprompted Commits or Pushes**: NEVER commit or push to git unless explicitly directed to do so by the user.

## Autonomous Orchestration Antigravity Execution

- **Immediate Coordinator Invocation on orchestrate & benchmarks (Antigravity Only)**: When running under the Google Antigravity agent, if any command resolving to the Antigravity harness (such as `uv run autofab orchestrate ...`, `uv run autofab clean ...`, `uv run autofab benchmark ...`, or `uv run bin/evaluate_model_efficiency.py ...`) is executed (or emits the `AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE`):
  1. If `agentapi send-message` reactive wakeup message is received in the chat, use the target scope specified directly in the message.
  2. If the command runs as a background task and no message arrived, immediately inspect the task log (`.system_generated/tasks/task-X.log`) or `logs/*_runner.log` to extract the scope name (`benchmarks_flight_*` or target scope). Do NOT wait for the background command to finish before launching the coordinator—the command is waiting for the coordinator to converge the DAG.
  3. Immediately invoke:
     `invoke_subagent(TypeName="autofab_coordinator", Role="Autofab Coordinator", Prompt="Clean all dirty nodes in <scope> using autofab_coordinator")`
  In other environments (such as DeepSeek Harness / DSH Desktop), run `uv run autofab clean <scope> [target_role]` directly via the terminal tool (configured with a model using the `dsh` harness in `model_configs.toml`).
  For autonomous DAG convergence under Antigravity, run `uv run autofab clean <target>` with a model using the `antigravity` harness.

## DSH Web Remote Access URL

- **Remote Access URL**: The only supported URL for remote access is `http://seans-macbook-pro-2.local:3080/?token=<active_token>`. Never suggest `localhost`, `127.0.0.1`, or raw IP addresses.
- **Dynamic Active Token (Never Hardcode Stale Tokens)**: Never hardcode a static or stale token. Always extract the active token dynamically from the running DSH Web daemon output (`dsh web: ...?token=<active_token>`) in the task log.

## Credentials & Package Publishing

- **Credentials Location**: External service and publishing credentials live in `~/.config/autofab/credentials.toml` outside the working tree (contains `UV_PUBLISH_TOKEN`, `OPENAI_API_KEY`, etc.). NEVER log, commit, or duplicate tokens from this file.
- **Publishing Instructions**: Detailed procedures for bumping versions, building wheels/sdists, and publishing the three repository packages (`autofab`, `autofab-py`, and `pretense-py`) to PyPI are maintained in [`docs/publishing.md`](file:///Users/seanmcdirmid/projects/cleanroom/docs/publishing.md).
- **Publishing Execution**: When directed to update or publish PyPI packages, extract `UV_PUBLISH_TOKEN` from `~/.config/autofab/credentials.toml`, build all distributions with `uv build` in their respective package directories (`.`, `autofab_py`, `pretense`), and publish via `uv publish`.
