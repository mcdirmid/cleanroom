# Requirements specified in tool_provider.pyi

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, Set, Tuple, Type, Union


@dataclass(frozen=True, init=False)
class WireType:
    pass


@dataclass(frozen=True)
class String(WireType):
    pass


@dataclass(frozen=True)
class Integer(WireType):
    pass


@dataclass(frozen=True)
class Boolean(WireType):
    pass


@dataclass(frozen=True)
class Float(WireType):
    pass


@dataclass(frozen=True)
class List(WireType):
    pass


@dataclass(frozen=True)
class Dictionary(WireType):
    pass


class ParameterType[ActualT, WireT](Protocol):
    @property
    def actual_type(self) -> Type[ActualT]: ...

    @property
    def wire_type(self) -> Type[WireT]: ...

    def to_actual(self, value: WireT) -> ActualT: ...

    def to_wire(self, value: ActualT) -> WireT: ...

    def convert(self, wire_value: WireT) -> ActualT: ...


@dataclass(frozen=True)
class IdentityParameterType[T](ParameterType[T, T]):
    target_type: Type[T]

    @property
    def actual_type(self) -> Type[T]:
        return self.target_type

    @property
    def wire_type(self) -> Type[T]:
        return self.target_type

    def to_actual(self, value: T) -> T:
        return value

    def to_wire(self, value: T) -> T:
        return value

    def convert(self, wire_value: T) -> T:
        return wire_value


@dataclass(frozen=True)
class ListParameterType[ItemActualT, ItemWireT](
    ParameterType[Sequence[ItemActualT], Sequence[ItemWireT]]
):
    item_type: ParameterType[ItemActualT, ItemWireT]

    @property
    def actual_type(self) -> Any:
        return list

    @property
    def wire_type(self) -> Any:
        return list

    def to_actual(self, value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        return [self.item_type.to_actual(v) for v in value]

    def to_wire(self, value: Sequence[ItemActualT]) -> Sequence[ItemWireT]:
        return [self.item_type.to_wire(v) for v in value]

    def convert(self, wire_value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        return self.to_actual(wire_value)


STRING_PARAMETER_TYPE: IdentityParameterType[str] = IdentityParameterType(str)
INTEGER_PARAMETER_TYPE: IdentityParameterType[int] = IdentityParameterType(int)
BOOLEAN_PARAMETER_TYPE: IdentityParameterType[bool] = IdentityParameterType(bool)
FLOAT_PARAMETER_TYPE: IdentityParameterType[float] = IdentityParameterType(float)


@dataclass(frozen=True)
class DictionaryParameterType[KeyActualT, KeyWireT, ValActualT, ValWireT](
    ParameterType[Mapping[KeyActualT, ValActualT], Mapping[KeyWireT, ValWireT]]
):
    value_type: ParameterType[ValActualT, ValWireT]
    key_type: Any = STRING_PARAMETER_TYPE

    @property
    def actual_type(self) -> Any:
        return dict

    @property
    def wire_type(self) -> Any:
        return dict

    def to_actual(
        self, value: Mapping[KeyWireT, ValWireT]
    ) -> Mapping[KeyActualT, ValActualT]:
        return {
            self.key_type.to_actual(k): self.value_type.to_actual(v)
            for k, v in value.items()
        }

    def to_wire(
        self, value: Mapping[KeyActualT, ValActualT]
    ) -> Mapping[KeyWireT, ValWireT]:
        return {
            self.key_type.to_wire(k): self.value_type.to_wire(v)
            for k, v in value.items()
        }

    def convert(
        self, wire_value: Mapping[KeyWireT, ValWireT]
    ) -> Mapping[KeyActualT, ValActualT]:
        return self.to_actual(wire_value)


@dataclass(frozen=True)
class Parameter[ActualT, WireT]:
    name: str
    description: str
    parameter_type: ParameterType[ActualT, WireT]
    is_required: bool = True
    default_value: Optional[ActualT] = None
    missing_message: Optional[Callable[[Set[str]], str]] = None

    def __init__(
        self,
        name: str,
        description: str,
        parameter_type: Optional[ParameterType[ActualT, WireT]] = None,
        parameter_converter: Optional[ParameterType[ActualT, WireT]] = None,
        is_required: bool = True,
        default_value: Optional[ActualT] = None,
        missing_message: Optional[Callable[[Set[str]], str]] = None,
    ) -> None:
        pt = parameter_type if parameter_type is not None else parameter_converter
        if pt is None:
            raise ValueError(
                "Either parameter_type or parameter_converter must be provided."
            )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "parameter_type", pt)
        object.__setattr__(self, "is_required", is_required)
        object.__setattr__(self, "default_value", default_value)
        object.__setattr__(self, "missing_message", missing_message)

    @property
    def parameter_converter(self) -> ParameterType[ActualT, WireT]:
        return self.parameter_type


@dataclass(frozen=True)
class ActualParameterBindings:
    bindings: Set[Tuple[Parameter, Any]]

    @property
    def bindings_by_name(self) -> Dict[str, Any]:
        return {p.name: v for p, v in self.bindings}

    def get_value(self, name: str, default: Any = None) -> Any:
        for p, v in self.bindings:
            if p.name == name:
                return v
        return default


@dataclass(frozen=True)
class WireParameterBindings:
    bindings: Set[Tuple[str, Any]]

    @property
    def bindings_by_name(self) -> Dict[str, Any]:
        return dict(self.bindings)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.bindings)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "WireParameterBindings":
        return cls(bindings=set(d.items()))


