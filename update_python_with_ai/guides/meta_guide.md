# Guide: Writing Guides for LLM Readers

## Summary

A guide is read by an LLM that produces an artifact satisfying the guide's constraints. This guide states how to write a guide an LLM can follow, and applies its own rules to itself. Every guide has two parts: a Summary that states the initial requirements, and checklist sections that state the fine-grained requirements.

The reader is an LLM consuming the guide through tool reads; it has only the current message and the artifact, and it takes every sentence literally. Every line must be actionable.

The Summary drives the initial write or edit in one or at most two concise paragraphs: it states the high-level subject and core constraints completely so the initial revision is accurate in substance, without detailing fine-grained checks that checklist sections verify. Because linters run immediately upon advancing, structural problems are exposed early, keeping the Summary light and focused on core constraints rather than deep rule duplication.

A guide never triggers. The prompt asks for alignment or conformance with the guide and the other input files, and it drives the loop; the guide stakes constraints and requirements only. Directive verbs aimed at the reader ("ensure", "produce", "apply", "verify the checklist", "call advance") are prohibited; declarative constraints ("the module must", "X matches Y") are the rule.

Every guide follows this structure:

- `# Guide: <title>`, then `## Summary`, then `## <checklist sections>`.
- The first `##` heading is the Summary; every `##` after it is a checklist point; no other `##` headings exist.
- The boundary is positional: the Summary runs to the second `##` heading; each checklist section runs to the next `##` heading or end of file.
- Checklist sections contain only `- [ ] <item>` lines.
- If the artifact has a linter, a `## Lint checks` section describes what is checked.
- The guide reads coherently whole (Summary then sections in order) and sectioned (Summary first, then one section at a time).

## Guide structure

- [ ] File is `# Guide: <title>` → `## Summary` → `## <section>` headings, in that order
- [ ] The first `##` heading is the Summary; every subsequent `##` heading is a checklist point; no other `##` headings
- [ ] If the artifact has a linter, a section titled `## Lint checks` describes what the linter checks
- [ ] Checklist sections contain only `- [ ] <item>` lines — no prose, no nested headings
- [ ] The guide reads coherently whole and sectioned

## Summary

- [ ] The Summary states the guide's subject declaratively: an alignment guide names the artifact and its source ("The module implements `low/<name>.md`"); a conformance guide names the artifact ("The artifact conforms to this guide")
- [ ] The Summary is concise (one or at most two paragraphs), stating complete high-level requirements so the initial write or edit is accurate in substance, while leaving fine-grained rules to checklist sections
- [ ] File references never use file paths; only virtual file names are used (except when files share names, where the directory prefix is appended, mainly `low/<name>.md` and `high/<name>.md`)
- [ ] Rules governing the editing process, tool usage, incremental editing strategy, or write permissions belong in the `## Summary` (which is visible before editing begins and throughout all steps in step mode); checklist items verify the artifact after changes are made and show up too late to control how editing is done
- [ ] Applicability restrictions and not-applicable conditions (e.g. only applying to implementation specs whose name ends in `_impl.md`) are never in the Summary; they belong in `## Lint checks`
- [ ] No directive framing — never "ensure", "produce", "transform" (the file pre-exists; the prompt triggers, the guide constrains)
- [ ] Build-critical requirements come first (BUILD entries, required structure) — nothing builds without them
- [ ] The guide's requirements are satisfiable from the guide alone: no reliance on the artifact's starting state — the file's existing content (a template, a prior version) is at most an efficiency boost, never the source of required structure
- [ ] No instruction to run or interpret verification; verification is transparent and the reader's only verification action is calling `advance`
- [ ] No instruction to do what the reader cannot do — the reader's capabilities are fixed (file reads, edits, and advance; no execution, no shell, no test runs); a capability the reader lacks is never stated as a requirement and never as a prohibition — the reader already knows it lacks it
- [ ] No reference to files the reader cannot read (other guides, HLS files, implementations); a label in the source material that names an unreadable file gets one sentence saying it carries no requirements
- [ ] External domain knowledge and foreign formats (third-party APIs, foreign serialization formats, runtime identifiers) are excluded from guides; external boundaries are specified in dedicated external boundary specifications (`low/<name>_ext.md`)
- [ ] Templates mentioned at most once ("a file that is a template is filled in")
- [ ] No meta-commentary, no rationale, no examples — state the constraint

