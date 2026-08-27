# Guide: Writing Guides for LLM Readers

## Summary

A guide is read by an LLM that produces an artifact satisfying the guide's constraints. This guide states how to write a guide an LLM can follow, and applies its own rules to itself. Every guide has two parts: a Summary that states the initial requirements, and checklist sections that state the fine-grained requirements.

The reader is an LLM consuming the guide through tool reads; it has only the current message and the artifact, and it takes every sentence literally. Every line must be actionable.

A guide never triggers. The prompt asks for alignment or conformance with the guide and the other input files, and it drives the loop; the guide stakes constraints and requirements only. Directive verbs aimed at the reader ("ensure", "produce", "apply", "verify the checklist", "call advance") are prohibited; declarative constraints ("the module must", "X matches Y") are the rule.

Every guide follows this structure:

- `# Guide: <title>`, then `## Summary`, then `## <checklist sections>`.
- The first `##` heading is the Summary; every `##` after it is a checklist point; no other `##` headings exist.
- The boundary is positional: the Summary runs to the second `##` heading; each checklist section runs to the next `##` heading or end of file.
- Checklist sections contain only `- [ ] <item>` lines.
- The guide reads coherently whole (Summary then sections in order) and sectioned (Summary first, then one section at a time).

## Guide structure

- [ ] File is `# Guide: <title>` → `## Summary` → `## <section>` headings, in that order
- [ ] The first `##` heading is the Summary; every subsequent `##` heading is a checklist point; no other `##` headings
- [ ] Checklist sections contain only `- [ ] <item>` lines — no prose, no nested headings
- [ ] The guide reads coherently whole and sectioned

## Summary

- [ ] The Summary states the guide's subject declaratively: an alignment guide names the artifact and its source ("The module implements `specs/low/<name>.md`"); a conformance guide names the artifact ("The artifact conforms to this guide")
- [ ] No directive framing — never "ensure", "produce", "transform" (the file pre-exists; the prompt triggers, the guide constrains)
- [ ] Build-critical requirements come first (BUILD entries, required structure) — nothing builds without them
- [ ] The guide's requirements are satisfiable from the guide alone: no reliance on the artifact's starting state — the file's existing content (a template, a prior version) is at most an efficiency boost, never the source of required structure
- [ ] No instruction to run or interpret verification; verification is transparent and the reader's only verification action is calling `advance`
- [ ] No instruction to do what the reader cannot do — the reader's capabilities are fixed (file reads, edits, and advance; no execution, no shell, no test runs); a capability the reader lacks is never stated as a requirement and never as a prohibition — the reader already knows it lacks it
- [ ] No reference to files the reader cannot read (other guides, HLS files, implementations); a label in the source material that names an unreadable file gets one sentence saying it carries no requirements
- [ ] Templates mentioned at most once ("a file that is a template is filled in")
- [ ] No meta-commentary, no rationale, no examples — state the constraint

## Checklist sections

- [ ] Each item is one independently verifiable constraint on the artifact; no cross-item reasoning ("see above")
- [ ] Items carry the precision: exact spellings, required forms, conformance checks — never style preferences the source already dictates
- [ ] Each item is checkable given the Summary, the section, and the artifact
- [ ] Sections are ordered fine-grain-first (layout, imports, types, contracts, pitfalls)
- [ ] Linter-verified points live in their own `## Lint checks` section, which contains only points the linter verifies — no judgment points
- [ ] A point only partly linter-verified is split: the linter-verified part goes in `## Lint checks`, the judgment part stays in its content section

## Step mode

- [ ] In step mode the reader sees the Summary and one section at a time; earlier sections are stubbed — each section is self-sufficient: a rule the section depends on appears in that section or in the Summary
- [ ] A rule with no document region (it constrains the whole artifact) lives in the Summary, never in a section
- [ ] All items in a section concern one step of producing the artifact; if the items split into two concerns, split the section
- [ ] If one item can undo another, they are one item stating both constraints, or two items in the same section with the clobbered rule first
- [ ] Sections are named after the document regions they govern, in document order
- [ ] A rule that applies to every instance in a region is stated once, generically ("every operation", "every alias")

## Size

- [ ] Whole guide under the read-size limit (20,000 bytes in this repo) so whole-guide mode reads it in one read
- [ ] Cut anything that does not change what the reader produces: restated rules, meta-commentary, duplicate examples
- [ ] Smaller is not automatically better; cutting an exception the reader needs is worse than a few extra lines

## Wording

- [ ] Headers and lists over tables; one fact per line; each line complete on its own
- [ ] "must", "never", "only" — never "should consider", "ideally"
- [ ] Never state a rule as "X or Y" when the reader must choose; state the condition of the choice
- [ ] Say what is an error and what is merely discouraged; the reader treats both as prohibitions unless told otherwise
- [ ] State exceptions beside their rules; the reader over-generalizes prohibitions
- [ ] Distinguish REQUIRED structure ("must contain") from CONTENT rules; the reader deletes redundant-looking required structure unless told it is required
- [ ] Define terms once; never introduce synonyms for one concept
- [ ] State each rule once within a section; a section never relies on a rule stated only in an earlier section (step mode stubs it) — repeat the rule or state it in the Summary

## Examples

- [ ] One strong example per rule beats three similar ones
- [ ] Every example obeys the guide's own rules
- [ ] Anti-examples paired with their fixes
- [ ] Examples never come from the current problem under work: no type names, components, or phrases from the specs, code, or conversation being guided; every example is a clean synthetic one invented for the guide

## Self-check

- [ ] Truncation test: cut at any line; every line before the cut remains a complete fact
- [ ] Action test: an LLM can derive a constraint from each sentence
- [ ] Section test: given the Summary, one section, and the artifact, the reader can check that section's items
- [ ] One-read test: given the whole guide in one read, the reader produces the required structure and applies the rules
- [ ] No-trigger test: no sentence directs the reader to do something the prompt already drives ("ensure", "produce", "call advance")
- [ ] Capability test: every action the guide names is one the reader can perform with its tools — no test runs, no shell, no unreadable files

## Common pitfalls

- [ ] Bloat — restated rules, meta-commentary, duplicate examples — cut each fact once
- [ ] Chunk-fragile structure — tables, header-dependent lines, "as above" — one fact per line; lists over tables
- [ ] Ambiguity — "should", "can optionally" — "must", "never", "only"
- [ ] Buried rules — the load-bearing constraint after examples — front-load; examples after rules
- [ ] Mixed lint/judgment points — a point the linter half-checks left whole — split: the linter part in `## Lint checks`, the judgment part in its content section
- [ ] Implicit requirements — required structure shown only by example — say "must contain"; list the structure
- [ ] Over-general rules — a prohibition without its exception — state the exception beside the rule
- [ ] Rule-breaking examples — a snippet that violates the guide — every example must conform
- [ ] Context examples — a snippet lifted from surrounding code or specs — use synthetic examples that obey the guide's rules
- [ ] Triggering — a sentence that instructs the reader ("ensure the module...") — the guide constrains; the prompt triggers
- [ ] Capability noise — telling the reader to run or interpret checks it has no tool for, or stating what it cannot do — the reader's capabilities are fixed; mention only actions the reader can take
