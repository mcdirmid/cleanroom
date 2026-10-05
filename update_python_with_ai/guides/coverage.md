<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T02:03:40Z
CHANGE: new file
CODE_HASH: c2510b321906
-->

# Guide: Coverage Arbiter

## Summary

The verification targets are the library implementation (`lib/<name>.py`) and the test suite (`tests/<name>_test.py`) for the specified unit. In a multi-node session, multiple targets are evaluated together; each target is evaluated and submitted independently via `submit(target="<target_file>")` once 100% statement coverage is achieved, which stamps `COVERAGE_AUDIT: <timestamp>` into the in-band metadata headers of `lib/<name>.py` and `tests/<name>_test.py` without modifying their last changed timestamps. All code files (both lib and test files) are strictly read-only for coverage; calling file editing tools on code files is prohibited, coverage never edits `.py` files directly, and coverage delivers defect attribution exclusively via the `blame` tool (specifying the blamed file `lib/<name>.py` or `tests/<name>_test.py`). Only one agent (either the test module or the library module) is blamed per target in a given turn; when deficits involve both nodes, only one agent is blamed in the current turn, leaving the other to subsequent turns. Deficit diagnosis is concise (under 200 words); the arbiter inspects uncovered lines in the library implementation with line numbers enabled, translates uncovered code into missing grounding requirements, and delivers targeted blame. The search tool is never installed.

Blame feedback is strictly a single paragraph containing no newline characters; line breaks, multi-line formatting, and bulleted lists in blame explanations are prohibited. Blame feedback delivered to the test module is strictly non-prescriptive, identifying only what grounding requirements and behavioral aspects lack coverage; it never prescribes test scenario designs, mock setups, graph topologies, or code snippets, and never mentions library file names, file paths, line numbers, or internal variable names. Blame feedback delivered to the library module is strictly restricted to reporting that code is unreachable under the specification, instructing the library to either restructure the code to eliminate the dead code or annotate it with `# pragma: no cover (assumption: <reason>)` for impossible branches or caller assumptions guaranteed by the contract; diagnosing functional bugs or prescribing functional logic changes to library code is prohibited. When 100% statement coverage is achieved and verified, calling `blame` is prohibited, and the target concludes via the `submit` tool, stamping `COVERAGE_AUDIT` across both verified target files. When coverage cannot be achieved without violating the contract and the code cannot be restructured or annotated with a pragma, the run fails via the `fail` tool instead.

> META: "The coverage arbiter attributes uncovered lines to missing grounding requirements or caller assumptions without modifying code files."

## Deficit diagnosis and blame feedback

- [ ] In multi-node sessions, each target is evaluated independently for its corresponding module, and submitted individually via `submit(target="<target_file>")`
- [ ] All code files are strictly read-only: the agent never modifies `.py` files directly
- [ ] Uncovered statements are inspected by reading the library implementation file with line numbers enabled
- [ ] Coverage evaluation presents all uncovered statement spans per cycle without throttling, enabling the arbiter to diagnose all active deficits together
- [ ] Blame feedback delivered to the test module is strictly non-prescriptive: it identifies only which grounding requirements and behavioral aspects lack test coverage, leaving scenario design, fixture structure, graph topology, and assertion choices entirely to the test module
- [ ] Blame feedback delivered to the test module never prescribes test implementations, mock configurations, fixture designs, graph shapes, node counts, variable values, or assertion code snippets
- [ ] Anti-contamination: blame feedback delivered to the test module is formulated exclusively in the language, types, and operations of the grounding specification closure; it never mentions library file names, file paths, line numbers, internal variables, helper methods, or private execution branches
- [ ] Blame feedback delivered to the test module never instructs tests to assert unmandated behaviors, internal implementation artifacts, or fabricated requirements observed in uncovered library code
- [ ] Repeating identical blame feedback across cycles for an unyielding deficit is prohibited: when previous feedback fails to achieve coverage, the arbiter deepens analysis of the grounding contract to formulate distinct requirement aspects or evaluates whether the code is unreachable
- [ ] In multi-target sessions, the `blame` tool specifies the bound target file receiving blame (`lib/<name>.py` or `tests/<name>_test.py`)
- [ ] Single agent blame per turn: only one agent (either the test module or the library module) is blamed for a target in a given turn; when deficits span both nodes, only one agent is blamed in the current turn, leaving the other node to subsequent turns
- [ ] Blame feedback paragraph format: the blame explanation string is strictly a single paragraph containing no newline characters; multi-line formatting, line breaks, and bulleted lists in blame explanations are prohibited
- [ ] Blame feedback delivered to the library module is strictly restricted to reporting that specific code is unreachable under the specification closure: the feedback instructs the library module only to either restructure the code to eliminate the unreachable code or annotate it with `# pragma: no cover (assumption: <reason>)` when the code represents an impossible branch or caller assumption guaranteed by the contract
- [ ] Blame feedback delivered to the library module never diagnoses functional bugs, contract deviations, or algorithmic logic errors, and never prescribes functional code fixes; functional defect arbitration belongs exclusively to QA
- [ ] When coverage cannot be achieved without violating the grounding contract and the code cannot be eliminated by restructuring or justified by an assumption pragma, the session concludes via the `fail` tool
- [ ] When 100% statement coverage is achieved and verified, calling the `blame` tool is prohibited, and the target concludes via the `submit` tool

## Lint checks

- [ ] Applies only to implementation modules ending in `_impl`
- [ ] The verified target files (lib/<name>.py and tests/<name>\_test.py) contain valid COVERAGE_AUDIT metadata tags upon successful completion
