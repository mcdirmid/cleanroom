<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-17T18:00:00Z
LAST_CHANGED: 2026-10-17T18:00:00Z
CHANGE: Disallow white-box test exemptions and require contracts for all test-imported symbols
CODE_HASH: uncontracted04
-->

# Guide: Uncontracted Code Identification, Specification Alignment, and Remediation

## Summary

Uncontracted code comprises any runtime logic, methods, classes, parameters, or functions in implementation modules (`lib/<name>.py` and `lib/<name>_impl.py`) or unit test suites (`tests/<name>_test.py`) that are used outside of their defining file and lack an upstream behavioral contract in low-level specifications (`low/<name>.pyi` and `low/<name>_impl.pyi`) and their governing scenarios, planning canvases, and high-level specifications. Functions, helper routines, and class members not used outside of their defining file are private implementation details and do not need to be contracted in low-level specifications or tagged as uncontracted. Unit test suites (`tests/<name>_test.py`) are external callers; test modules that import or assert against functions, helpers, or members count as external usage, and every tested behavior or symbol must be grounded in contracts in `low/<name>.pyi`. Subtypes fulfilling base class or protocol contracts inherit their behavioral contracts transitively across the inheritance hierarchy; inherited members do not need to be re-declared in derived `low/<name>_impl.pyi` stubs. Standard lifecycle registration mechanisms (`__initialize__` and lifecycle initialization patterns) defined by Cleanroom guides are recognized framework facilities rather than uncontracted defects. Auditing cross-references external-facing declarations against `low/<name>.pyi`: contracted code is annotated with brief inline comments linking methods and critical control-flow branches to the specific postconditions, invariants, or sequencing guarantees they fulfill, while uncontracted declarations used outside the file are tagged inline using standardized `# NONCONTRACTED: <reason>` comments and cataloged in an inventory tracking document (`uncontracted_code_inventory.md`) before any code is modified or deleted.

Remediation evaluates each uncontracted inventory entry against strict decision criteria: dead, redundant, speculative, or uncontracted defensive fallback logic is recommended for safe deletion, whereas essential capabilities, active caller requirements, and external data formats are recommended for specification retrofitting. In accordance with the mandatory Specification-First (HLS-First) rule, retrofitting never patches `lib/` or `low/` directly; missing contracts must first be authored in High-Level Specifications (`high/<name>.md` or external boundary specifications `high/<name>_ext.md`) and cascaded down the complete pipeline (`high` → `planning` → `scenarios` → `low` → `lib` → `tests`). All remediation actions are strictly gated on explicit human review and approval of the inventory recommendations. Following human approval, safe deletions are executed first, specification cascades are executed second, all `# NONCONTRACTED:` comments are pruned from code, and the inventory document is removed once full repository verification confirms zero lint errors, zero type errors, and complete test suite success.

> META: "This guide establishes standard procedures for auditing library and test code against low-level specifications, documenting contract alignment, tagging uncontracted logic, maintaining inventory artifacts, formulating deletion versus HLS-first retrofitting recommendations, gating execution on human review, and cleaning up temporary audit artifacts."

## Specification alignment commenting in library code

- [ ] Every public method and function in `lib/<name>.py` and `lib/<name>_impl.py` accessed outside the module includes a concise inline comment or docstring citing the specific contract in `low/<name>.pyi` it realizes
- [ ] Contractual postconditions (`MUST <outcome>.` and `WHEN <condition>, MUST <outcome>.`) in `low/<name>.pyi` are referenced beside their implementing control-flow branches, validation checks, and return statements
- [ ] Invariant maintenance logic (`INVARIANTS:`) in `low/<name>.pyi` is annotated at internal state mutation points
- [ ] Inherited contracts fulfilled across subtyping hierarchies cite the declaring base protocol or class without requiring redundant re-declaration in derived `.pyi` stubs
- [ ] Module-level procedural facade functions and top-level entrypoints cite top-level postconditions under `__orphan__()` in `low/<name>.pyi`
- [ ] Comments on specification alignment remain concise, factual, and devoid of conversational prose or speculative commentary

## Uncontracted code identification and tagging

- [ ] Implementation modules (`lib/<name>.py`, `lib/<name>_impl.py`) and test modules (`tests/<name>_test.py`) are audited against `low/<name>.pyi` and `low/<name>_impl.pyi` for external contract surface
- [ ] Functions, helpers, and class members not used outside of their defining file are private implementation details and do not need to be contracted or tagged as uncontracted
- [ ] Unit tests are external callers; all functions, helpers, and members imported or exercised by unit test suites are external surface requiring contracts in `low/<name>.pyi`
- [ ] Inherited methods and properties defined on base protocols or parent classes are contracted through inheritance and do not need to be re-mentioned in derived `.pyi` stubs
- [ ] Lifecycle registration routines (`__initialize__` and lifecycle initialization patterns) defined by Cleanroom guides are recognized lifecycle infrastructure and are excluded from uncontracted tagging
- [ ] Module-level procedural facade functions and top-level entrypoints are contracted in low-level specifications under `def __orphan__() -> None:` in accordance with low-level specification structure rules
- [ ] Any method, helper function, class, parameter, or branch accessed outside of its defining file that lacks a corresponding declaration or contract clause in `low/<name>.pyi` is marked as uncontracted
- [ ] Every identified uncontracted code construct used outside its defining file is tagged inline with a standardized comment: `# NONCONTRACTED: <description of behavior and rationale for uncontracted status>`
- [ ] Standardized `# NONCONTRACTED:` comment tags are placed immediately preceding the uncontracted definition, branch, or block
- [ ] Unit tests asserting behaviors, parameters, or outcomes not grounded in `low/<name>.pyi` contracts are tagged with `# NONCONTRACTED:` comments
- [ ] Automated search across all source and test directories identifies all occurrences of `# NONCONTRACTED:` markers across the codebase

