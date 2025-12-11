from abc import ABC
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from pydantic import BaseModel, Field, model_validator, field_validator
from enum import Enum
import json

from agent_analytics.core.data.element_data import ElementData


class SpanKind(str, Enum):
    INTERNAL = "SpanKind.INTERNAL"
    CLIENT = "SpanKind.CLIENT"
    SERVER = "SpanKind.SERVER"
    PRODUCER = "SpanKind.PRODUCER"
    CONSUMER = "SpanKind.CONSUMER"

class SpanStatus(BaseModel):
    status_code: str

class SpanContext(BaseModel):
    trace_id: str
    span_id: str
    trace_state: str = "[]"

class SpanEvent(BaseModel):
    name: str
    timestamp: datetime
    attributes: Dict[str, Any] = {}
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def convert_timestamp(cls, v):
        if isinstance(v, int):
            if v > 1e15:  # Microseconds (like your 1747900772479476)
                return datetime.fromtimestamp(v / 1000000)  # Preserves full precision
            elif v > 1e12:  # Milliseconds
                return datetime.fromtimestamp(v / 1000)
            else:  # Seconds
                return datetime.fromtimestamp(v)
        return v    
    
class ResourceAttributes(BaseModel):
    service_name: str = Field(
        serialization_alias="service.name",
        validation_alias="service.name"
    )
    telemetry_sdk_language: Optional[str] = Field(
        None,
        serialization_alias="telemetry.sdk.language",
        validation_alias="telemetry.sdk.language"
    )
    telemetry_sdk_name: Optional[str] = Field(
        None,
        serialization_alias="telemetry.sdk.name",
        validation_alias="telemetry.sdk.name"
    )
    telemetry_sdk_version: Optional[str] = Field(
        None,
        serialization_alias="telemetry.sdk.version",
        validation_alias="telemetry.sdk.version"
    )

    model_config = {
        "populate_by_name": True,
        "extra": "allow",
        "alias_generator": None
    }    



class Resource(BaseModel):
    attributes: ResourceAttributes
    schema_url: str = ""

class BaseSpanData(ElementData):
    """Base class for all span types with common fields"""    
    context: SpanContext
    parent_id: Optional[str]=None
    kind: SpanKind
    start_time: datetime
    end_time: datetime
    status: SpanStatus
    resource: Resource
    # Store original attributes
    raw_attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[SpanEvent] = []
    links: List[Any] = []

    @model_validator(mode='before')
    @classmethod
    def set_ids_and_attributes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if 'context' in data:
                # Use span_id as element_id if not provided
                if 'element_id' not in data:
                    data['element_id'] = data['context']['span_id']
                
                # Use trace_id as root_id if not provided
                if 'root_id' not in data:
                    data['root_id'] = data['context']['trace_id']
            
            # Store original attributes
            if 'attributes' in data and 'raw_attributes' not in data:
                data['raw_attributes'] = data['attributes']
        
        return data
