# <name>

imports: <dep> (what it provides)              # optional
terms (from <dep>): ...                        # optional
terms (owned): ...                             # optional

## Purpose

<TODO: what the component provides; may name its operation families>

## Terms                    # present iff terms (owned)

- <term>: <use-level definition>
<TODO: define each owned term; delete this section when no terms are owned>

## Contract

**Inputs**                  # optional; "configured:" vs "per call:"
- <client-supplied values>
<TODO: fill in, distinguishing configured from per-call inputs>

**Operations**
- <what the client may do>
<TODO: fill in>

**Guarantees**
- <one fact per line; factor shared state effects>
<TODO: fill in>

**Assumptions**
- <one per line>
<TODO: fill in or delete the block>

**<Named block>**           # optional; any single concern (Logging, Events, Stubbing, ...)
- <one per line>
<TODO: fill in or delete the block>

## Non-concerns

- <one per line>
<TODO: fill in or delete the section>

<!--
TODO: work through this template section by section per guides/high_level_spec.md:
  - replace every TODO marker with content derived from the source materials
  - the section inventory is closed (interfaces: Purpose/Terms/Contract/Non-concerns)
  - the HLS is declarative: no mechanism, no "returns", one fact per line
  - every term used is owned or listed in `terms (from ...)`
  - remove this comment block when the document is complete
-->
