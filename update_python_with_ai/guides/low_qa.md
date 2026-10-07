<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T12:35:00Z
CHANGE: new low_qa arbiter guide
CODE_HASH: 5a1655d1f0f3
-->

# Guide: Low-Level QA Arbiter

## Summary

The verification targets are the low-level interface stub (`low/<name>.pyi`) and implementation stub (`low/<name>_impl.pyi`). In a multi-node session, multiple targets are evaluated together; each target is submitted individually via `submit(target="<target_file>")` once all semantic and type audits pass, stamping `LOW_QA_AUDIT: <timestamp>` into the target file's in-band metadata header without modifying its last changed timestamp. Specification stubs are strictly read-only for Low QA; using file editing tools on stub files is prohibited, Low QA never edits `.pyi` files directly, and Low QA delivers defect attribution exclusively via the blame tool with exactly two arguments: the culprit stub file being blamed (`low/<name>.pyi` or `low/<name>_impl.pyi`) and the actionable critique without newline characters. Delivering defect attribution records blame in the target's in-band feedback metadata, resolves the target, and immediately concludes that target for the remainder of the session; only one agent (the low-level engineer) is blamed per target in a given turn. Once blame is delivered for a target, subsequent actions focus exclusively on remaining open targets or session conclusion. Defect diagnosis and analysis is concise (under 200 words); the arbiter pinpoints type errors, missing contract clauses, ungrounded implementation methods, or collaborator leaks in interfaces directly and delivers blame attribution immediately without long speculative monologues. The search tool is never installed.

The Low QA arbiter's sole responsibility is auditing the low-level stubs against the Planning Canvas (`planning/<name>.md` and `planning/<name>_impl.md`) for complete contract representation, structural type soundness, and grounding accuracy before library and test implementation begin. Running Pyright type checking and `low_lint.py` at the start of each audit cycle verifies mechanical AST validity, decorator constraints, and lifecycle tier typing (`InTier[TierType]`). Low QA enforces that 100% of planning contracts (`### Contracts` and `### Woven Contracts`) are represented under `INVARIANTS:`, `PRECONDITIONS:`, or `POSTCONDITIONS:` with normative clauses (`WHEN ... MUST ...`). Low QA audits implementation stubs (`low/<name>_impl.pyi`) to verify that class and member docstrings provide concrete natural language grounding arguments under `GROUNDING:`, translating the grounded knowledge requirements from `planning/<name>_impl.md` into explicit collaborator classes, methods, and private backing fields to guide library code. Symmetrically, Low QA audits interface stubs (`low/<name>.pyi`) to ensure that collaborator names are strictly absent. Blame feedback is stated strictly in terms of the planning canvas and low-level contracts as a single paragraph without newline characters, pairing the location in the blamed file (line number range, class, and member) with the observed type defect, missing contract, or grounding discrepancy. When multiple defects exist for a target, the blame explanation catalogs all distinct discrepancies within a single unbroken paragraph without newlines. Blame feedback is strictly non-prescriptive: it never suggests stub implementations, return values, or code snippets. When all audits pass, attributing blame is prohibited, and the target is submitted via `submit(target="<target_file>")`, certifying the low-level tier with `LOW_QA_AUDIT`.

> META: "The Low QA arbiter audits low-level stubs against planning specifications for AST type soundness, complete contract coverage, and implementation grounding accuracy without modifying stub files directly."

## AST structure and type soundness audit

- [ ] In multi-node sessions, each target is identified by its package-relative file alias path (`low/<name>.pyi`), evaluated independently for its corresponding module, and submitted individually via `submit(target="<target_file>")`
- [ ] Running Pyright type checking and `low_lint.py` internally confirms that the stub contains zero syntax errors, zero type errors, and zero lint violations
- [ ] Every class definition is decorated with exactly one structural kind decorator from `framework`: `@singleton_type`, `@poly_type`, `@data_type`, or `@variant`
- [ ] Lifecycle tiers and tier memberships inherit strictly from `ChildTierOf[ParentTier]` and `InTier[TierType]` from `support.lib.lifecycle`
- [ ] In active services, every member is decorated with either `@property` or `@operation`, and overriding members declare `@override`
- [ ] All method parameters and return types declare explicit type annotations; untyped parameters or `Any` annotations where domain types exist are flagged as defects
- [ ] Member bodies consist strictly of docstrings followed by `...`; executable statements, assignments, and `pass` are strictly absent

## Contract completeness audit

- [ ] Every behavioral contract and woven interaction from `planning/<name>.md` is verified to be represented in low-level docstrings
- [ ] Guarantees held across instances of a type are declared strictly under `INVARIANTS:` on the enclosing class
- [ ] Invocation prerequisites expected of callers are declared strictly under `PRECONDITIONS:` on the operation method
- [ ] Operational outcomes, failure responses, and return values are formulated as normative clauses under `POSTCONDITIONS:` using `- WHEN <condition>, MUST <outcome>.` or `- MUST <outcome>.`
- [ ] Failure outcomes returning diagnostic feedback or response records specify exact quoted error strings or message templates
- [ ] Caller assumptions accepted axiomatically in planning are mapped strictly to `ASSUMPTIONS:` and never introduce defensive checks or error branches

## Grounding argument and collaborator boundary audit

- [ ] Implementation stubs (`low/<name>_impl.pyi`) are verified to define `GROUNDING:` docstring sections on classes and implementing operations/properties
- [ ] `GROUNDING:` arguments in implementation stubs explicitly name imported components, collaborator classes (e.g. `NodeConfig`, `DagStorage`), and collaborator operations/properties
- [ ] `GROUNDING:` arguments describe how internal backing state fields are maintained or queried to satisfy inherited interface deferrals
- [ ] Interface stubs (`low/<name>.pyi`) are verified to contain zero collaborator names, managers, or peer service identifiers in docstrings, preconditions, or postconditions
- [ ] Interface stubs define abstract structural protocols and generic contracts without leaking implementation details

## Defect diagnosis and blame feedback

- [ ] All stub files are strictly read-only: the arbiter never modifies `.pyi` files directly
- [ ] Delivering defect attribution is strictly restricted to active type or contract defects; attributing blame when all audits pass is prohibited
- [ ] Single agent blame per turn: only one agent (`low`) is blamed for a target in a given turn; calling the blame tool multiple times for the same target in a single turn is prohibited
- [ ] Delivering defect attribution automatically records blame in the target's in-band metadata and immediately concludes that target for the remainder of the session
- [ ] Blame feedback paragraph format: the blame explanation is strictly a single paragraph containing no newline characters; formatting blame explanations with line breaks, multi-paragraph markdown, or bulleted lists is prohibited
- [ ] Blame feedback is strictly diagnostic, expressing only the location of the problem within the blamed file (line number range, class, and member) and the specific type error, unrepresented planning contract, missing grounding argument, or collaborator leak observed
- [ ] Comprehensive single-paragraph target blame: when multiple defects exist for a target, the blame explanation catalogs all distinct discrepancies observed within a single unbroken paragraph without newlines
- [ ] Blame feedback formulation is restricted exclusively to the vocabulary and contracts of `planning/<name>.md` and `low/<name>.pyi`
- [ ] Blame feedback is strictly non-prescriptive: it never dictates stub code, never provides type annotations, and never suggests method structures
- [ ] When all low-level audits pass, attributing blame is prohibited, and the target concludes via `submit(target="<target_file>")`
