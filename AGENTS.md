# Cleanroom Behavioral Constraints & Guide References

## Workspace Boundaries & File Locations

- **NEVER modify or rely on the `staging/` directory**: The `staging/` directory is an ephemeral test consumer directory that can be deleted or wiped at any time. Running `bin/sync_staging.sh` counts as modifying the `staging/` directory.
- **Canonical Codebase**: All production specifications, library implementations, and builds live exclusively in:
  - `update_with_ai/`
  - `update_python_with_ai/`

## Mandatory Specification-First (HLS-First) Rule

- **ALWAYS start with HLS changes when changing code in a parts directory**: Never make stealth changes to library code (`lib/*.py`), unit tests (`tests/*_test.py`), or grounding specs (`grounding/*.pyi`) without first authoring and aligning the corresponding High-Level Specification (`high/*.md`).
- **Automatic Downstream Alignment**: Whenever changes are made to HLS files (`high/*.md`), immediately and automatically cascade alignment across the entire downstream pipeline: `HLS` (`high/*.md`) $\\to$ `Planning` (`planning/*.md`) $\\to$ `Low` (`low/*.pyi`) $\\to$ `Grounding` (`grounding/*.py`) $\\to$ `Grounding QA` (`logs/*_grounding_qa.log`) $\\to$ `Library` (`lib/*.py`) $\\to$ `Unit Tests` (`tests/*_test.py`). Do not stop after editing HLS files or wait for separate prompts to complete downstream alignment.

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
- **Low to Grounding Alignment**: `update_python_with_ai/guides/low_to_grounding.md`
- **Grounding QA Arbiter**: `update_python_with_ai/guides/grounding_qa.md`
- **Low-Level Specification to Library Code Alignment**: `update_python_with_ai/guides/low_to_lib.md`
- **Low-Level Specification to Unit Tests Alignment**: `update_python_with_ai/guides/low_to_test.md`
- **QA Verification**: `update_python_with_ai/guides/qa.md`
- **Coverage Arbiter**: `update_python_with_ai/guides/coverage.md`

## Bazel Test Execution Flags

- **Required Flags**: When running tests via `bazel test`, ALWAYS include `--test_output=errors --test_timeout=100` and `--noshow_progress --noshow_loading_progress`.

## Local Python Linter Invocations (test_lint.py)

- **Required PYTHONPATH**: When running `test_lint.py` directly outside of Bazel (such as during dry-run collection verification), ensure `PYTHONPATH` includes `update_python_with_ai` and all constituent library directories (`update_with_ai/parts/*/lib` or package roots) to prevent cross-package `ModuleNotFoundError` during test module dry runs.

## DO NOT EDIT pyrightconfig.json to fix type problems!

If a test doesn't matter, don't run the test! Do not edit pyrightconfig.json to make the test not matter anymore. If you have a type error that you can't fix, don't edit pyrightconfig.json to make the type error go away. Etc...

## Git Operations

- **NO Unprompted Commits or Pushes**: NEVER commit or push to git unless explicitly directed to do so by the user.
