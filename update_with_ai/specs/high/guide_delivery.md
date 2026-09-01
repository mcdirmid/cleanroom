# guide_delivery

imports: tool_provider
types from tool_provider: tool result

## Purpose

Delivers incremental task guidance to keep agents focused on single milestones and prevent rushed execution.

> When step-by-step execution is disabled, the guide is provided as a whole read-only file injected into the session at startup.

Providing entire task guides at once encourages models to attempt all steps simultaneously, skipping intermediate validation. Guide delivery splits guides into sequential step sections, delivering the next milestone only when current progress passes verification.

## Types

- A *guide delivery* is a service that delivers step-by-step instructions from a *guide*
- A *guide delivery factory* is a provider that constructs *guide delivery* services for specific *guides*
- A *guide* is structured instructional text containing a summary and sequential *step sections*
- A *step section* is a discrete milestone section within a *guide*
- A *step delivery* is a *tool result* delivering active guidance to an agent

## Behavior

- Creating a *guide delivery* through a *guide delivery factory* yields a *guide delivery* initialized from a *guide*.
- A *guide delivery* provides initial summary guidance identifying the active *guide* as a *step delivery* at session start.
- A *guide delivery* advances to the next *step section* upon successful verification, producing a *step delivery*.
- A *guide delivery* retains the current *step section* without advancement upon failed verification.
- When progressive guide delivery is configured for a *guide*, the *guide* is delivered exclusively through *step delivery* and excluded from readable session files.
