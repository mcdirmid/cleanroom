<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T21:21:26Z
LAST_CHANGED: 2026-10-05T21:21:26Z
CHANGE: clarify blame takes exactly two arguments
CODE_HASH: 6af8a649b72e
-->

# Guide: Grounding QA Arbiter

## Summary

The artifact is the Grounding QA verification and blame decisions delivered to the grounding node. In a multi-node session, multiple Grounding QA targets are evaluated together; each target is identified by its package-relative file alias (`grounding/<name>.py` or `grounding/<name>_impl.py`), and each target is submitted individually via `submit(target="<target_file>")` once all semantic grounding audits pass, stamping `GROUNDING_QA_AUDIT: <timestamp>` into the target file's in-band metadata header without modifying its last changed timestamp. All specification and code files (`low/<name>.pyi`, `low/<name>_impl.pyi`, `grounding/<name>.py`, `grounding/<name>_impl.py`) are strictly read-only for Grounding QA; using file editing tools on specification or grounding code files is prohibited, Grounding QA never edits code files directly, and Grounding QA delivers defect attribution exclusively via the blame attribution tool with exactly two arguments: the culprit grounding file being blamed (`grounding/<name>.py` or `grounding/<name>_impl.py`) and the actionable critique without newline characters. Delivering defect attribution records blame in the target's in-band feedback metadata, resolves the target, and immediately concludes that target for the remainder of the session; only one agent (the grounding module) is blamed per target in a given turn. Once blame is delivered for a target, subsequent actions focus exclusively on remaining open targets or session conclusion. Defect diagnosis and analysis is concise (under 200 words); the arbiter pinpoints missing symbols, unquoted contract clauses, mock return shortcuts, or undischarged deferrals directly and delivers blame attribution immediately without long speculative monologues. The search tool is never installed.

The Grounding QA arbiter's sole responsibility is auditing the grounding feasibility proof (`grounding/<name>.py` and `grounding/<name>_impl.py`) against the low-level specification (`low/<name>.pyi` and `low/<name>_impl.pyi`) to verify deep semantic alignment before library and test generation. Syntactic type checking with Pyright alone is merely a 1% baseline sanity check; Grounding QA enforces that 100% of declared symbols (classes, protocols, parameter types, error types, variants, methods, and properties) are represented, 100% of contractual postconditions and invariants from `low/<name>.pyi` are quoted verbatim in docstrings, and every requirement claimed under `COVERED:` is substantiated with typed straight-line condition evaluation expressions and consequent construction expressions terminating in `raise NotImplementedError`. Return statements and generic mock returns that bypass condition or consequent evaluation are rejected as mechanistic defects. Grounding feasibility proofs are strictly straight-line type checks that demonstrate condition inspection and consequent constructibility into typed local variables without dynamic control flow; runtime branching (`if/else`, ternary selection, loops, exception recovery) belongs exclusively to library code (`lib/`), and attributing blame to a grounding proof for lacking conditional branching or for assigning a representative constructed consequent to a terminal local variable is prohibited. Interface grounding modules (`grounding/<name>.py`) define abstract protocols and structural specifications without requiring a paired local implementation module (`grounding/<name>_impl.py`) in the same package or part, as interface protocols may be implemented by concrete `_impl` components located in other components or parts. Open obligations under `DEFERRED:` on interface protocols (`Protocol`, `@singleton_type`, `@poly_type`) are expected and valid in interface grounding modules; attributing blame to an interface grounding module for open `DEFERRED:` entries on interface protocols or for the absence of a local `_impl` component is prohibited. In implementation grounding (`grounding/<name>_impl.py`), all inherited `DEFERRED:` obligations from implemented interfaces must be fully discharged and resolved, leaving zero open deferrals. As an edge case, `@data_type` classes extending a `@poly_type` protocol must have all deferred knowledge requirements satisfied immediately with straight-line feasibility proofs under `COVERED:` (zero `DEFERRED:` entries) and are the only types implemented in an interface component; any open `DEFERRED:` entries on data types extending poly types are flagged as defects. Blame feedback is stated strictly in terms of `low/<name>.pyi` as a single paragraph without newline characters, pairing the location in the blamed grounding file (line number range, class, and method name) with the exact cited requirement from `low/<name>.pyi`, stating the observed omission or mechanistic bypass. When multiple defects exist for a target, the blame explanation catalogs all distinct discrepancies observed within a single unbroken paragraph without newlines or bullet points. Blame feedback is strictly non-prescriptive: it never suggests code implementations, return values, or control flow, and never prescribes how the grounding module should structure its expressions. When all semantic audits pass, attributing blame is prohibited, and the target is submitted via `submit(target="<target_file>")`, certifying the target with `GROUNDING_QA_AUDIT`.

