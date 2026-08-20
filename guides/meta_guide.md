# Guide: Writing Guides for LLM Readers

## Purpose

A guide is read by an LLM (an agent) that must produce an artifact conforming to the guide's rules. The guide's size, structure, and wording determine whether the reader conforms. This guide states how to write a guide an LLM can follow — and applies its own rules to itself.

## The Reader

- The reader is an LLM consuming the guide through tool reads bounded by a read-size limit.
- The reader has no memory of prior reads; with a chunked guide, later sections may never reach it.
- Every sentence must be actionable: the reader can derive a rule, a constraint, or a decision from it.

## Size

- Measure in bytes (`wc -c`); keep the guide under the sandbox read-size limit (20,000 bytes in this repo) so it arrives in one read.
- Reads are plain by default; line numbers are opt-in, so byte size equals the returned read size.
- Cut anything that does not change what the reader must produce: restated rules, meta-commentary, duplicate examples.
- Smaller is not automatically better: cutting an exception the reader needs is worse than a few extra lines.

## State Each Rule Once

- If the same fact appears in two sections, delete one; duplication makes the reader guess which statement is authoritative.
- Cut meta-commentary ("note that", "it's worth mentioning", "as we discussed"); state the rule, not how to feel about it.
- Cross-references are not duplication: point to the checklist or pitfalls list instead of repeating it.

## Structure for the Reader

- Headers and lists over tables; a list line is a complete fact, a table row without its header is a fragment, and truncation cuts from the end.
- One fact per line; each line complete on its own.
- Front-load: purpose and the most load-bearing rules first; attention fades over the file.
- End with a complete, compact Validation Checklist the reader can verify against.

## Rules vs Requirements — Be Explicit

- Distinguish REQUIRED structure (must be present) from CONTENT rules (how to write it). Say "must contain", not "typically contains".
- An LLM will delete "redundant-looking" required structure unless told it is required. Observed: a model read a spec whose Contract guarantees overlapped its Observable dataflow facts, judged the required `**The component guarantees:**` sub-section redundant — an over-generalization of the "no restating" rule — and deleted it.
- State exceptions beside their rules; LLMs over-generalize prohibitions.
- Use "must", "never", "only"; avoid "should consider", "ideally", "best to".
- Say what is an error and what is merely discouraged; the reader treats both as prohibitions unless told otherwise.

## Examples

- One strong example per rule beats three similar ones; keep a single pitfalls list and point to it.
- Every example must obey the guide's own rules; a violating example licenses the violation.
- Pair each anti-example with its fix; an anti-example alone teaches the wrong pattern.
- Never use an example from the surrounding context (code, specs, conversation) as a guide example. Context examples were not written to illustrate the guide's rules: they may violate them, carry implementation detail, or bind the guide to the source artifact — and the reader treats examples as normative. Write clean synthetic examples that obey the rules.

## Terminology

- Define terms once, use them consistently, and never introduce synonyms for one concept.
- The reader is literal: an undefined term is interpreted loosely; two names for one concept become two concepts.

## Self-Check

- **Truncation test:** cut at any line; every line before the cut remains a complete fact.
- **Action test:** can an LLM derive an actionable rule from each sentence? If not, cut or rewrite.
- **Checklist test:** the Validation Checklist covers every body rule; every checklist item traces to a body rule.
- **One-read test:** given the guide alone in a single read, would a model reproduce the required structure and apply the rules?

## Common Pitfalls

Pitfall — Example — Fix.

- Bloat — restated rules, meta-commentary, duplicate examples — Cut each fact once.
- Chunk-fragile structure — tables, header-dependent lines, "as above" — One fact per line; lists over tables.
- Ambiguity — "should", "can optionally" — "must", "never", "only".
- Buried rules — the load-bearing constraint after examples — Front-load; examples after rules.
- Implicit requirements — required structure shown only by example — Say "must contain"; list the structure.
- Over-general rules — a prohibition without its exception — State the exception beside the rule.
- Rule-breaking examples — a snippet that violates the guide — Every example must conform.
- Context examples — a snippet lifted from surrounding code or specs — Use synthetic examples that obey the guide's rules.
