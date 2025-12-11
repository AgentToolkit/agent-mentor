from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from .elements import Element
from .resources import Resource
from .elements import Element, AttributeValue
from datetime import datetime 

class Event(BaseModel):
    name: str
    timestamp: datetime
    attributes: Optional[Dict[str, AttributeValue]] = Field(default_factory=dict)

class AIEvent(Event, Element):
    """
    Represents an OpenTelemetry event capturing the lifecycle stage of an AI element.
    """
    class Status(str, Enum):
        CREATION = "CREATION"
        UPDATE = "UPDATE"
        START = "START"
        END = "END"
        SUSPENSION = "SUSPENSION"
        ABORTION = "ABORTION"
        FAILURE = "FAILURE"
        DELETE = "DELETE"      
    
    status: Optional[Status] = Field(
        None, description="The lifecycle status of the AI element captured by this event"
    )
    resources: Optional[List[str]] = Field(
        None, description="List of related resource IDs"
    )
