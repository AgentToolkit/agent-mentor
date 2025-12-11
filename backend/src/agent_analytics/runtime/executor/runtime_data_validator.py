from typing import Any

from agent_analytics.runtime.registry.analytics_metadata import AnalyticsMetadata, FieldType
from agent_analytics.runtime.registry.validators.field_type_validator import FieldTypeValidator


class RuntimeDataValidator:
    """Runtime data validator"""

    @staticmethod
    def validate_input_data(input_data: dict[str, Any], metadata: AnalyticsMetadata) -> str | None:
        """Validates input data using shared field validation logic"""
        for field_spec in metadata.template.input_spec.fields:
            value = input_data.get(field_spec.name)
            error = FieldTypeValidator.validate_field_value(value, field_spec)
            if error:
                return error
        return None



    @staticmethod
    def validate_field_value(value: Any, field_spec) -> str | None:
        """
        Validates a single field value against its specification
        Returns error message if validation fails, None otherwise
        """
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
            if not isinstance(value, (int, float)):
                return f"Field {field_spec.name} must be numeric"
        elif field_spec.type == FieldType.BOOLEAN:
            if not isinstance(value, bool):
                return f"Field {field_spec.name} must be boolean"
        elif field_spec.type == FieldType.ARRAY:
            if not isinstance(value, (list, tuple)):
                return f"Field {field_spec.name} must be array"
            # Validate array elements if type specified
            if field_spec.array_type:
                for i, item in enumerate(value):
                    # Create temporary field spec for array element validation
                    element_spec = type(field_spec)(
                        name=f"{field_spec.name}[{i}]",
                        type=field_spec.array_type,
                        description="Array element",
                        required=True  # Array elements are always required
                    )
                    error = RuntimeDataValidator.validate_field_value(item, element_spec)
                    if error:
                        return f"Invalid array element at index {i}: {error}"
        elif field_spec.type == FieldType.ANY:
            # No type validation for ANY type
            pass
        else:
            return f"Unknown field type {field_spec.type} for field {field_spec.name}"

        return None


    @staticmethod
    def validate_output_data(output_data: dict[str, Any], metadata: AnalyticsMetadata) -> str | None:
        """
        Validates output data against analytics metadata specification
        Returns error message if validation fails, None otherwise
        """
        for field_spec in metadata.template.output_spec.fields:
            value = output_data.get(field_spec.name)
            error = RuntimeDataValidator.validate_field_value(value, field_spec)
            if error:
                return error
        return None
