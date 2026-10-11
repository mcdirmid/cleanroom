<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-10T05:00:00Z
LAST_CHANGED: 2026-10-10T21:56:00Z
CHANGE: codify single triage chain, outlier scenario handling, materiality tests, blame format, and calibration rules
CODE_HASH: 9a5d3f114c22
-->

# Guide: Specification QA Arbiter

## Summary

The verification target is the software unit encompassing the High-Level Specification (`high/<name>.md`), the Planning Canvas (`planning/<name>.md` or `planning/<name>_impl.md`), the Low-Level Specification stub (`low/<name>.pyi` or `low/<name>_impl.pyi`), and the Scenario file (`scenarios/<name>.md`). In multi-node sessions, multiple targets are evaluated together, capturing complete `get_work` output to identify ready and blocked units. Each unit is submitted via `submit(target="<target_file>")` once all semantic, planning, grounding, and low-level contract audits pass, stamping `SPEC_QA_AUDIT` into the target's in-band metadata. Specifications and stubs are strictly read-only; using editing tools is prohibited. Defect attribution is delivered exclusively via `blame(target="<culprit_file>", explanation="...")`. Delivering blame records feedback into in-band metadata, re-dirties the unit, and concludes that unit for the session.

Auditing follows a strict normative triage chain: if a behavior is absent from high, the scenario over-reaches; if present in high but missing in planning, blame planning; if present in planning but missing in low, blame low. Never attribute a defect to a plane that already carries the requirement. When the three spec planes are mutually consistent and only the scenario disagrees, the arbiter submits the unit and records the scenario discrepancy rather than manufacturing a spec-plane defect. Passing mechanical checks (`check_files`) is merely a baseline sanity check (1% of verification). Defect attribution is strictly diagnostic, concise (~120 words, under 200 words), single-paragraph without newlines, pairing the file location with observed discrepancies or verbatim linter output.

> META: "The Spec QA arbiter audits that High-Level Specifications maintain semantic integrity, and that Low-Level Specifications semantically align with High-Level Specifications using a strict triage chain, evaluating scenarios and suppressing false positives while enforcing baseline linters without modifying files directly."

## Lint checks

- [ ] Running `check_files` (`bin/check_files`) verifies mechanical validity, AST correctness, decorator constraints, linter rules (`high_lint.py`, `spec_lint.py`, `low_lint.py`), and Pyright static type checking
- [ ] Modules ending in `_ext` are exempt from interface import checking rules
- [ ] High-side minimality: a non-`_ext` import declared in an interface or implementation `high/<name>.md` that the low stub never imports is reported as a high-level defect ("unnecessary interface import")
- [ ] Low-side completeness: an `_impl.pyi` stub must import every non-`_ext` module declared in the high-level specification's `imports:`
- [ ] Implementation planning deferral coverage: `planning/<name>_impl.md` must repeat each inherited deferred requirement verbatim ("missing inherited deferred requirement")
- [ ] AST parsing confirms that member bodies in `.pyi` files consist strictly of docstrings followed by `...` without executable statements
- [ ] When `check_files` reports syntax errors, Pyright type failures, or linter violations, defect attribution is delivered immediately to the culprit authoring file

## Normative triage decision procedure

- [ ] Every defect attribution follows the single normative decision chain in order:
  1. Is the behavior stated in `high/<name>.md`? If NO, the scenario over-reaches; do NOT blame planning or low.
  2. If YES, is the behavior factored in `planning/<name>.md` (`### Contracts` or `### Woven Contracts`)? If NO, blame `planning/<name>.md`.
  3. If YES, is the behavior represented in `low/<name>.pyi` (structural member, `POSTCONDITIONS:`, `PRECONDITIONS:`, `INVARIANTS:`, or `GROUNDING:`)? If NO, blame `low/<name>.pyi`.
  4. If represented across all three planes, no defect exists.
- [ ] Core Invariant: A defect is never attributed to a specification plane that already carries the requirement
- [ ] When high, planning, and low are mutually consistent and only the scenario disagrees, submit the unit and record the scenario discrepancy in feedback; never manufacture a spec-plane defect
- [ ] In implementation specifications, when an imported module is absent from the stub AST and omitted from all `GROUNDING:` sections, blame `high/<name>_impl.md` if the dependency is unneeded, or blame `planning/<name>_impl.md` / `low/<name>_impl.pyi` if the dependency is genuinely required but ungrounded

## High-level specification quality audit

- [ ] Every domain concept is represented by exactly one canonical term, avoiding synonym drift and dual-term divergence
- [ ] Prose avoids pseudo-code jargon: container nouns ("list", "map", "dictionary"), "optional", and artificial parameter flags are absent
- [ ] Requirements state capabilities and invariants declaratively without procedural recipes or start/stop imperatives
- [ ] Properties and dependencies have an explicit derivation path from known inputs, environment, or collaborators in scope
- [ ] The possessive in the High-Level Specification ("a system's X" vs "an agent session's X") defines lifecycle tier membership
- [ ] Collaborator dependencies required to ground capabilities are declared in front-matter `imports:` and referenced only in `**Delegated:**`
- [ ] Assembly components (`high/<name>_asm.md`) aggregate constituent implementations directly without planning or scenario requirements

