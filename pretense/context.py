"""Dynamic scope context for Hypothesis draw integration in Pretense."""

from update_python_with_ai.parts.pretense.lib.pretense import (
    DrawContext,
    get_current_draw,
    with_draw,
)

__all__ = ["DrawContext", "get_current_draw", "with_draw"]
