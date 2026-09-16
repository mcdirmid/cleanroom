# Cleanroom Behavioral Constraints & Guide References

## Workspace Boundaries & File Locations

- **NEVER modify or rely on the `testing/` directory**: The `testing/` directory is an ephemeral test consumer directory that can be deleted or wiped at any time.
- **Canonical Codebase**: All production specifications, library implementations, and builds live exclusively in:
  - `update_with_ai/`
  - `update_python_with_ai/`

## Mandatory Specification-First (HLS-First) Rule

- **ALWAYS start with HLS changes when changing code in a parts directory**: Never make stealth changes to library code (`lib/*.py`), unit tests (`tests/*_test.py`), or grounding specs (`grounding/*.pyi`) without first authoring and aligning the corresponding High-Level Specification (`high/*.md`).
- **Four-Way Strict Alignment**: Every behavior, boundary condition, error diagnostic, or parameter must follow the pipeline: `HLS` (`high/*.md`) $\\to$ `Grounding` (`grounding/*.pyi`) $\\to$ `Library` (`lib/*.py`) $\\to$ `Unit Tests` (`tests/*_test.py`).
- **Verbatim Requirement Citations**: Implementation and test comments must cite exact requirement strings from `FRESH_REQUIREMENTS:` or `INHERITED_REQUIREMENTS:` using `# Requirement: <exact text>`. Fabricating unmandated requirement comments or implementing uncontracted behavior is prohibited.

## Guide Editing & Meta-Rules

- **Editing Guides**: ALWAYS read and maintain in context `update_with_ai/guides/meta_guide.md` before creating, updating, or editing any guide.

## Required Guides for Alignments & Tasks

Always read and maintain in context the relevant guide from `update_python_with_ai/guides/` when modifying specs, implementations, tests, or doing alignments:

- **High-Level Specs (HLS)**: `update_python_with_ai/guides/high_level_spec.md`
- **HLS to Grounding Alignment**: `update_python_with_ai/guides/high_to_grounding.md`
- **Grounding to Library Code Alignment**: `update_python_with_ai/guides/grounding_to_lib.md`
- **Grounding to Unit Tests Alignment**: `update_python_with_ai/guides/grounding_to_test.md`
- **QA Verification**: `update_python_with_ai/guides/qa.md`
- **Coverage Arbiter**: `update_python_with_ai/guides/coverage.md`

## Bazel Test Execution Flags

- **Required Flags**: When running tests via `bazel test`, ALWAYS include `--test_output=errors --test_timeout=100` and `--noshow_progress --noshow_loading_progress`.

## DO NOT EDIT pyrightconfig.json to fix type problems!

If a test doesn't matter, don't run the test! Do not edit pyrightconfig.json to make the test not matter anymore. If you have a type error that you can't fix, don't edit pyrightconfig.json to make the type error go away. Etc...

## Git Operations

- **NO Unprompted Commits or Pushes**: NEVER commit or push to git unless explicitly directed to do so by the user.
