import datetime
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class FieldType(str, Enum):
    """Supported field types for analytics input/output"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    ANY = "any"

class FieldSpec(BaseModel):
    """Specification for an individual field"""
    name: str = Field(..., description="Name of the field")
    type: FieldType = Field(..., description="Type of the field")
    required: bool = Field(default=True, description="Whether the field is required")
    description: str = Field(..., description="Description of what this field represents")
    array_type: FieldType | None = Field(
        default=None,
        description="For array types, specifies the type of array elements"
    )
    default: Any | None = Field(
        default=None,
        description="Default value for the field"
    )

    @model_validator(mode='after')
    def validate_array_type(self):
        if self.type == FieldType.ARRAY and not self.array_type:
            raise ValueError(f"Array field {self.name} must specify array_type")
        return self

    @model_validator(mode='after')
    def validate_default_value(self):
        if self.default is not None:
            if self.type == FieldType.STRING and not isinstance(self.default, str):
                raise ValueError(f"Default value for string field {self.name} must be string")
            elif self.type == FieldType.INTEGER and not isinstance(self.default, int):
                raise ValueError(f"Default value for integer field {self.name} must be integer")
            elif self.type == FieldType.FLOAT and not isinstance(self.default, (int, float)):
                raise ValueError(f"Default value for float field {self.name} must be numeric")
            elif self.type == FieldType.BOOLEAN and not isinstance(self.default, bool):
                raise ValueError(f"Default value for boolean field {self.name} must be boolean")
            elif self.type == FieldType.ARRAY:
                if not isinstance(self.default, (list, tuple)):
                    raise ValueError(f"Default value for array field {self.name} must be list or tuple")
                if self.array_type:
                    # Validate each element in array
                    temp_spec = FieldSpec(
                        name=f"{self.name}_element",
                        type=self.array_type,
                        description="Array element"
                    )
                    for i, item in enumerate(self.default):
                        if (temp_spec.type == FieldType.STRING and not isinstance(item, str)) or \
                           (temp_spec.type == FieldType.INTEGER and not isinstance(item, int)) or \
                           (temp_spec.type == FieldType.FLOAT and not isinstance(item, (int, float))) or \
                           (temp_spec.type == FieldType.BOOLEAN and not isinstance(item, bool)):
                            raise ValueError(f"Array element at index {i} has invalid type for field {self.name}")
        return self


class IOSpec(BaseModel):

    """Input/Output specification for an analytics plugin"""
    fields: list[FieldSpec] = Field(..., description="List of field specifications")

    def get_field_names(self) -> list[str]:
        """Get list of all field names"""
        return [field.name for field in self.fields]

    @model_validator(mode='after')
    def validate_fields(self):
        if not self.fields:
            raise ValueError("IOSpec must contain at least one field")

        field_names = set()
        for field in self.fields:
            if field.name in field_names:
                raise ValueError(f"Duplicate field name found: {field.name}")
            field_names.add(field.name)
        return self

# Enums for the restricted field values
class Status(str,Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"

class RuntimeType(str, Enum):
    PYTHON = 'PYTHON'

class TriggerType(str, Enum):
    DIRECT = "DIRECT"


# Runtime configuration
class RuntimeConfig(BaseModel):
    type: RuntimeType = Field(..., description="Runtime type, currently only supports PYTHON")
    config: dict[str, str] = Field(..., description="Runtime-specific configuration",min_length=1)

# Controller configuration
class ControllerConfig(BaseModel):
    trigger_config: dict[str, TriggerType] = Field(
        ..., description="Trigger configuration for the controller"
    )
    dependsOn: list[str] = Field(default_factory=list, description="List of dependent analytics IDs")
    triggers: list[str] = Field(default_factory=list, description="List of analytics IDs to trigger after execution")

# Template structure
class TemplateConfig(BaseModel):
    runtime: RuntimeConfig = Field(..., description="Runtime configuration details")
    controller: ControllerConfig = Field(..., description="Controller configuration details")
    config: dict[str, Any | None] = Field(default_factory=dict, description="Template-specific parameters")
    input_spec: IOSpec | None = None
    output_spec: IOSpec | None = None


# AnalyticsMetadata definition
class AnalyticsMetadata(BaseModel):
    id: str = Field(..., description="Unique analytics identifier")
    name: str = Field(..., description="Analytics name")
    description: str = Field(..., description="Analytics description")
    version: str = Field(...,description="Version of the analytics")
    owner: str = Field(..., description="Owner of the analytics")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    status: Status = Field(..., description="Current status of the analytics")
    template: TemplateConfig = Field(..., description="Template details for analytics execution")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    def equals(self, other) -> bool:
        """Compare two AnalyticsMetadata instances for equality."""
        if not isinstance(other, AnalyticsMetadata):
            return False

        return (
            self.id == other.id and
            self.name == other.name and
            self.version == other.version and
            self.template.runtime.config["module_path"] == other.template.runtime.config["module_path"] and
            self.template.controller.dependsOn == other.template.controller.dependsOn and
            self.template.controller.triggers == other.template.controller.triggers
        )
