from typing import Any

from agent_analytics.runtime.registry.analytics_metadata import (
    AnalyticsMetadata,
    FieldSpec,
    FieldType,
)


class DependencyValidator:
    """Validates analytics dependencies"""

    @staticmethod
    def get_required_input_fields(metadata: AnalyticsMetadata) -> dict[str, Any]:
        """
        Gets dict of required input fields and their specifications
        Returns: Dict[field_name, field_spec]
        """
        return {
            field.name: field
            for field in metadata.template.input_spec.fields
            if field.required
        }

    @staticmethod
    def get_output_fields(metadata: AnalyticsMetadata) -> dict[str, Any]:
        """
        Gets dict of output fields and their specifications
        Returns: Dict[field_name, field_spec]
        """
        return {
            field.name: field
            for field in metadata.template.output_spec.fields
        }

    @staticmethod
    def validate_dependency_fields(
    analytics_metadata: AnalyticsMetadata,
    dependency_metadata: AnalyticsMetadata,
    pipeline_inputs: set[str]
    ) -> None:
        # Get all required input fields with their specs
        required_inputs = {
            field.name: field
            for field in analytics_metadata.template.input_spec.fields
            if field.required
        }

        # Get dependency outputs with their specs
        dependency_outputs = {
            field.name: field
            for field in dependency_metadata.template.output_spec.fields
        }

        for field_name, input_spec in required_inputs.items():
            # Check field exists
            if field_name not in dependency_outputs and field_name not in pipeline_inputs:
                raise ValueError(
                    f"Required input field '{field_name}' for analytics '{analytics_metadata.id}' "
                    f"is not provided by dependency '{dependency_metadata.id}' "
                    f"and is not available in pipeline inputs"
                )

            # Check type compatibility if field comes from dependency
            if field_name in dependency_outputs:
                output_spec = dependency_outputs[field_name]

                # Basic type check
                if input_spec.type != output_spec.type:
                    raise ValueError(
                        f"Type mismatch for field {field_name}: "
                        f"dependency '{dependency_metadata.id}' provides {output_spec.type}, "
                        f"but '{analytics_metadata.id}' requires {input_spec.type}"
                    )

                # Array element type check if applicable
                if input_spec.type == FieldType.ARRAY:
                    if input_spec.array_type != output_spec.array_type:
                        raise ValueError(
                            f"Array element type mismatch for field {field_name}: "
                            f"dependency '{dependency_metadata.id}' provides {output_spec.array_type}, "
                            f"but '{analytics_metadata.id}' requires {input_spec.array_type}"
                        )

    @staticmethod
    def _create_dummy_value(field_spec: FieldSpec) -> Any:
        """Creates a dummy value of the correct type for type checking"""
        if field_spec.type == FieldType.STRING:
            return ""
        elif field_spec.type == FieldType.INTEGER:
            return 0
        elif field_spec.type == FieldType.FLOAT:
            return 0.0
        elif field_spec.type == FieldType.BOOLEAN:
            return False
        elif field_spec.type == FieldType.ARRAY:
            if field_spec.array_type:
                dummy_spec = FieldSpec(
                    name=field_spec.name,
                    type=field_spec.array_type,
                    description="Array element"
                )
                return [DependencyValidator._create_dummy_value(dummy_spec)]
            return []
        else:  # ANY
            return None