## Checklist sections

- [ ] Each item is one independently verifiable constraint on the artifact; no cross-item reasoning ("see above")
- [ ] Checklist items constrain the post-edit artifact state (what the artifact contains), never the editing process or tool mechanics (how editing is performed) — process, tool, and editing constraints belong in `## Summary`
- [ ] Items carry the precision: exact spellings, required forms, conformance checks — never style preferences the source already dictates
- [ ] Each item is checkable given the Summary, the section, and the artifact
- [ ] Sections are ordered fine-grain-first (layout, imports, types, contracts, pitfalls)
- [ ] File references in all sections use virtual file names and never expose file paths (unless disambiguation is required for same-named files, using `low/<name>.md` and `high/<name>.md`)
- [ ] If the artifact has a linter, a `## Lint checks` section (with the exact title "Lint checks") describes what is checked
- [ ] All checklist items that can be deterministically verified by verifying the presence or absence of a specific string, marker, or token belong in `## Lint checks` (and are implemented by the artifact's linter), never in judgment-based content sections
- [ ] The `## Lint checks` section contains only linter-verified checks and applicability constraints (e.g., target spec must end in `_impl.md`) — no human judgment points
- [ ] A point only partly linter-verified is split: the linter-verified part goes in `## Lint checks`, the judgment part stays in its content section

## Step mode

- [ ] In step mode the reader sees the Summary and one section at a time; earlier sections are stubbed — each section is self-sufficient: a rule the section depends on appears in that section or in the Summary
- [ ] Checklist sections are delivered after edits are made and an advance is called: they cannot control how editing is done because they show up too late; all editing workflow and tool rules live in `## Summary`
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
- [ ] Path test: no file paths appear anywhere in the guide; only virtual file names appear (with directory prefixes only for disambiguation such as `low/<name>.md` and `high/<name>.md`)
- [ ] Linter test: if a linter exists for the artifact, a section titled `## Lint checks` lists all automated and applicability checks, and no applicability rules appear in the Summary
- [ ] Deterministic test: every check verifiable by verifying presence or absence of a specific string or token is listed in `## Lint checks`

## Common pitfalls

- [ ] Bloat — restated rules, meta-commentary, duplicate examples — cut each fact once
- [ ] Chunk-fragile structure — tables, header-dependent lines, "as above" — one fact per line; lists over tables
- [ ] Ambiguity — "should", "can optionally" — "must", "never", "only"
- [ ] Buried rules — the load-bearing constraint after examples — front-load; examples after rules
- [ ] Exposing file paths — using filesystem paths (e.g. `specs/low/<name>.md`) instead of virtual file names (`low/<name>.md`)
- [ ] Applicability in Summary — stating not-applicable conditions or spec filters in the Summary instead of `## Lint checks`
- [ ] Mixed lint/judgment points — a point the linter half-checks left whole — split: the linter part in `## Lint checks`, the judgment part in its content section
- [ ] Deterministic checks outside Lint checks — placing string-presence or string-absence checks in content sections instead of `## Lint checks`
- [ ] Process rules in checklist — placing editing strategy, tool usage, or step-by-step modification rules in checklist sections instead of `## Summary` where they are visible before editing
- [ ] Missing Lint checks section — omitting `## Lint checks` when a linter is present
- [ ] Implicit requirements — required structure shown only by example — say "must contain"; list the structure
- [ ] Over-general rules — a prohibition without its exception — state the exception beside the rule
- [ ] Rule-breaking examples — a snippet that violates the guide — every example must conform
- [ ] Context examples — a snippet lifted from surrounding code or specs — use synthetic examples that obey the guide's rules
- [ ] Triggering — a sentence that instructs the reader ("ensure the module...") — the guide constrains; the prompt triggers
- [ ] Capability noise — telling the reader to run or interpret checks it has no tool for, or stating what it cannot do — the reader's capabilities are fixed; mention only actions the reader can take
