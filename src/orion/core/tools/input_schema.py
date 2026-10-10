from dataclasses import dataclass
from enum import Enum


class ToolInputType(str, Enum):
    """Supported types for tool input validation."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    ANY = "any"
    SECRET_REFERENCE = "secret_reference"


@dataclass(frozen=True)
class ToolInputField:
    """Validation contract for one tool argument."""

    name: str
    input_type: ToolInputType
    required: bool = False
    nullable: bool = False
    max_length: int | None = None
    max_items: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Tool input field name cannot be empty.")

        if not isinstance(self.input_type, ToolInputType):
            raise TypeError("Tool input type must be a ToolInputType.")

        if self.max_length is not None and self.max_length < 1:
            raise ValueError("max_length must be greater than zero.")

        if self.max_items is not None and self.max_items < 1:
            raise ValueError("max_items must be greater than zero.")


@dataclass(frozen=True)
class ToolInputSchema:
    """Immutable validation contract for a tool's arguments."""

    fields: tuple[ToolInputField, ...] = ()
    allow_unknown_fields: bool = False
    max_fields: int = 32
    max_depth: int = 5
    max_string_length: int = 8192
    max_collection_items: int = 128

    def __post_init__(self) -> None:
        names = [field.name for field in self.fields]

        if len(names) != len(set(names)):
            raise ValueError("Tool input field names must be unique.")

        if self.max_fields < 1:
            raise ValueError("max_fields must be greater than zero.")

        if self.max_depth < 1:
            raise ValueError("max_depth must be greater than zero.")

        if self.max_string_length < 1:
            raise ValueError("max_string_length must be greater than zero.")

        if self.max_collection_items < 1:
            raise ValueError("max_collection_items must be greater than zero.")

        if not isinstance(self.allow_unknown_fields, bool):
            raise TypeError("allow_unknown_fields must be a boolean.")
