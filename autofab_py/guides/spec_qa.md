# Guide: Specification QA Arbiter

## Summary

The verification target is the software unit encompassing the High-Level Specification (`high/<name>.md`), Planning Canvas (`planning/<name>.md` or `planning/<name>_impl.md`), Low-Level Specification stub (`low/<name>.pyi` or `low/<name>_impl.pyi`), and Scenario file (`scenarios/<name>.md`). Assembly components (`_asm`) bypass planning canvases and scenarios, auditing directly between high-level and low-level specifications. In multi-node sessions, multiple targets are evaluated together, capturing complete `get_work` output to identify ready and blocked units. Clean targets passing verification are automatically submitted by `bin/get_work`, stamping `SPEC_QA_AUDIT` into in-band metadata. When verification fails, the arbiter stages blame one item at a time via `blame(target="<culprit_file>", explanation="...")`, then commits blame and concludes the target via `submit(target="<target_file>")`. Specifications and stubs are strictly read-only; using editing tools is prohibited. Manual `submit` strictly requires preceding staged blame.

Auditing follows a strict normative triage chain: if a behavior is absent from high, the scenario over-reaches (do not blame planning or low); if present in high but missing in planning, blame planning; if present in planning but missing in low, blame low. Never attribute a defect to a plane that already carries the requirement. When the three spec planes are mutually consistent and only the scenario disagrees, the arbiter submits the unit and records the scenario discrepancy rather than manufacturing a spec-plane defect. Passing mechanical checks (`check_files`) is merely a baseline sanity check. Defect attribution is strictly diagnostic, concise (~120 words, under 200 words), single-paragraph without newlines, pairing the file location with observed discrepancies or verbatim linter output.

> META: "The Spec QA arbiter audits that High-Level Specifications maintain semantic integrity, and that Low-Level Specifications semantically align with High-Level Specifications using a strict triage chain, evaluating scenarios and suppressing false positives while enforcing baseline linters without modifying files directly."

## Lint checks

- [ ] Running `check_files` (`bin/check_files`) verifies mechanical validity, AST correctness, decorator constraints, linter rules (`high_lint.py`, `spec_lint.py`, `low_lint.py`), and Pyright static type checking
- [ ] Modules ending in `_ext` are exempt from interface import checking rules
- [ ] High-side minimality: a non-`_ext` import declared in an interface or implementation `high/<name>.md` that the low stub never imports is reported as a high-level defect ("unnecessary interface import")
- [ ] Low-side completeness: an `_impl.pyi` stub must import every non-`_ext` module declared in the high-level specification's `imports:`
- [ ] Implementation import accountability: every module declared in front-matter `imports:` of `high/<name>_impl.md` must be utilized in AST signatures or cited in at least one `GROUNDING:` section in `low/<name>_impl.pyi`
- [ ] Host file literal grounding: non-`_ext` stubs must not contain hardcoded file names, configuration markers, or persistence files unless grounded via imported `_ext` components
- [ ] Implementation planning deferral coverage: `planning/<name>_impl.md` must repeat each inherited deferred requirement verbatim ("missing inherited deferred requirement")
- [ ] AST parsing confirms that member bodies in `.pyi` files consist strictly of docstrings followed by `...` without executable statements
- [ ] When `check_files` reports syntax errors, Pyright type failures, or linter violations, defect attribution is delivered immediately to the culprit authoring file

## Normative triage decision procedure

- [ ] Defects follow the strict triage chain: (1) if behavior is absent from `high/<name>.md`, scenario over-reaches (never blame planning or low); (2) if present in high but missing in `planning/<name>.md`, blame planning; (3) if present in planning but missing in `low/<name>.pyi`, blame low; (4) if represented across all three planes, no defect exists
- [ ] Core Invariant: A defect is never attributed to a specification plane that already carries the requirement
- [ ] When high, planning, and low are mutually consistent and only the scenario disagrees, submit the unit and record the scenario discrepancy in feedback; never manufacture a spec-plane defect
- [ ] In implementation specifications, when an imported module is absent from the stub AST and omitted from all `GROUNDING:` sections, blame `high/<name>_impl.md` if unneeded, `planning/<name>_impl.md` if needed by deferred requirements but omitted from planning, or `low/<name>_impl.pyi` if grounded in planning but omitted from stub grounding
- [ ] Assembly components (`high/<name>_asm.md`) aggregate constituent implementations directly and bypass planning canvases and scenario evaluation

## High-level specification quality audit

- [ ] Every domain concept is represented by exactly one canonical term, avoiding synonym drift and dual-term divergence
- [ ] Prose avoids pseudo-code jargon: container nouns ("list", "map", "dictionary"), "optional", and artificial parameter flags are absent
- [ ] Requirements state capabilities and invariants declaratively without procedural recipes or start/stop imperatives
- [ ] Properties and dependencies have an explicit derivation path from known inputs, environment, or collaborators in scope
- [ ] The possessive in the High-Level Specification ("a system's X" vs "an agent session's X") defines lifecycle tier membership
- [ ] Collaborator dependencies required to ground capabilities are declared in front-matter `imports:` and referenced only in `**Delegated:**`

## High-to-low direct semantic alignment audit

