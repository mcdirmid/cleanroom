# Cleanroom Behavioral Constraints & Guide References

## Workspace Boundaries & File Locations

- **NEVER modify or rely on the `testing/` directory**: The `testing/` directory is an ephemeral test consumer directory that can be deleted or wiped at any time. Running `bin/sync_testing.sh` counts as modifying the `testing/` directory.
- **Canonical Codebase**: All production specifications, library implementations, and builds live exclusively in:
  - `update_with_ai/`
  - `update_python_with_ai/`

## Mandatory Specification-First (HLS-First) Rule

- **ALWAYS start with HLS changes when changing code in a parts directory**: Never make stealth changes to library code (`lib/*.py`), unit tests (`tests/*_test.py`), or grounding specs (`grounding/*.pyi`) without first authoring and aligning the corresponding High-Level Specification (`high/*.md`).
- **Automatic Downstream Alignment**: Whenever changes are made to HLS files (`high/*.md`), immediately and automatically cascade alignment across the entire downstream pipeline: `HLS` (`high/*.md`) $\to$ `Grounding` (`grounding/*.pyi`) $\to$ `Library` (`lib/*.py`) $\to$ `Unit Tests` (`tests/*_test.py`). Do not stop after editing HLS files or wait for separate prompts to complete downstream alignment.
- **Well-Grounded Specifications During Alignment**: When aligning grounding specifications (`grounding/*.pyi`), ensure the specification remains strictly well-grounded:
  - All properties, operational parameters, and dependencies must have explicit derivation paths from in-scope collaborators, configurations, or inputs without floating directives or ungrounded gaps.
  - Implementation stubs (`<name>_impl.pyi`) must maintain sound `GROUNDING_ARGUMENT:` reasoning that demonstrates concrete collaborator wiring, parameter provenance, and tier-appropriate lifecycle interactions for all implemented operations and properties.
- **Specification Links and Verbatim Requirement Citations**: In library code (`lib/*.py`), modules link to their grounding specification in the header (`# Requirements specified in <name>.pyi`) rather than duplicating inline requirement comments. In test code (`tests/*_test.py`), test comments cite exact requirement strings from `FRESH_REQUIREMENTS:` or `INHERITED_REQUIREMENTS:` using `# Requirement: <exact text>`. Fabricating unmandated requirement citations or implementing uncontracted behavior is prohibited.

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
