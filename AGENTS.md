# Cleanroom Behavioral Constraints & Guide References

## Workspace Boundaries & File Locations

- **NEVER modify or rely on the `staging/` directory**: The `staging/` directory is an ephemeral test consumer directory that can be deleted or wiped at any time. Running `bin/sync_staging.sh` counts as modifying the `staging/` directory.
- **Canonical Codebase**: All production specifications, library implementations, and builds live exclusively in:
  - `update_with_ai/`
  - `update_python_with_ai/`

## Strict Prohibition on Hardcoding Specific Paths, Directory Names, and Role Names

- **NO Hardcoded Directory Names or Paths**: Specific directory names, package scopes, or ephemeral workspace paths (such as `staging`, `update_with_ai`, `update_python_with_ai`, `role_workspaces`, or temporary directories) must NEVER be hardcoded into tools, linters, runners, verifiers, test assertions, or library implementations.
- **NO Hardcoded Role Names**: Role names (such as `high`, `planning`, `low`, `spec_qa`, `lib`, `test`, `qa`, `coverage`, `scenario`, etc.) must NEVER be hardcoded into core tools, workspace provisioners, runners, orchestrators, or library logic. Roles must be discovered dynamically from the active methodology configuration (e.g., `cleanroom_roles.toml`, `cleanroom.toml`) and target definitions.
- **Dynamic Scoping and Target Derivation**: Package scopes, workspace roots, role definitions, and directory paths must always be derived dynamically from the target address (e.g., `//<scope>/parts/...#<role>`), active configuration files (e.g., `cleanroom.toml`, `cleanroom_roles.toml`), environment variables (e.g., `BUILD_WORKSPACE_DIRECTORY`), or passed explicitly as arguments without hardcoded directory or role defaults.
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

## Guide Editing & Meta-Rules

- **Editing Guides**: ALWAYS read and maintain in context `update_with_ai/guides/meta_guide.md` before creating, updating, or editing any guide.

## Required Guides for Alignments & Tasks

Always read and maintain in context the relevant guide from `update_python_with_ai/guides/` when modifying specs, implementations, tests, or doing alignments:

- **High-Level Specs (HLS)**: `update_python_with_ai/guides/high_level_spec.md`
- **HLS to Planning Alignment**: `update_python_with_ai/guides/high_to_planning.md`
- **Planning to Low Alignment**: `update_python_with_ai/guides/planning_to_low.md`
- **Spec QA Arbiter**: `update_python_with_ai/guides/spec_qa.md`
- **Low-Level Specification to Library Code Alignment**: `update_python_with_ai/guides/low_to_lib.md`
- **Low-Level Specification to Unit Tests Alignment**: `update_python_with_ai/guides/low_to_test.md`
- **QA Verification**: `update_python_with_ai/guides/qa.md`
- **Coverage Arbiter**: `update_python_with_ai/guides/coverage.md`

## Test Execution (bin/test)

- **Required Test Runner**: Use `bin/test` to run repo verification and tests cleanly.

## Local Python Linter Invocations (test_lint.py)

- **Required PYTHONPATH**: When running `test_lint.py` directly (such as during dry-run collection verification), ensure `PYTHONPATH` includes `update_python_with_ai` and all constituent library directories (`update_with_ai/parts/*/lib` or package roots) to prevent cross-package `ModuleNotFoundError` during test module dry runs.

## DO NOT EDIT pyrightconfig.json to fix type problems!

If a test doesn't matter, don't run the test! Do not edit pyrightconfig.json to make the test not matter anymore. If you have a type error that you can't fix, don't edit pyrightconfig.json to make the type error go away. Etc...

## Git Operations

- **NO Unprompted Commits or Pushes**: NEVER commit or push to git unless explicitly directed to do so by the user.

## Autonomous Clean-All Antigravity Execution

- **Immediate Coordinator Invocation on clean-all**: When `bin/cleanroom clean-all ...` is executed (or outputs the `AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE`), do NOT stop to ask for confirmation. Immediately and automatically invoke the `cleanroom_coordinator` subagent in the very same turn to drive DAG convergence.
