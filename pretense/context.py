"""Dynamic scope context for Hypothesis draw integration in Pretense."""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Callable, Generator, Optional

# Active draw function provided by Hypothesis DataObject.draw
_CURRENT_DRAW: ContextVar[Optional[Callable[..., Any]]] = ContextVar(
    "_CURRENT_DRAW", default=None
)


def get_current_draw() -> Optional[Callable[..., Any]]:
    """Get the active draw function if running inside a Hypothesis rule."""
    return _CURRENT_DRAW.get()


@contextmanager
def with_draw(draw_fn: Optional[Callable[..., Any]]) -> Generator[None, None, None]:
    """Execute a block within dynamic scope bound to a draw function."""
    token: Token[Optional[Callable[..., Any]]] = _CURRENT_DRAW.set(draw_fn)
    try:
        yield
    finally:
        _CURRENT_DRAW.reset(token)