## Inventory documentation and cataloging

- [ ] Before deleting code or modifying specifications, all tagged uncontracted items are cataloged in an inventory document (`uncontracted_code_inventory.md`)
- [ ] The inventory document organizes findings by component and target package
- [ ] Each inventory entry records the target file, symbol or member name, line range, and observed runtime behavior
- [ ] Each inventory entry documents the current specification status across `high/<name>.md`, `planning/<name>.md`, and `low/<name>.pyi`
- [ ] The inventory document enumerates all uncontracted instances comprehensively before initiating code deletions or specification modifications

## Remediation recommendation criteria

- [ ] Each uncontracted inventory entry is evaluated to determine whether deletion or specification modification is appropriate
- [ ] Uncontracted code is recommended for safe deletion when the logic is dead, orphaned, unused by active callers, or redundant with standard library or collaborator capabilities
- [ ] Uncontracted defensive validation branches that violate caller assumptions (`ASSUMPTIONS:`) or handle uncontracted impossible states are recommended for deletion
- [ ] Legacy prototype functions, obsolete command aliases, and uncontracted test-only conveniences are recommended for deletion
- [ ] Uncontracted code is recommended for specification retrofitting when the functionality is essential for runtime system execution, active external integration, or critical lifecycle management
- [ ] External data schemas, serialization envelopes, and manifest headers required by implementation logic are recommended for formalization in external boundary specifications (`high/<name>_ext.md` and `low/<name>_ext.pyi`)
- [ ] Every specification modification recommendation explicitly specifies the High-Level Specification changes required to cascade the contract downstream

## Human review gating and decision recording

- [ ] The inventory document presents explicit recommendations (Delete vs. Modify Specification) alongside their technical rationale for human review
- [ ] No code is deleted and no specifications are modified prior to receiving explicit human review and approval
- [ ] Modifications requested during human review are incorporated into the inventory document before proceeding to execution
- [ ] The inventory document acts as the authoritative plan of record during the execution phases

## Execution of approved deletions and divergence fixes

- [ ] Approved deletions and divergence corrections are executed first before beginning specification cascades
- [ ] Deleted uncontracted methods, functions, and classes are pruned cleanly without leaving orphaned references or dangling imports
- [ ] Callers and unit tests expecting deleted uncontracted behavior are pruned or redirected to contracted alternative services
- [ ] Divergent parameter names or mismatched signatures are aligned to canonical interfaces
- [ ] Static type checking and unit test suites are executed to verify that approved deletions do not break contracted system behavior

## Specification-first cascading for retained code

- [ ] For all uncontracted code approved for retention, contract authoring begins exclusively in High-Level Specifications (`high/<name>.md` or `high/<name>_ext.md`)
- [ ] Stealth edits and direct retrofitting patches applied directly to `lib/<name>.py` or `low/<name>.pyi` without upstream HLS authoring are prohibited
- [ ] External formats, manifest formats, and third-party types are formalized in `high/<name>_ext.md` and `low/<name>_ext.pyi`
- [ ] High-Level Specification changes cascade systematically through Planning Canvases (`planning/<name>.md`), Scenarios (`scenarios/<name>.md`), and Low-Level Specifications (`low/<name>.pyi`)
- [ ] Low-Level Specifications maintain strict contract standards, omitting top-level functions and structuring contracts via classes, protocols, dataclasses, and normative postconditions
- [ ] Library implementations (`lib/<name>.py`) and unit tests (`tests/<name>_test.py`) are aligned to the updated low-level specifications, incorporating specification alignment comments

## Post-remediation verification and cleanup

- [ ] Standardized `# NONCONTRACTED:` comments are removed from each code block once the code is deleted or fully contracted
- [ ] Repository-wide automated search confirms zero `# NONCONTRACTED:` comment markers remain in source or test files
- [ ] Repository specification linters confirm that all high, planning, and low specifications pass structural and boundary checks
- [ ] Static type checkers report zero errors and zero warnings across all packages
- [ ] Complete unit test suites execute cleanly with zero test failures
- [ ] The temporary inventory document (`uncontracted_code_inventory.md`) is removed once full repository verification succeeds
