# Requirements specified in tool_provider.pyi

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, Set, Tuple, Type, Union


@dataclass(frozen=True, init=False)
class WireType:
    pass


@dataclass(frozen=True, init=False)
class WireString(str, WireType):
    def __new__(cls, value: str = "") -> "WireString":
        return super().__new__(cls, value)

    def __init__(self, value: str = "") -> None:
        pass


@dataclass(frozen=True)
class WireInteger(WireType):
    pass


@dataclass(frozen=True)
class WireBoolean(WireType):
    pass


@dataclass(frozen=True)
class WireFloat(WireType):
    pass


@dataclass(frozen=True)
class WireList(WireType):
    pass


@dataclass(frozen=True)
class WireDictionary(WireType):
    pass



class ParameterType[ActualT, WireT](Protocol):
    @property
    def actual_type(self) -> Type[ActualT]: ...

    @property
    def wire_type(self) -> Type[WireT]: ...

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

    def convert(self, wire_value: T) -> T:
        return wire_value


@dataclass(frozen=True)
class ListParameterType[ItemActualT, ItemWireT](
    ParameterType[Sequence[ItemActualT], Sequence[ItemWireT]]
):
    item_type: ParameterType[ItemActualT, ItemWireT]

    @property
    def actual_type(self) -> Type[Sequence[ItemActualT]]:
        return list

    @property
    def wire_type(self) -> Type[Sequence[ItemWireT]]:
        return list

    def convert(self, wire_value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        return [self.item_type.convert(v) for v in wire_value]


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
    def actual_type(self) -> Type[Mapping[KeyActualT, ValActualT]]:
        return dict

    @property
    def wire_type(self) -> Type[Mapping[KeyWireT, ValWireT]]:
        return dict

    def convert(
        self, wire_value: Mapping[KeyWireT, ValWireT]
    ) -> Mapping[KeyActualT, ValActualT]:
        return {
            self.key_type.convert(k): self.value_type.convert(v)
            for k, v in wire_value.items()
        }


@dataclass(frozen=True)
class ToolParameter[ActualT, WireT]:
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
    bindings: Set[Tuple[ToolParameter, Any]]


@dataclass(frozen=True)
class WireParameterBindings:
    bindings: Set[Tuple[str, Any]]

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "WireParameterBindings":
        return cls(bindings=set(d.items()))


@dataclass(frozen=True)
class FollowUpToolCall:
    tool_name: str
    wire_parameter_bindings: WireParameterBindings
    reasoning_text: Optional[str] = None


@dataclass(frozen=True)
class ToolResponse:
    is_failed: bool
    is_terminated: bool
    content: str
    reminder: Optional[str] = None
    suppression_key: Optional[str] = None
    follow_up_tool_call: Optional[FollowUpToolCall] = None



class Tool(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def parameters(self) -> Set[ToolParameter]: ...

    def execute_tool(
        self, actual_parameter_bindings: ActualParameterBindings
    ) -> ToolResponse: ...


class ToolManager(Protocol):
    @property
    def installed_tools(self) -> Set[Tool]: ...

    def install_tool(self, tool: Tool) -> None: ...

    def execute_tool(
        self, name: str, wire_parameter_bindings: WireParameterBindings
    ) -> ToolResponse: ...

    def execute_tool_with_arguments(
        self, name: str, arguments: Mapping[str, Any]
    ) -> ToolResponse: ...