- [ ] Every domain concept, data record, parameter, and return value specified in `high/<name>.md` is represented in `low/<name>.pyi`
- [ ] Every operational contract, behavioral rule, and invariant described in `high/<name>.md` is represented under `INVARIANTS:`, `PRECONDITIONS:`, or `POSTCONDITIONS:` in `low/<name>.pyi`
- [ ] Postconditions map all behavioral outcomes, state transitions, and return values using normative clauses (`- WHEN <condition>, MUST <outcome>.` or `- MUST <outcome>.`)
- [ ] Every failure mode and contract violation error (`*Error`) specified in `high/<name>.md` is represented under `PRECONDITIONS:` using `- WHEN <condition>, MUST raise <Error>.`; specifying contract violation errors under `POSTCONDITIONS:` is strictly prohibited
- [ ] Operational failures (`*Exception`) and guaranteed outcomes are represented under `POSTCONDITIONS:` using exact quoted error strings or outcome descriptions
- [ ] Member parity: every `@property` and `@operation` declared in an interface stub is implemented with `@override` in the corresponding `_impl.pyi` stub
- [ ] Interface stubs (`low/<name>.pyi`) define abstract protocols without leaking internal backing fields or collaborator class names
- [ ] Implementation stubs (`low/<name>_impl.pyi`) define concrete `GROUNDING:` sections naming valid collaborator classes, methods, and backing fields

## Scenario evaluation and outlier handling

- [ ] The scenario file (`scenarios/<name>.md`) is evaluated alongside the specification planes as a read-only audit artifact
- [ ] Every interface scenario observation is judged against `low/<name>.pyi` as supported, partial, or unstated
- [ ] Every implementation scenario observation is traced to an imported collaborator capability, delegated capability, or private mechanism
- [ ] A realization reading internal state is traced to the operation that writes that state; unstated preconditions in thin specifications are accepted if marked as inferred in `Given:`

## Materiality test and false-positive suppression

- [ ] A defect must be a concrete behavior the specification plane cannot support, not merely terse or condensed wording
- [ ] An enumeration inside a contract that is an instance of a broader invariant the stub already states is not a defect
- [ ] Negative partitions, empty cases, or missing-key cases that high specifications never mention are not defects unless high specifies them
- [ ] An unused low-side import is not a defect if the stub's AST and `GROUNDING:` arguments fully cover all required capabilities
- [ ] Arbiters do not invent stricter syntactic constraints than those enforced by `check_files`

## Defect diagnosis, calibration, and blame feedback

- [ ] Calibration rule: before declaring a novel class of defect, the arbiter compares against a reference unit carrying `SPEC_QA_AUDIT`
- [ ] Single agent blame per round: only one agent (`high`, `planning`, or `low`) is blamed for a unit in a given round

<!-- if experiment:structured_blame -->

- [ ] Structured blame tuple format (mandatory under structured_blame): blame critique MUST use the structured tuple format:
  `bin/blame <culprit_file> "[slug:<spec.slug>] Violation: <noun phrase> Facet: <noun phrase> [Lines: <range>] [Witness: <key_value_pairs>]"`
  or via taxonomy tag format:
  `bin/blame <culprit_file> "[slug:<spec.slug>] [viol:<prefix>.<name>] Facet: <noun phrase> [Lines: <range>] [Witness: <key_value_pairs>]"`
  or via flags: `bin/blame <culprit_file> --slug <slug> --viol <viol> --facet "<noun phrase>" [--lines "<range>"] [--witness "<values>"]`
  - Specification slug: Must match a slug declared in `low/*.pyi`.
  - Violation section: Either a generalized non-prescriptive noun phrase (`Violation: <noun phrase>`, max 8 words, max 120 chars, no action verbs) or a taxonomy tag (`[viol:<prefix>.<name>]`). Canonical violation phrases include `Violation: compound conjunction` and `Violation: uncontracted type`.
  - Facet: Descriptive noun phrase of domain state/entity without verbs or commands (max 8 words, max 120 chars, e.g. `Facet: relational comparator and hyphen parsing conjunction`).
  - Lines (optional): Dedicated single line number or range strictly within the culprit file being blamed (e.g. `Lines: 42` or `Lines: 42-50`). Cannot reference foreign files or paths.
  - Witness: Literal key-value pairs (max 250 chars, e.g. `Witness: clause='POSTCONDITIONS: MUST parse basic comparators...'`). Conversational prose sentences and prescriptive instructions are prohibited. Line numbers belong in `Lines:`, not Witness.

<!-- else -->

- [ ] Blame feedback paragraph format: the explanation is strictly a single paragraph containing no newline characters, formatted as: plane $\\to$ section/member $\\to$ omitted behavior in that plane's vocabulary $\\to$ evidence (quoted clause or verbatim linter diagnostic)

<!-- endif -->

- [ ] Blame feedback length is targeted at approximately 120 words and strictly under 200 words; quoting linter output verbatim as evidence is permitted and encouraged
- [ ] Blame feedback is strictly non-prescriptive: it identifies the gap without dictating replacement prose, slug names, or code snippets
- [ ] Unit atomicity: auditing evaluates the unit as a whole; when all specification, low-level, and scenario audits pass, attributing blame is prohibited, and the unit is certified with `submit(target="<target_file>")`