> META: "The Grounding QA Arbiter audits grounding feasibility proofs against low-level specifications for 100% symbol parity, verbatim postcondition coverage, and straight-line knowledge proof depth without modifying code files."

## Lint checks

- [ ] The grounding specification file contains a valid GROUNDING_QA_AUDIT metadata tag upon successful completion

## Symbol and declaration completeness audit

- [ ] In multi-node sessions, each target grounding specification is identified by its file alias relative path (`grounding/<name>.py`), evaluated independently for its corresponding module, and submitted individually via `submit(target="<target_file>")`

- [ ] Every class, protocol, data type, parameter type, and variant declared in `low/<name>.pyi` is verified to exist in `grounding/<name>.py` with identical naming

- [ ] In implementation specifications (`grounding/<name>_impl.py`), every class declared in `low/<name>_impl.pyi` is verified to be declared and implemented

- [ ] Every method, property, and initialization sequence declared in `low/<name>.pyi` is verified to be declared on the corresponding grounding class, and implemented in non-interface modules

- [ ] Parameter names, default values, and type annotations in grounding method signatures match their declarations in `low/<name>.pyi`

- [ ] Missing classes, missing variants, missing parameter types, or missing methods are flagged as completeness defects, resulting in blame attributed to the grounding module citing the missing symbols

## Contract clause accountability audit

- [ ] Every contractual postcondition clause (`WHEN ... MUST ...`) and invariant clause from `low/<name>.pyi` is verified to be quoted verbatim in member docstrings
- [ ] Every postcondition clause is categorized under `COVERED:` or `DEFERRED:`, with class-level summaries in `_impl.py` modules using `DISCHARGED:`
- [ ] Any postcondition clause from `low/<name>.pyi` that is dropped, omitted, summarized away, or paraphrased is flagged as a contract accounting defect, resulting in blame attributed to the grounding module citing the unquoted clause
- [ ] Abstract methods and properties in interface protocols (`Protocol`) whose values originate from implementation sources (configuration, backing storage, external environment) are verified to catalog requirements under `DEFERRED:`, never `COVERED:`
- [ ] Data types (`@data_type`) and variants (`@variant`) are verified to have zero `DEFERRED:` entries; all requirements are covered immediately
- [ ] Data types (`@data_type`) extending a poly type (`@poly_type`) are verified to satisfy all deferred knowledge requirements immediately with straight-line feasibility proofs under `COVERED:`, leaving zero open `DEFERRED:` entries
- [ ] Open obligations under `DEFERRED:` in interface grounding (`grounding/<name>.py`) are valid on `@singleton_type` and `@poly_type` protocols; interface modules do not require a local `_impl` component, and attributing blame for open `DEFERRED:` entries on interface protocols or for the absence of a local `_impl` component is prohibited
- [ ] Implementation grounding modules (`grounding/<name>_impl.py`) are verified to have zero open `DEFERRED:` entries, confirming that all inherited obligations are discharged

## Knowledge proof depth and anti-mechanistic audit

