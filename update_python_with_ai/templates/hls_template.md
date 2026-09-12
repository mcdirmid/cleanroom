# <name> <component_type> component

<!-- if: is_asm -->
assembles: <constituent_modules>
<!-- endif -->
imports: <imported_modules>
<!-- if: needs_implements -->
implements: <implemented_interfaces>
<!-- endif -->

## Purpose

The <name> <component_type> component <TODO: provides ...>.

<TODO: one or two paragraphs of architectural rationale motivating the component from a system perspective.>

**Out of scope:** <TODO: client workflow purpose, background intent, or caller motivations>; these are handled by other components.

<!-- if: is_ext -->
## Grounding Gaps Covered

<TODO: describe external domain knowledge, mechanics, foreign serialization formats, or third-party SDK concepts.>
<!-- endif -->
<!-- if: is_not_ext -->
## Types and Behavior

<TODO: literate prose describing types and behavior with semantic italics on concept introductions.>
<!-- endif -->

<!--
TODO: work through this template section by section:
  - replace every TODO marker with content derived from the source materials
  - the section inventory is closed strictly to ## Purpose and ## Types and Behavior (or ## Grounding Gaps Covered for external components)
  - the HLS is declarative: no mechanism, no pseudo-code, no bolding, no nested bullets
  - delete this comment block when the document is complete
-->

