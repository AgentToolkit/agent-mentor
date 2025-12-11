from agent_analytics.runtime.registry.analytics_metadata import AnalyticsMetadata, FieldType
from agent_analytics.runtime.registry.validators.field_type_validator import FieldTypeValidator


class FieldValidator:
    """Registration-time field specification validator"""

    @staticmethod
    def validate_field_specs(metadata: AnalyticsMetadata):
        """Validates field specifications including any default values"""
        # Validate input spec structure
        field_names = set()
        for field in metadata.template.input_spec.fields:
            if field.name in field_names:
                raise ValueError(f"Duplicate input field name: {field.name}")
            field_names.add(field.name)

            # Validate array type specification
            if field.type == FieldType.ARRAY and not field.array_type:
                raise ValueError(f"Array field {field.name} must specify array_type")

            # Validate default value if present
            if field.default is not None:
                error = FieldTypeValidator.validate_field_value(field.default, field)
                if error:
                    raise ValueError(f"Invalid default value for field {field.name}: {error}")

        # Similar validation for output spec
        field_names = set()
        for field in metadata.template.output_spec.fields:
            if field.name in field_names:
                raise ValueError(f"Duplicate output field name: {field.name}")
            field_names.add(field.name)

            if field.type == FieldType.ARRAY and not field.array_type:
                raise ValueError(f"Array field {field.name} must specify array_type")

            # Output fields shouldn't have default values
            if field.default is not None:
                raise ValueError(f"Output field {field.name} should not have a default value")
