# Guide: Writing Guides for LLM Readers

## Summary

A guide defines declarative constraints for an LLM reader producing an artifact, staking requirements without triggering actions. Every guide begins with `# Guide: <title>`, followed by `## Summary` in at most two concise paragraphs, optional non-step sections (`## Verification failure`, `## Lint checks`), and progressive checklist sections (`## <section>`). Environmental communication to the agent is declarative and impersonal without second-person pronouns ("you", "your"); synthetic injected reasoning uses first-person ("I", "let me"). The ambiguous term "turn" is strictly prohibited across all guides, prompts, and specifications; "step" refers exclusively to a single prompt/tool interaction cycle, and "round" refers to a full Cleanroom role dispatch wave.

The Summary establishes core constraints to preserve working artifacts and bootstrap minimal valid revisions, delegating fine-grained checks to checklist sections containing only `- [ ] <item>` lines. Checklist items constrain the post-edit artifact state rather than tool mechanics; process, editing strategy, and write permissions belong in `## Summary`, failure recovery belongs in `## Verification failure`, and deterministic string or applicability checks belong in `## Lint checks`. Information blockades and meta notes are expressed exclusively as single-paragraph blockquotes (`> META: "..."`), filtered out by agent readers. Whole guides must remain under 20,000 bytes.

> META: "Guides are written for LLM readers that take every sentence literally; meta notes provide guidance for human authors, tooling, and information blockades while remaining invisible to the agent during execution. For the Markdown template format used to structure initial templates with HTML comment directives and parameters, see design-docs/template_format.md."

## Guide structure

- [ ] File is `# Guide: <title>` → `## Summary` → optional non-step sections (`## Verification failure`, `## Lint checks`) → `## <section>` headings, in that order
- [ ] The first `##` heading is the Summary
- [ ] An optional section titled `## Verification failure` states instructions or restrictions that apply only when verification fails; it is never delivered as a progression step
- [ ] If the artifact has a linter, a section titled `## Lint checks` describes what the linter checks; it is never delivered as a progression step
- [ ] Meta notes are expressed as single-paragraph blockquotes starting with `> META: "one paragraph of meta note."`
- [ ] Meta notes contain guidance, rationale, or information blockades intended for human authors and meta-tools, never normative requirements or constraints for the agent (since agent readers filter out `> META:` paragraphs)
- [ ] Information blockades restricting access to other files or roles are expressed strictly as meta notes; direct blockade constraints in the guide are prohibited because the completed system enforces them mechanically, and direct statements confuse the agent
- [ ] Checklist sections contain only `- [ ] <item>` lines — no prose, no nested headings
- [ ] The guide reads coherently whole and sectioned

## Summary

