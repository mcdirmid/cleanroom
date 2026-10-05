# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: f74d5c72c898
# --- END CLEANROOM METADATA ---

# Requirements specified in tool_provider.pyi

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Mapping,
    NewType,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

ToolName = NewType("ToolName", str)
ToolDescription = NewType("ToolDescription", str)
ParameterName = NewType("ParameterName", str)
ParameterDescription = NewType("ParameterDescription", str)
MissingMessage = NewType("MissingMessage", str)
ToolResponseContent = NewType("ToolResponseContent", str)
ToolReminder = NewType("ToolReminder", str)
SuppressionKey = NewType("SuppressionKey", str)
ReasoningText = NewType("ReasoningText", str)
ConversionErrorMessage = NewType("ConversionErrorMessage", str)
type WireType = str | int | float | bool | Mapping[str, Any] | Sequence[Any]
SomeParameterActualType = NewType("SomeParameterActualType", object)


@dataclass(frozen=True)
class ParameterConversionError(ValueError):
    message: ConversionErrorMessage


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


@dataclass(frozen=True)
class MappingParameterType[
    KeyActualT,
    ValActualT,
    ValWireT,
](ParameterType[Mapping[KeyActualT, ValActualT], Mapping[str, ValWireT]]):
    key_type: ParameterType[KeyActualT, str]
    value_type: ParameterType[ValActualT, ValWireT]

    @property
    def actual_type(self) -> Type[Mapping[KeyActualT, ValActualT]]:
        return dict

    @property
    def wire_type(self) -> Type[Mapping[str, ValWireT]]:
        return dict

    def convert(
        self, wire_value: Mapping[str, ValWireT]
    ) -> Mapping[KeyActualT, ValActualT]:
        return {
            self.key_type.convert(k): self.value_type.convert(v)
            for k, v in wire_value.items()
        }


STRING_PARAMETER_TYPE: IdentityParameterType[str] = IdentityParameterType(str)
INTEGER_PARAMETER_TYPE: IdentityParameterType[int] = IdentityParameterType(int)
BOOLEAN_PARAMETER_TYPE: IdentityParameterType[bool] = IdentityParameterType(bool)
FLOAT_PARAMETER_TYPE: IdentityParameterType[float] = IdentityParameterType(float)

_WireString = str
_WireInteger = int
_WireFloat = float
_WireBoolean = bool
_WireList = list
_WireDictionary = dict
_DictionaryParameterType = MappingParameterType


@dataclass(frozen=True)
class ToolParameter[ActualT, WireT]:
    name: ParameterName
    description: ParameterDescription
    parameter_type: ParameterType[ActualT, WireT]
    is_required: bool = True
    default_value: Optional[ActualT] = None
    missing_message: Optional[Callable[[Set[ParameterName]], MissingMessage]] = None

    @property
    def parameter_converter(self) -> ParameterType[ActualT, WireT]:
        return self.parameter_type


class _WireParameterBindings(dict[ParameterName, WireType]):
    def __init__(
        self,
        *args: Any,
        items: Optional[Any] = None,
        bindings: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if items is not None:
            if isinstance(items, Mapping):
                self.update(items)
            else:
                self.update(dict(items))
        if bindings is not None:
            if isinstance(bindings, Mapping):
                self.update(bindings)
            else:
                self.update(dict(bindings))

    @property
    def items_set(self) -> FrozenSet[Tuple[ParameterName, WireType]]:
        return frozenset(self.items())

    @property
    def bindings(self) -> FrozenSet[Tuple[ParameterName, WireType]]:
        return frozenset(self.items())


_MISSING = object()


class _ActionParameterBindings(dict[Any, Any]):
    def __init__(
        self,
        *args: Any,
        items: Optional[Any] = None,
        bindings: Optional[Any] = None,
        parameters_by_name: Optional[
            Mapping[ParameterName, ToolParameter[Any, Any]]
        ] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        params_by_name = dict(parameters_by_name or {})
        object.__setattr__(self, "_params_by_name", params_by_name)
        if items is not None:
            if isinstance(items, Mapping):
                self.update(items)
            else:
                self.update(dict(items))
        if bindings is not None:
            if isinstance(bindings, Mapping):
                self.update(bindings)
            else:
                self.update(dict(bindings))

    def get(self, key: Any, default: Any = None) -> Any:
        if super().__contains__(key):
            return super().__getitem__(key)
        if isinstance(key, str):
            params_by_name = getattr(self, "_params_by_name", {})
            param_obj = params_by_name.get(key)
            if param_obj is not None and super().__contains__(param_obj):
                return super().__getitem__(param_obj)
            for p in self:
                if getattr(p, "name", None) == key:
                    return super().__getitem__(p)
        elif hasattr(key, "name"):
            name = getattr(key, "name")
            if super().__contains__(name):
                return super().__getitem__(name)
        return default

    def __getitem__(self, key: Any) -> Any:
        val = self.get(key, _MISSING)
        if val is _MISSING:
            raise KeyError(key)
        return val

    def __contains__(self, key: object) -> bool:
        if super().__contains__(key):
            return True
        if isinstance(key, str):
            for p in self:
                if getattr(p, "name", None) == key:
                    return True
        elif hasattr(key, "name"):
            if super().__contains__(getattr(key, "name")):
                return True
        return False

    @property
    def bindings(self) -> FrozenSet[Tuple[Any, Any]]:
        return frozenset(self.items())


_ActualParameterBindings = _ActionParameterBindings


@dataclass(frozen=True)
class FollowUpToolCall:
    tool_name: ToolName
    wire_parameter_bindings: Mapping[ParameterName, WireType]
    reasoning_text: Optional[ReasoningText] = None


@dataclass(frozen=True)
class ToolResponse:
    is_failed: bool
    is_terminated: bool
    content: ToolResponseContent
    reminder: Optional[ToolReminder] = None
    suppression_key: Optional[SuppressionKey] = None
    follow_up_tool_call: Optional[FollowUpToolCall] = None


class Tool(Protocol):
    @property
    def name(self) -> ToolName: ...

    @property
    def description(self) -> ToolDescription: ...

    @property
    def parameters(self) -> Mapping[ParameterName, ToolParameter[Any, Any]]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            ToolParameter[Any, Any], SomeParameterActualType
        ],
    ) -> ToolResponse: ...


class ToolManager(Protocol):
    @property
    def installed_tools(self) -> Mapping[ToolName, Tool]: ...

    def install_tool(self, tool: Tool) -> None: ...

    def execute_tool(
        self, name: ToolName, wire_parameter_bindings: Mapping[ParameterName, WireType]
    ) -> ToolResponse: ...