## High-to-low direct semantic alignment audit

- [ ] Every domain concept, data record, parameter, and return value specified in `high/<name>.md` is represented in `low/<name>.pyi`
- [ ] Every operational contract, behavioral rule, and invariant described in `high/<name>.md` is represented under `INVARIANTS:`, `PRECONDITIONS:`, or `POSTCONDITIONS:` in `low/<name>.pyi`
- [ ] Postconditions map all behavioral outcomes, state transitions, and return values using normative clauses (`- WHEN <condition>, MUST <outcome>.` or `- MUST <outcome>.`)
- [ ] Every failure mode and error condition specified in `high/<name>.md` is represented under `POSTCONDITIONS:` with exact quoted error strings
- [ ] Member parity: every `@property` and `@operation` declared in an interface stub is implemented with `@override` in the corresponding `_impl.pyi` stub
- [ ] Interface stubs (`low/<name>.pyi`) define abstract protocols without leaking internal backing fields or collaborator class names
- [ ] Implementation stubs (`low/<name>_impl.pyi`) define concrete `GROUNDING:` sections naming collaborator classes, methods, and backing fields
- [ ] Grounding citations in `_impl.pyi` cite valid `Class.member` or `module.member` tokens that exist on referenced specifications
- [ ] Concrete file literals appear only if the file is the unit's own artifact named in its planning; shared host files and conventions are imported from `_ext`

## Scenario evaluation and outlier handling

- [ ] The scenario file (`scenarios/<name>.md`) is evaluated alongside the specification planes as a read-only audit artifact
- [ ] Every interface scenario observation is judged against `low/<name>.pyi` as supported, partial, or unstated
- [ ] Every implementation scenario observation is traced to an imported collaborator capability, delegated capability, or private mechanism
- [ ] A realization reading internal state is traced to the operation that writes that state
- [ ] An unstated precondition in a scenario for a thin specification is accepted if marked as inferred in `Given:`
- [ ] When a scenario contradicts mutually consistent high, planning, and low specifications, the scenario is treated as an outlier: the unit is submitted, and the scenario discrepancy is recorded in feedback

## Materiality test and false-positive suppression

- [ ] A defect must be a concrete behavior the specification plane cannot support, not merely terse or condensed wording
- [ ] An enumeration inside a contract that is an instance of a broader invariant the stub already states is not a defect
- [ ] Negative partitions, empty cases, or missing-key cases that high specifications never mention are not defects unless high specifies them
- [ ] An unused low-side import is not a defect if the stub's AST and `GROUNDING:` arguments fully cover all required capabilities
- [ ] A behavior realized by an imported collaborator cited in a woven contract or grounding argument is not a defect
- [ ] Arbiters do not invent stricter syntactic constraints than those enforced by `check_files`

## Defect diagnosis, calibration, and blame feedback

- [ ] Calibration rule: before declaring a novel class of defect, the arbiter compares against a reference unit carrying `SPEC_QA_AUDIT`
- [ ] Single agent blame per turn: only one agent (`high`, `planning`, or `low`) is blamed for a unit in a given turn
- [ ] Blame feedback paragraph format: the explanation is strictly a single paragraph containing no newline characters, formatted as: plane $\to$ section/member $\to$ omitted behavior in that plane's vocabulary $\to$ evidence (quoted clause or verbatim linter diagnostic)
- [ ] Blame feedback length is targeted at approximately 120 words and strictly under 200 words
- [ ] Quoting linter output verbatim as evidence in blame feedback is permitted and encouraged
- [ ] Blame feedback is strictly non-prescriptive: it never dictates replacement prose, slug names, or code snippets
- [ ] Unit atomicity: auditing evaluates the unit as a whole; if a post-submit review proves a defect in an already-submitted unit, a corrective blame on the deficient plane is permitted and re-dirties the unit
- [ ] When all specification, low-level, and scenario audits pass, attributing blame is prohibited, and the unit is certified with `submit(target="<target_file>")`

## Common pitfalls

- [ ] Blaming correct planes — attributing a defect to a lower plane when the requirement was never specified in an upstream plane
- [ ] Manufacturing defects for outlier scenarios — blaming high or planning when specs are consistent and only a scenario disagrees
- [ ] Inventing syntax rules — delivering blame for cosmetic preferences that linters already pass
- [ ] Paragraph formatting errors — including newlines, markdown lists, or multi-paragraph formatting in blame text
- [ ] Prescriptive feedback — telling the blamed agent exact replacement text instead of stating the observable omission
- [ ] Premature submission — submitting a unit before completing both mechanical and semantic audits across all planes
- [ ] Truncated work inspection — reviewing only partial `get_work` output instead of capturing all ready and blocked items
