from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event type enumeration"""
    DATA_AVAILABLE = "data_available"


class DataItemType(str, Enum):
    """Data item type enumeration"""
    SPAN = "span"


class NotificationContent(BaseModel):
    """Base notification content with timestamp"""
    timestamp: datetime = Field(
        ...,
        description="Timestamp of the event",
        examples=["2024-01-01T10:00:00Z"]
    )


class DataAvailableContent(NotificationContent):
    """Content for data_available event notifications"""
    trace_id: str = Field(
        ...,
        description="Trace identifier",
        examples=["trace_123456"]
    )
    trace_group_id: Optional[str] = Field(
        None,
        description="Trace group identifier",
        examples=["group_789"]
    )
    data_subtype: Optional[str] = Field(
        None,
        description="Data subtype",
        examples=["http_request"]
    )
    creating_plugin_id: Optional[str] = Field(
        None,
        description="ID of the plugin that created this data",
        examples=["jaeger_collector"]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata",
        examples=[{"span_count": 15, "duration_ms": 250}]
    )


class EventNotificationRequest(BaseModel):
    """Request model for event notification"""
    event_type: EventType = Field(
        ...,
        description="Type of the event"
    )
    data_item_type: DataItemType = Field(
        ...,
        description="Type of data item"
    )
    content: DataAvailableContent = Field(
        ...,
        description="Event content"
    )


class EventNotification(EventNotificationRequest):
    """Event notification with auto-generated event ID"""
    event_id: UUID = Field(
        ...,
        description="Auto-generated unique identifier for the event",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )


class EventResponse(BaseModel):
    """Successful event processing response"""
    success: bool = Field(
        ...,
        description="Whether the event was accepted",
        examples=[True]
    )
    event_id: str = Field(  # Changed from UUID to str
        ...,
        description="ID of the processed event (format: analytics_id:trace_id)",
        examples=["task_analytics:trace_123456"]
    )
    message: str = Field(
        ...,
        description="Response message",
        examples=["Event accepted for processing"]
    )


class ValidationError(BaseModel):
    """Individual validation error"""
    field: str = Field(
        ...,
        description="Field that failed validation",
        examples=["trace_id"]
    )
    message: str = Field(
        ...,
        description="Error message",
        examples=["Field is required"]
    )
    code: str = Field(
        ...,
        description="Error code",
        examples=["missing"]
    )


class ErrorResponse(BaseModel):
    """Error response for 400 and 500 errors"""
    error: str = Field(
        ...,
        description="Error type",
        examples=["INVALID_REQUEST"]
    )
    message: str = Field(
        ...,
        description="Error message",
        examples=["The request could not be processed"]
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )


class ValidationErrorResponse(BaseModel):
    """Error response for validation failures (422)"""
    error: str = Field(
        ...,
        description="Error type",
        examples=["VALIDATION_ERROR"]
    )
    message: str = Field(
        ...,
        description="Error message",
        examples=["Request validation failed"]
    )
    validation_errors: list[ValidationError] = Field(
        ...,
        description="List of validation errors"
    )