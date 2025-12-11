from typing import Any

from agent_analytics.runtime.registry.analytics_metadata import FieldType


class FieldTypeValidator:
    """Shared field type validation logic used by both registration and runtime validation"""

    @staticmethod
    def validate_field_value(value: Any, field_spec) -> str | None:
        """Core field validation logic used by both registration and runtime"""
        if value is None:
            if field_spec.required:
                return f"Required field {field_spec.name} is missing"
            return None

        # Type validation
        if field_spec.type == FieldType.STRING:
            if not isinstance(value, str):
                return f"Field {field_spec.name} must be string"

        elif field_spec.type == FieldType.INTEGER:
            if not isinstance(value, int):
                return f"Field {field_spec.name} must be integer"

        elif field_spec.type == FieldType.FLOAT:
            if not isinstance(value, (int, float)):  # Allow both int and float for flexibility
                return f"Field {field_spec.name} must be numeric (integer or float)"

        elif field_spec.type == FieldType.BOOLEAN:
            if not isinstance(value, bool):
                return f"Field {field_spec.name} must be boolean"

        elif field_spec.type == FieldType.ARRAY:
            if not isinstance(value, (list, tuple)):
                return f"Field {field_spec.name} must be array"

            # If array_type is specified, validate each element
            if field_spec.array_type:
                for i, item in enumerate(value):
                    # Create a temporary field spec for the array element
                    element_spec = type(field_spec)(
                        name=f"{field_spec.name}[{i}]",
                        type=field_spec.array_type,
                        description="Array element",
                        required=True  # Array elements are always required
                    )
                    error = FieldTypeValidator.validate_field_value(item, element_spec)
                    if error:
                        return f"Invalid array element at index {i}: {error}"

        elif field_spec.type == FieldType.ANY:
            # No type validation for ANY type
            pass

        else:
            return f"Unknown field type {field_spec.type} for field {field_spec.name}"

        return None
