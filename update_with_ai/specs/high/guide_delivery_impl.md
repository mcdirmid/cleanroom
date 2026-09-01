# guide_delivery_impl

imports: tool_provider, guide_delivery
types from tool_provider: tool result
types from guide_delivery: guide delivery factory, guide delivery, guide, step section, step delivery
implements: guide delivery factory

## Purpose

Implements step delivery by splitting Markdown heading sections, skipping lint check sections to keep the agent focused on code modification steps.

## Behavior

- Creating a *guide delivery* through a *guide delivery factory* yields a *guide delivery* initialized from a *guide*.
- A *guide delivery* splits a *guide* into its summary and *step sections* following standard guide format headings, skipping lint check sections (headed by `## Lint checks`) during step delivery.
- The initial *guide* summary is pre-injected as a *step delivery* before the first agent turn.
- A *guide delivery* advances to the next *step section* upon successful verification and delivers it via *step delivery*.
- A failing verification retains the current *step section* in the *guide delivery* without advancement.