- [ ] The Summary states the guide's subject declaratively: an alignment guide names the artifact and its source ("The module implements `low/<name>.md`"); a conformance guide names the artifact ("The artifact conforms to this guide")
- [ ] The Summary is concise (one or at most two paragraphs), stating complete high-level requirements so the initial write or edit is accurate in substance, while leaving fine-grained rules to checklist sections
- [ ] The Summary serves two purposes: (a) preserving an already working artifact without edits when contracts and verification pass, and (b) establishing a minimal valid artifact that passes initial verification when starting from scratch or a template, delegating expanded coverage to checklist steps
- [ ] File references and multi-node session targets use package-relative file alias relative paths (e.g. `high/<name>.md`, `grounding/<name>.pyi`, `lib/<name>.py`, `tests/<name>_test.py`) and never expose host repository filesystem paths
- [ ] Rules governing the editing process, tool usage, incremental editing strategy, or write permissions belong in the `## Summary` (which is visible before editing begins and throughout all steps in step mode); checklist items verify the artifact after changes are made and show up too late to control how editing is done; rules that apply specifically and exclusively to recovering from verification failure belong in `## Verification failure`
- [ ] Applicability restrictions and not-applicable conditions (e.g. only applying to implementation specs whose name ends in `_impl.md`) are never in the Summary; they belong in `## Lint checks`
- [ ] No directive framing — never "ensure", "produce", "transform" (the file pre-exists; the prompt triggers, the guide constrains)
- [ ] Environmental communication to the agent (guides, prompts, tool outputs, reminders) is declarative and impersonal, stating environmental facts and constraints without second-person pronouns ("you", "your")
- [ ] Injected reasoning text representing agent cognition uses the first-person perspective ("I", "let me") to match the assistant monologue and drive action continuation
- [ ] Build-critical requirements come first (BUILD entries, required structure) — nothing builds without them
- [ ] The guide's requirements are satisfiable from the guide alone: no reliance on the artifact's starting state — the file's existing content (a template, a prior version) is at most an efficiency boost, never the source of required structure
- [ ] No instruction to run or interpret verification; verification is transparent and the reader's only verification action is calling `advance`; guides and prompts never advise about tool arguments: they can refer to advance, but they cannot refer to tool arguments or the content of advance
- [ ] Prompts state what the artifact is, never what it is not: no negative instructions, no speculation about other modules, and no editing or tool advice
- [ ] No instruction to do what the reader cannot do — the reader's capabilities are fixed (file reads, edits, and advance; the search tool is never installed; no execution, no shell, no test runs); a capability the reader lacks is never stated as a requirement and never as a prohibition — the reader already knows it lacks it
- [ ] No reference to files the reader cannot read (other guides, HLS files, implementations); a label in the source material that names an unreadable file gets one sentence saying it carries no requirements; information blockades are expressed exclusively as meta notes rather than direct reader prohibitions that confuse the agent
- [ ] External domain knowledge and foreign formats (third-party APIs, foreign serialization formats, runtime identifiers) are excluded from guides; external boundaries are specified in dedicated external boundary specifications (`low/<name>_ext.md`)
- [ ] Templates provide initial creation and bootstrapping guidance through inline instruction comments; checklist sections verify that template instruction comments are deleted before final artifact completion
- [ ] Templates follow the Markdown template format in design-docs/template_format.md, using HTML comment directives and placeholder parameters that remain readable without bindings
- [ ] The Summary mentions templates at most once to describe initial bootstrapping ("When starting from a template, the template's inline instructions guide creating a minimal artifact...")
- [ ] No meta-commentary, no rationale, no examples — state the constraint

## Checklist sections

