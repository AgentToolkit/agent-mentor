import importlib
from inspect import isabstract

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from agent_analytics.core.plugin.base_plugin import BaseAnalyticsPlugin
from agent_analytics.runtime.registry.analytics_metadata import (
    AnalyticsMetadata,
    FieldSpec,
    FieldType,
    IOSpec,
)


class PluginValidator:
    """Validates analytics code implementation"""

    @staticmethod
    def _model_to_io_spec(model: type[BaseModel]) -> IOSpec:
        """Convert a Pydantic model to IOSpec"""
        fields = []
        for field_name, field in model.model_fields.items():
            field_type = FieldType.ANY # Default to ANY instead of STRING
            array_type = None  # Initialize array_type
            annotation = field.annotation

            if annotation is not None:
                # Determine base field type
                if annotation == int:
                    field_type = FieldType.INTEGER
                elif annotation == float:
                    field_type = FieldType.FLOAT
                elif annotation == bool:
                    field_type = FieldType.BOOLEAN
                elif annotation == str:
                    field_type = FieldType.STRING
                elif hasattr(annotation, '__origin__'):
                    # Check if it's a List type
                    if annotation.__origin__ in (list, list):
                        field_type = FieldType.ARRAY
                        # Handle array element type
                        if hasattr(annotation, '__args__') and annotation.__args__:
                            element_type = annotation.__args__[0]
                            if element_type == str:
                                array_type = FieldType.STRING
                            elif element_type == int:
                                array_type = FieldType.INTEGER
                            elif element_type == float:
                                array_type = FieldType.FLOAT
                            elif element_type == bool:
                                array_type = FieldType.BOOLEAN
                            else:
                                array_type = FieldType.ANY

            # Check if field is required by checking if it has a default value
            is_required = (
                field.default is PydanticUndefined and
                field.default_factory is None
            )

            fields.append(FieldSpec(
                name=field_name,
                type=field_type,
                array_type=array_type,
                required=is_required,
                description=field.description or f"Field {field_name}"
            ))
        return IOSpec(fields=fields)

    @classmethod
    def get_plugin_io_specs(cls, plugin_class: type[BaseAnalyticsPlugin]) -> tuple[IOSpec, IOSpec]:
        """Get IOSpecs from a plugin class's input/output models"""
        input_model = plugin_class.get_input_model()
        output_model = plugin_class.get_output_model()
        return (
            cls._model_to_io_spec(input_model),
            cls._model_to_io_spec(output_model)
        )

    # @staticmethod
    # def validate_module_import(module_path: str):
    #     """Validates module can be imported and contains valid analytics class"""
    #     try:
    #         module = importlib.import_module(module_path)
    #         if not any(isinstance(obj, type) and issubclass(obj, BaseAnalyticsPlugin)
    #                   for obj in module.__dict__.values()):
    #             raise ValueError(f"Module {module_path} does not contain a valid analytics class")
    #         return module
    #     except ImportError as e:
    #         raise ImportError(f"Failed to load analytics module: {str(e)}")

    @classmethod
    def validate_module_import(cls, module_path: str) -> tuple[type[BaseAnalyticsPlugin], tuple[IOSpec, IOSpec]]:
        """
        Validates module can be imported and contains valid analytics class.
        Returns the module and IO specs.
        """
        try:
            module = importlib.import_module(module_path)

            # Find concrete implementation of BaseAnalyticsPlugin
            concrete_classes = [
                obj for obj in module.__dict__.values()
                if isinstance(obj, type) and
                issubclass(obj, BaseAnalyticsPlugin) and
                obj != BaseAnalyticsPlugin and
                not isabstract(obj)
            ]

            if not concrete_classes:
                raise ValueError(f"Module {module_path} does not contain a valid analytics class")

            if len(concrete_classes) > 1:
                raise ValueError("Multiple implementations of BaseAnalyticsPlugin found in module")

            plugin_class = concrete_classes[0]

            # Get IO specs from the plugin class
            specs = cls.get_plugin_io_specs(plugin_class)

            return plugin_class, specs

        except ImportError as e:
            raise ImportError(f"Failed to load analytics module: {str(e)}")

    @staticmethod
    def validate_field_usage(module: object, metadata: 'AnalyticsMetadata') -> None:
        """Additional field usage validation if needed"""
        pass
