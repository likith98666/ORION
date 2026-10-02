from typing import Any

from orion.core.security.secrets import SecretReference
from orion.core.tools.input_schema import (
    ToolInputSchema,
    ToolInputType,
)


class ToolInputValidationError(ValueError):
    """Raised when tool arguments violate the declared input boundary."""


class ToolInputValidator:
    """Validates untrusted tool arguments against a bounded input schema."""

    def validate(
        self,
        arguments: dict[str, Any],
        schema: ToolInputSchema,
    ) -> None:
        if not isinstance(arguments, dict):
            raise ToolInputValidationError(
                "Tool arguments must be a dictionary."
            )

        if len(arguments) > schema.max_fields:
            raise ToolInputValidationError(
                f"Tool arguments exceed the maximum field count "
                f"of {schema.max_fields}."
            )

        fields = {field.name: field for field in schema.fields}

        if not schema.allow_unknown_fields:
            unknown = sorted(set(arguments) - fields.keys())

            if unknown:
                raise ToolInputValidationError(
                    f"Unknown tool argument field(s): {', '.join(unknown)}."
                )

        for field in schema.fields:
            if field.required and field.name not in arguments:
                raise ToolInputValidationError(
                    f"Required tool argument '{field.name}' is missing."
                )

        for name, value in arguments.items():
            input_field = fields.get(name)

            if input_field is None:
                self._validate_value(
                    value=value,
                    path=name,
                    input_type=ToolInputType.ANY,
                    nullable=True,
                    max_length=schema.max_string_length,
                    max_items=schema.max_collection_items,
                    depth=0,
                    max_depth=schema.max_depth,
                )
                continue

            if value is None:
                if input_field.nullable:
                    continue

                raise ToolInputValidationError(
                    f"Tool argument '{name}' cannot be null."
                )

            self._validate_value(
                value=value,
                path=name,
                input_type=input_field.input_type,
                nullable=input_field.nullable,
                max_length=(
                    input_field.max_length
                    if input_field.max_length is not None
                    else schema.max_string_length
                ),
                max_items=(
                    input_field.max_items
                    if input_field.max_items is not None
                    else schema.max_collection_items
                ),
                depth=0,
                max_depth=schema.max_depth,
            )

    def _validate_value(
        self,
        value: Any,
        path: str,
        input_type: ToolInputType,
        nullable: bool,
        max_length: int,
        max_items: int,
        depth: int,
        max_depth: int,
    ) -> None:
        if value is None:
            if nullable:
                return

            raise ToolInputValidationError(
                f"Tool argument '{path}' cannot be null."
            )

        if depth > max_depth:
            raise ToolInputValidationError(
                f"Tool argument '{path}' exceeds maximum nesting depth "
                f"of {max_depth}."
            )

        if not self._matches_type(value, input_type):
            raise ToolInputValidationError(
                f"Tool argument '{path}' must be of type "
                f"'{input_type.value}'."
            )

        if input_type == ToolInputType.SECRET_REFERENCE:
            return

        if isinstance(value, str):
            if len(value) > max_length:
                raise ToolInputValidationError(
                    f"Tool argument '{path}' exceeds maximum string "
                    f"length of {max_length}."
                )

            return

        if isinstance(value, (list, tuple, set)):
            if len(value) > max_items:
                raise ToolInputValidationError(
                    f"Tool argument '{path}' exceeds maximum collection "
                    f"size of {max_items}."
                )

            for index, item in enumerate(value):
                self._validate_value(
                    value=item,
                    path=f"{path}[{index}]",
                    input_type=ToolInputType.ANY,
                    nullable=True,
                    max_length=max_length,
                    max_items=max_items,
                    depth=depth + 1,
                    max_depth=max_depth,
                )

            return

        if isinstance(value, dict):
            if len(value) > max_items:
                raise ToolInputValidationError(
                    f"Tool argument '{path}' exceeds maximum object "
                    f"field count of {max_items}."
                )

            for key, item in value.items():
                if not isinstance(key, str):
                    raise ToolInputValidationError(
                        f"Tool argument '{path}' contains a non-string key."
                    )

                if len(key) > max_length:
                    raise ToolInputValidationError(
                        f"Tool argument '{path}' contains an oversized key."
                    )

                self._validate_value(
                    value=item,
                    path=f"{path}.{key}",
                    input_type=ToolInputType.ANY,
                    nullable=True,
                    max_length=max_length,
                    max_items=max_items,
                    depth=depth + 1,
                    max_depth=max_depth,
                )

    @staticmethod
    def _matches_type(
        value: Any,
        input_type: ToolInputType,
    ) -> bool:
        if input_type == ToolInputType.ANY:
            return True

        if input_type == ToolInputType.STRING:
            return isinstance(value, str)

        if input_type == ToolInputType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)

        if input_type == ToolInputType.FLOAT:
            return isinstance(value, (float, int)) and not isinstance(
                value, bool
            )

        if input_type == ToolInputType.BOOLEAN:
            return isinstance(value, bool)

        if input_type == ToolInputType.LIST:
            return isinstance(value, list)

        if input_type == ToolInputType.DICT:
            return isinstance(value, dict)

        if input_type == ToolInputType.SECRET_REFERENCE:
            return isinstance(value, SecretReference)

        return False