- [ ] Each item is one independently verifiable constraint on the artifact; no cross-item reasoning ("see above")
- [ ] Checklist items constrain the post-edit artifact state (what the artifact contains), never the editing process or tool mechanics (how editing is performed) — process, tool, and editing constraints belong in `## Summary`
- [ ] Items carry the precision: exact spellings, required forms, conformance checks — never style preferences the source already dictates
- [ ] Each item is checkable given the Summary, the section, and the artifact
- [ ] Sections are ordered fine-grain-first (layout, imports, types, contracts, pitfalls)
- [ ] File references in all sections use package-relative file alias relative paths and never expose host repository filesystem paths
- [ ] If the artifact has a linter, a `## Lint checks` section (with the exact title "Lint checks") describes what is checked
- [ ] All checklist items that can be deterministically verified by verifying the presence or absence of a specific string, marker, or token belong in `## Lint checks` (and are implemented by the artifact's linter), never in judgment-based content sections
- [ ] The `## Lint checks` section contains only linter-verified checks and applicability constraints (e.g., target spec must end in `_impl.md`) — no human judgment points
- [ ] A point only partly linter-verified is split: the linter-verified part goes in `## Lint checks`, the judgment part stays in its content section

## Step mode

- [ ] In step mode the reader sees the Summary and one section at a time; earlier sections are stubbed — each section is self-sufficient: a rule the section depends on appears in that section or in the Summary
- [ ] Checklist sections are delivered after edits are made and an advance is called: they cannot control how editing is done because they show up too late; all editing workflow and tool rules live in `## Summary`
- [ ] Since guide delivery does not advance to subsequent sections until verification passes, checklist items cannot help the reader resolve verification errors; rules that govern resolving verification failures belong in `## Verification failure`
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
- [ ] Second-person pronouns ("you", "your") are prohibited in all agent-facing environmental messages (guides, prompts, tool outputs, reminders, errors); constraints and states are stated impersonally and declaratively
- [ ] First-person perspective ("I", "let me") is used when injecting synthetic assistant reasoning to simulate internal agent cognition and prime tool execution
- [ ] Standard terminology: the ambiguous term "turn" is strictly prohibited; "step" is used exclusively for single prompt/tool interaction cycles, and "round" is used exclusively for full Cleanroom role dispatch waves
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
- [ ] Perspective test: all environmental communications to the agent are declarative and impersonal without second-person pronouns ("you", "your"); injected assistant reasoning uses the first-person perspective ("I", "let me")
- [ ] Path test: no host filesystem paths appear anywhere in the guide; only package-relative file alias relative paths appear (such as `high/<name>.md`, `grounding/<name>.pyi`, `lib/<name>.py`, `tests/<name>_test.py`)
- [ ] Linter test: if a linter exists for the artifact, a section titled `## Lint checks` lists all automated and applicability checks, and no applicability rules appear in the Summary
- [ ] Deterministic test: every check verifiable by verifying presence or absence of a specific string or token is listed in `## Lint checks`

## Common pitfalls

- [ ] Bloat — restated rules, meta-commentary, duplicate examples — cut each fact once
- [ ] Chunk-fragile structure — tables, header-dependent lines, "as above" — one fact per line; lists over tables
- [ ] Second-person environmental address — using "you" or "your" in guides, prompts, tool responses, or reminders instead of declarative, impersonal constraints; or failing to use first-person perspective when injecting assistant reasoning
- [ ] Ambiguity — "should", "can optionally" — "must", "never", "only"
- [ ] Buried rules — the load-bearing constraint after examples — front-load; examples after rules
- [ ] Exposing file paths — using host or repository filesystem paths (e.g. `specs/low/<name>.md` or `testing/parts/...`) instead of package-relative file alias relative paths (e.g. `high/<name>.md`, `grounding/<name>.pyi`)
- [ ] Applicability in Summary — stating not-applicable conditions or spec filters in the Summary instead of `## Lint checks`
- [ ] Mixed lint/judgment points — a point the linter half-checks left whole — split: the linter part in `## Lint checks`, the judgment part in its content section
- [ ] Deterministic checks outside Lint checks — placing string-presence or string-absence checks in content sections instead of `## Lint checks`
- [ ] Process rules in checklist — placing editing strategy, tool usage, or step-by-step modification rules in checklist sections instead of `## Summary` where they are visible before editing
- [ ] Failure recovery in Summary or checklist — placing verification-failure recovery rules (such as fail-tool escalation or diagnostic triage) in `## Summary` or checklist sections instead of `## Verification failure`
- [ ] Missing Lint checks section — omitting `## Lint checks` when a linter is present
- [ ] Implicit requirements — required structure shown only by example — say "must contain"; list the structure
- [ ] Over-general rules — a prohibition without its exception — state the exception beside the rule
- [ ] Rule-breaking examples — a snippet that violates the guide — every example must conform
- [ ] Context examples — a snippet lifted from surrounding code or specs — use synthetic examples that obey the guide's rules
- [ ] Triggering — a sentence that instructs the reader ("ensure the module...") — the guide constrains; the prompt triggers
- [ ] Checklist items helping with verification — attempting to use checklist sections to guide the reader through resolving verification errors; because guides do not advance until verification passes, checklist items cannot help the reader fix verification failures
- [ ] Capability noise — telling the reader to run or interpret checks it has no tool for, or stating what it cannot do — the reader's capabilities are fixed; mention only actions the reader can take
- [ ] Direct information blockades — stating information blockades or unreadable file prohibitions directly in guide text or checklist items instead of expressing them exclusively as meta notes (`> META: "..."`); the completed system enforces file isolation mechanically, and direct blockade statements confuse the agent
