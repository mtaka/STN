"""Value types for STN Core."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


@dataclass
class VText:
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass
class VNumber:
    value: float

    def __str__(self) -> str:
        v = self.value
        if v == int(v):
            return str(int(v))
        return str(v)


@dataclass
class VDate:
    value: str  # ISO-8601

    def __str__(self) -> str:
        return self.value


@dataclass
class VBool:
    value: bool

    def __str__(self) -> str:
        return str(self.value).lower()


@dataclass
class VEnum:
    value: str
    choices: list[str]

    def __str__(self) -> str:
        return self.value


@dataclass
class VList:
    items: list["Value"]

    def __post_init__(self) -> None:
        # Non-field DOM references — excluded from __eq__ / __repr__
        self._parent: "VEntity | VList | _Empty | None" = None
        self._document: "object | None" = None  # Document (forward ref)

    def __str__(self) -> str:
        return "[" + ", ".join(str(v) for v in self.items) + "]"

    @property
    def parent(self) -> "VEntity | VList | None":
        return self._parent  # type: ignore[return-value]

    @property
    def document(self) -> "object | None":
        return self._document

    def locate(self, path: "str | int", callback=lambda x: x):
        """Yield (callback(result), path_str) pairs via the locator."""
        from .locator import locate_value
        return locate_value(self, path, callback)

    def get(self, path: "str | int") -> "list":
        """Return all locate() results as a list."""
        return [v for v, _ in self.locate(path)]

    def get_first(self, path: "str | int") -> "Value":
        """Return the first locate() result, or Empty."""
        for v, _ in self.locate(path):
            return v  # type: ignore[return-value]
        return Empty

    @property
    def children(self) -> "list[Value]":
        """Direct child values (all items in the list)."""
        return list(self.items)

    def to_obj(self):
        """Convert to a plain Python object (list for VList)."""
        from .projector import value_to_obj
        return value_to_obj(self)

    def to_json(self, **kwargs) -> str:
        """Serialize to a JSON string."""
        from .projector import value_to_json
        return value_to_json(self, **kwargs)

    def to_yaml(self, **kwargs) -> str:
        """Serialize to a YAML string."""
        from .projector import value_to_yaml
        return value_to_yaml(self, **kwargs)


@dataclass
class VEntity:
    typedef: "TypeDef | None"   # TypeDef from typedef.py (forward ref)
    type_name: str | None
    fields: dict[str, "Value"] = field(default_factory=dict)
    props: dict[str, "Value"] = field(default_factory=dict)
    reserved: dict[str, "Value"] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Non-field DOM references — excluded from __eq__ / __repr__
        self._parent: "VEntity | VList | _Empty | None" = None
        self._document: "object | None" = None  # Document (forward ref)

    def __str__(self) -> str:
        if self.type_name:
            return f"VEntity({self.type_name})"
        return "VEntity"

    @property
    def parent(self) -> "VEntity | VList | None":
        return self._parent  # type: ignore[return-value]

    @property
    def document(self) -> "object | None":
        return self._document

    def locate(self, path: "str | int", callback=lambda x: x):
        """Yield (callback(result), path_str) pairs via the locator."""
        from .locator import locate_value
        return locate_value(self, path, callback)

    def get(self, path: "str | int") -> "list":
        """Return all locate() results as a list."""
        return [v for v, _ in self.locate(path)]

    def get_first(self, path: "str | int") -> "Value":
        """Return the first locate() result, or Empty."""
        for v, _ in self.locate(path):
            return v  # type: ignore[return-value]
        return Empty

    @property
    def children(self) -> "list[Value]":
        """Direct child values (fields + props, in definition order)."""
        return list(self.fields.values()) + list(self.props.values())

    def to_obj(self):
        """Convert to a plain Python object (dict or list)."""
        from .projector import value_to_obj
        return value_to_obj(self)

    def to_json(self, **kwargs) -> str:
        """Serialize to a JSON string."""
        from .projector import value_to_json
        return value_to_json(self, **kwargs)

    def to_yaml(self, **kwargs) -> str:
        """Serialize to a YAML string."""
        from .projector import value_to_yaml
        return value_to_yaml(self, **kwargs)


class _Empty:
    """Singleton for undefined references."""

    _instance: "_Empty | None" = None

    def __new__(cls) -> "_Empty":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "Empty"

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return "Empty"


Empty = _Empty()

Value = Union[VText, VNumber, VDate, VBool, VEnum, VList, VEntity, _Empty]
