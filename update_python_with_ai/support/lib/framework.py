"""Cleanroom Specification Framework: Structural markers for pure .pyi groundings."""

from typing import Any, Callable, Literal, TypeVar

T = TypeVar("T")
LifecycleTier = Literal["system", "agent_session"]


def singleton_type(
    lifecycle: LifecycleTier = "agent_session",
) -> Callable[[type[T]], type[T]]:
    """Marks an active service as a singleton within its lifecycle tier ('system' or 'agent_session')."""

    def decorator(cls: type[T]) -> type[T]:
        return cls

    return decorator


def poly_type(cls: type[T]) -> type[T]:
    """Marks an active service as an open polymorphic multiton interface."""
    return cls


def data_type(cls: type[T]) -> type[T]:
    """Marks a passive structural value type with value equality."""
    return cls


def variant(cls: type[T]) -> type[T]:
    """Marks a closed sum-type variant extending a data type or variant."""
    return cls


def operation(func: Callable[..., Any]) -> Callable[..., Any]:
    """Marks a member as an active operation on a service or data type."""
    return func


def override(func: Callable[..., Any]) -> Callable[..., Any]:
    """Marks an operation or property as overriding an inherited contract."""
    return func
