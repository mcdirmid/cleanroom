<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T04:09:45Z
CHANGE: Removed the agent_session import: it was contributed solely by tool_coverage_impl, which is now system-tier, and is no longer imported by any constituent.
CODE_HASH: cd333ec6b850
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# tools_asm assembly component

assembles: tool_coverage_impl
implements: tool_coverage

## Purpose

The tools_asm assembly component aggregates tool and inspection services, including module statement test coverage evaluation, into the unified tools package.

Cleanroom role workspaces and developer CLI commands require standard access to testing, coverage, and analysis tools through configured lifecycle dependencies. The tools_asm assembly component initializes constituent services and registers singleton implementations with the session lifecycle registry.

**Out of scope:** The tools_asm assembly component does not implement individual evaluation logic, execute coverage measurements, or modify source files; these are handled by other components.

## Types and Behavior

The tools_asm assembly component aggregates the implementation of the tool coverage interface, providing a unified assembly for module coverage evaluation and report generation.