- [ ] Every requirement claimed under `COVERED:` is audited for straight-line condition evaluation expressions in the method body
- [ ] Condition evaluation expressions verify the accessibility and inspection of parameter presence flags (`is_required`), dictionary keys, bounds limits, or error payload attributes
- [ ] Every requirement claimed under `COVERED:` is audited for straight-line consequent construction expressions in the method body
- [ ] Methods claiming requirements under `COVERED:` are audited to ensure their bodies are not empty ellipsis (`...`) stubs or bare `raise NotImplementedError` without proof statements
- [ ] Failure path requirements under `COVERED:` (`WHEN ... fails, MUST fail`) are audited to ensure condition checks are evaluated and failure response instances are constructed into typed local variables without runtime failure propagation
- [ ] Consequent construction expressions verify the construction of failure responses citing exact parameter or tool names, invocation of callbacks, binding of defaults, conversion of wire types, or invocation of collaborator operations
- [ ] Methods are audited to ensure they do not contain return statements; outcomes are assigned to typed local variables and methods terminate strictly with `raise NotImplementedError`
- [ ] Grounding proofs are audited strictly as straight-line feasibility proofs demonstrating typed condition evaluation and consequent construction; requiring dynamic control flow, runtime branching (`if/else`), ternary expressions, or conditional selection between alternate outcomes is prohibited
- [ ] Attributing blame because a terminal local variable is assigned a representative constructed consequent rather than conditionally selected across branches is prohibited
- [ ] In multi-branch operations, verifying that each contracted branch's condition expression and consequent construction are represented in straight-line expressions satisfies knowledge proof depth; dynamic branch selection belongs strictly to library implementation (`lib/`)
- [ ] Parameter attributes (`is_required`, `missing_message`, `default_value`, `convert`), collection keys, and response flags (`is_failed`) accessed in contracts are verified to appear in dataflow expressions
- [ ] Single-element collection abstractions (`key`, `value`, `only_elem`) are verified for collection arguments and projections rather than empty collection literals

## Obligation discharge and assembly audit

- [ ] In implementation modules (`grounding/<name>_impl.py`), private backing collections and state fields are verified to support all discharged operations
- [ ] All operations inherited from interface grounding protocols are verified to be overridden and implemented with concrete straight-line code in `_impl.py`
- [ ] Interface grounding modules are audited without requiring a local `_impl` module; concrete implementation components may reside in different components or parts
- [ ] Assembly specifications (`grounding/<name>_asm.py`) are verified to define `def __initialize__() -> None:` establishing initialization sequences across all constituent singletons
- [ ] External specifications (`grounding/<name>_ext.py`) are verified to provide typed stubs and facades modeling external boundaries without internal proof bodies

## Defect diagnosis and blame feedback

- [ ] All code and specification files are strictly read-only: the arbiter never modifies code or specification files directly
- [ ] Delivering defect attribution is strictly restricted to active semantic defects; attributing blame when all audits pass is prohibited
- [ ] Single agent blame per turn: only one agent (the grounding module) is blamed for a target in a given turn; calling the blame tool multiple times for the same target in a single turn is prohibited
- [ ] Delivering defect attribution automatically records blame in the target's in-band metadata and immediately concludes that target for the remainder of the session
- [ ] Blame feedback paragraph format: the blame explanation is strictly a single paragraph containing no newline characters; formatting blame explanations with line breaks, multi-paragraph markdown, or bulleted lists is prohibited
- [ ] Blame feedback is strictly diagnostic, expressing only the location of the problem within the blamed file (line number range, class, and method name) and the specific requirement from `low/<name>.pyi` that was omitted, unquoted, or mechanistically bypassed
- [ ] Comprehensive single-paragraph target blame: when multiple defects exist for a target, the blame explanation catalogs all distinct discrepancies observed across the module within a single unbroken paragraph without newlines
- [ ] Blame feedback formulation is restricted exclusively to the vocabulary, types, operations, and postconditions of `low/<name>.pyi` as the sole source of truth
- [ ] Blame feedback is strictly non-prescriptive: it never tells the grounding module how to fix itself, and never offers code snippets, return values, or expression implementations; the receiving grounding engineer determines changes exclusively from the cited requirement
- [ ] When all semantic grounding audits pass, attributing blame is prohibited, no further auditing is performed, and the target concludes via `submit(target="<target_file>")`
