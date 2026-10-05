# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 6febf9196b32
# GROUNDING_QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

"""Loop subsystem assembly grounding specification module."""

from __future__ import annotations

from parts.loop.grounding import loop_cleaner_impl
from parts.loop.grounding import loop_guard_impl
from parts.loop.grounding import loop_node_cleaner_impl
from parts.openai.grounding import openai_conversation_impl
from parts.openai.grounding import openai_driver_impl

CONSTITUENTS = (
    loop_cleaner_impl,
    loop_guard_impl,
    loop_node_cleaner_impl,
    openai_conversation_impl,
    openai_driver_impl,
)


def __initialize__() -> None:
    """Aggregates turn loop execution, prompt conversation history formatting, loop guard repetition tracking, subgraph iteration, and node cleaning orchestration into the loop subsystem assembly.

    CONSTITUENTS:
    - loop_cleaner_impl
    - loop_guard_impl
    - loop_node_cleaner_impl
    - openai_conversation_impl
    - openai_driver_impl
    """
    loop_cleaner_impl.__initialize__()
    loop_guard_impl.__initialize__()
    loop_node_cleaner_impl.__initialize__()