@dataclass(frozen=True)
class FollowUpToolCall:
    tool_name: str
    wire_parameter_bindings: WireParameterBindings
    reasoning_text: Optional[str] = None


@dataclass(frozen=True)
class Response:
    is_failed: bool
    is_terminated: bool
    content: str
    reminder: Optional[str] = None
    suppression_key: Optional[str] = None
    follow_up_tool_call: Optional[FollowUpToolCall] = None

    @property
    def output_text(self) -> str:
        if self.reminder:
            return f"{self.content}\n\nReminder: {self.reminder}"
        return self.content


ToolCallResult = Response


class Tool(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def parameters(self) -> Set[Parameter]: ...

    def execute_tool(
        self, actual_parameter_bindings: ActualParameterBindings
    ) -> Response: ...


class ToolManager(Protocol):
    @property
    def installed_tools(self) -> Set[Tool]: ...

    def install_tool(self, tool: Tool) -> None: ...

    def execute_tool(
        self, name: str, wire_parameter_bindings: WireParameterBindings
    ) -> Response: ...

    def execute_tool_with_arguments(
        self, name: str, arguments: Mapping[str, Any]
    ) -> Response: ...

    def create_tool_callable(self, name: str) -> Any: ...


ParameterConverter: Type[Any] = ParameterType
IdentityParameterConverter: Type[Any] = IdentityParameterType


class StringParameterConverter(IdentityParameterType[str]):
    def __init__(self) -> None:
        super().__init__(str)


StringParameterType: Type[Any] = StringParameterConverter


class IntegerParameterConverter(IdentityParameterType[int]):
    def __init__(self) -> None:
        super().__init__(int)


IntegerParameterType: Type[Any] = IntegerParameterConverter


class BooleanParameterConverter(IdentityParameterType[bool]):
    def __init__(self) -> None:
        super().__init__(bool)


BooleanParameterType: Type[Any] = BooleanParameterConverter


class FloatParameterConverter(IdentityParameterType[float]):
    def __init__(self) -> None:
        super().__init__(float)


FloatParameterType: Type[Any] = FloatParameterConverter
ListParameterConverter: Type[Any] = ListParameterType
DictionaryParameterConverter: Type[Any] = DictionaryParameterType
