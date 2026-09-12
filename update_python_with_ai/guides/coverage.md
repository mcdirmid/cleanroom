# Guide: Coverage Arbiter

## Summary

The artifact is the coverage arbiter log `<name>_coverage.log` and the blame decisions delivered to the test and lib nodes. All code files (both lib and test files) are strictly read-only for coverage; calling file editing tools (`replace`, `update_lines`) on code files is prohibited, coverage never edits `.py` files, and coverage modifies only `<name>_coverage.log`, delivering defect attribution exclusively via the `blame` tool. Deficit diagnosis is concise; the arbiter inspects uncovered lines in the library implementation with line numbers enabled, translates uncovered code into missing grounding requirements, and records active deficits and attempted resolution tactics in `<name>_coverage.log` to track progress across turns and avoid repetitive blame cycles. The search tool is never installed.

The log documents active coverage deficits and the history of attempted resolutions across feedback turns to avoid repeating identical feedback; entries for lines covered in subsequent cycles are deleted, and the log is completely emptied (0 bytes) once 100% statement coverage is achieved. Blame feedback is assigned primarily to the test module, formulated exclusively in the language of the grounding specification closure (grounding terms, operations, postconditions, and scenario angles) without mentioning library file names, file paths, or line numbers. When a line remains uncovered after prior feedback, the arbiter consults its log, avoids repeating identical feedback, analyzes whether a different scenario angle or requirement interpretation is required, evaluates whether the uncovered line represents an impossible branch or caller assumption guaranteed by the contract, and delivers blame to the library module to add `# pragma: no cover (assumption: <reason>)` only when an assumption holds, or concludes via the `fail` tool when progress cannot be made. Completion succeeds only when 100% statement coverage is achieved and the coverage log is completely empty.

> META: "The coverage arbiter attributes uncovered lines to missing grounding requirements or caller assumptions without modifying code files."

## Tracking and translating coverage deficits

- [ ] The log `<name>_coverage.log` records active deficits and attempted feedback tactics across turns: when previous feedback fails to cover a line, the log is consulted to select alternative requirement angles or identify caller assumptions rather than repeating prior feedback
- [ ] The log `<name>_coverage.log` holds only active, unresolved coverage deficits in the current cycle: when lines from previous turns become covered in subsequent runs, their entries are removed from `<name>_coverage.log`
- [ ] All code files are strictly read-only: the agent never modifies `.py` files and modifies only `<name>_coverage.log`
- [ ] Uncovered statements are inspected by reading the library implementation file with line numbers enabled
- [ ] Uncovered implementation statements are translated into missing requirements or unexercised scenario angles with respect to the grounding specification
- [ ] Blame feedback delivered to the test module is formulated exclusively in the language of the grounding specification, citing grounding operations, types, postconditions, or boundary scenarios that lack test coverage
- [ ] Blame feedback delivered to the test module never mentions library file names, file paths, line numbers, or internal variable names
- [ ] Repeating identical blame feedback across cycles for an unyielding deficit is prohibited: when previous feedback fails to achieve coverage, the arbiter deepens analysis of the grounding contract to formulate distinct scenario angles
- [ ] When an uncovered line in the library implementation corresponds to an impossible branch or caller assumption guaranteed by the grounding specification closure, blame feedback is delivered to the library module instructing it to annotate the line with `# pragma: no cover (assumption: <reason>)`
- [ ] Library module blame feedback is strictly restricted to `# pragma: no cover` annotations for impossible cases or caller assumptions; assigning blame to the library module for any other reason is prohibited
- [ ] When coverage cannot be achieved without violating the grounding contract and the line is not an assumption, the session concludes via the `fail` tool
- [ ] Coverage evaluation presents at most 3 non-continuous line spans per cycle to keep blame feedback focused; once the reported spans are addressed, subsequent evaluation cycles expose any remaining spans
- [ ] When 100% statement coverage is achieved and verified, the coverage log is completely empty (0 bytes, all lines including headers deleted)

## Lint checks

- [ ] Applies only to implementation modules ending in `_impl`
- [ ] The coverage log `<name>_coverage.log` is empty (0 bytes) upon successful completion
