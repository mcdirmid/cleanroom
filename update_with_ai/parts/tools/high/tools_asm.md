<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: a047b7441f03
-->

# tools_asm assembly component

assembles: tool_coverage_impl
imports: agent_session
implements: tool_coverage

## Purpose

The tools_asm assembly component aggregates tool and inspection services, including module statement test coverage evaluation, into the unified tools package.

Cleanroom role workspaces and developer CLI commands require standard access to testing, coverage, and analysis tools through configured lifecycle dependencies. The tools_asm assembly component initializes constituent services and registers singleton implementations with the session lifecycle registry.

**Out of scope:** The tools_asm assembly component does not implement individual evaluation logic; it delegates to constituent tool implementations.

## Types and Behavior

The tools assembly component provides initialization routines that register constituent tool service singletons into the session tier.
