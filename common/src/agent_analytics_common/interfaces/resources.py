from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Any, Union, Dict
from enum import Enum
from .elements import Element, AttributeValue

class ResourceCategory(str, Enum):
    TEMPLATE = "TEMPLATE"
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    CODE = "CODE"
    ENCODING = "ENCODING"
    FILE = "FILE"
    DB = "DB"
    JSONSTRING = "JSONSTRING"

class Resource(Element):
    category: Union[ResourceCategory, str] = Field(
        None, description="Category of the resource. E.g. IMAGE, TEMPLATE"
    )
    format: Optional[str] = Field(
        None, description="Format of the resource. E.g. CSV, PDF"
    )
    payload: AttributeValue = Field(
        None, description="The actual serialized content (payload) of the resource."
    )
    