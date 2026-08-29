# guide_delivery

imports: tool_provider (presented tool result)
terms (from tool_provider): presented tool result, tool result
terms (owned): guide, guide summary, step section, step mode

## Purpose

Provides the guide's delivery to the agent: when step mode is enabled, the guide's content reaches the agent only through the advance operation — the guide summary at run start, then one step section after each advance that passed verification; when step mode is disabled, the guide is provided whole at run start.

## Terms

- Guide: the declared guide input — a readable file the node declares separately from its dependencies, at most one per run, in the guide format: its first line is `# Guide: <title>` and its first `##` heading is `## Summary`.
- Guide summary: the guide's first part — the content from the guide's first line through the end of its `## Summary` section.
- Step section: a checklist section of the guide — a part of the guide after the guide summary, delimited by `## <name>` headings (excluding the `## Lint checks` section, which is skipped in step mode), delivered after an advance that passed verification.
- Step mode: a configuration in which the guide is not readable and its content reaches the agent only through the advance operation: the guide summary at run start, then the step sections one at a time after successful advances.

## Contract

**Inputs**

- Configured: the guide (at most one, may be absent); whether step mode is enabled.
- Per call: whether the advance passed verification.

**Operations**

- Provide the guide's presentation at run start.
- Provide the advance's step-mode output (a presented tool result).
- Query whether step sections remain.

**Guarantees**

- When step mode is disabled, the guide is provided whole at run start and is re-readable like other readable files.
- When step mode is enabled, the guide is not readable: its content reaches the agent only through the advance operation's outputs.
- In step mode, the guide is not presented among the readable files: file lists shown to the agent do not name the guide.
- In step mode, the guide is revealed incrementally: advance delivers one section at a time.
- In step mode, the `## Lint checks` section is skipped and never delivered as a step section.
- A failing verification prevents progressing to the next section, requiring correction before continuing.
- A readable file that is not the guide is unaffected by step mode.
- Termination cannot occur until all guide sections are delivered and verification passes.

**Assumptions**

- At most one guide is declared per run.
- The guide, when declared, is in the guide format.

## Non-concerns

- Step section size: step sections are parts of the guide file, which is assumed reasonably sized; no separate size bound is introduced for step sections.
- Guide parsing: the exact rules for splitting the guide into its guide summary and step sections follow the guide format; section content is delivered in order without interpretation.
- Step presentation: the exact wording of the ensure instruction and the formatting of the summary and step sections within an advance output are unspecified; the intent is conveyed by the Step mode guarantees.
