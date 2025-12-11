"""
Configuration classes for Agent Analytics SDK.

This module provides configuration models for different tracer types:
- LogExporterConfig: For file-based logging
- RemoteExporterConfig: For OTLP remote collectors
- CustomExporterConfig: For custom exporters
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from abc import ABC


class BaseExporterConfig(BaseModel, ABC):
    """
    Base configuration model for all collector types.

    Contains common attributes shared across different tracer implementations.
    """
    app_name: Optional[str] = Field(
        None,
        description="Application name for tracing. If not provided, will be auto-generated."
    )
    resource_attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="OpenTelemetry resource attributes to attach to spans"
    )
    new_trace_on_workflow: bool = Field(
        False,
        description="Whether to create a new trace context on workflow boundaries"
    )
    # Prevent passing irrelevant fields
    model_config = {
       "extra": "forbid"
    }


class LogExporterConfig(BaseExporterConfig):
    """
    Configuration for file-based log tracing (LOG tracer type).

    Writes OpenTelemetry spans to a local log file for debugging and development.
    """
    logs_dir_path: Optional[str] = Field(
        None,
        description="Directory path for log files. If not provided, defaults to './log'"
    )
    log_filename: Optional[str] = Field(
        None,
        description="Custom log filename (without .log extension). If not provided, uses caller filename."
    )


class RemoteExporterConfig(BaseExporterConfig):
    """
    Configuration for OTLP remote collector (REMOTE tracer type).

    Sends OpenTelemetry spans to a remote OTLP collector like Jaeger, Zipkin, or cloud providers.
    """
    endpoint: str = Field(
        ...,
        description="OTLP collector endpoint URL (e.g., 'http://localhost:4317' for Jeager)"
    )
    insecure: bool = Field(
        False,
        description="Whether to use insecure connection (no TLS). Set to False for production."
    )
    timeout: int = Field(
        10,
        ge=1,
        description="Connection timeout in seconds"
    )
    is_grpc: bool = Field(
        False,
        description="Whether to use gRPC protocol. False uses HTTP/protobuf."
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="Additional headers for authentication or metadata (e.g., API keys)"
    )

    @validator('endpoint')
    def validate_endpoint(cls, v: str) -> str:
        """Validate that endpoint has proper format."""
        v = v.strip()
        if not v:
            raise ValueError("Endpoint cannot be empty")

        # For gRPC endpoints, they might not have a protocol prefix
        if not any(v.startswith(prefix) for prefix in ['http://', 'https://', 'grpc://']):
            # Check if it looks like a host:port format
            if ':' not in v:
                raise ValueError(
                    "Endpoint must be a valid URL (http://host:port or https://host:port) "
                    "or host:port format for gRPC"
                )

        return v

    @validator('headers')
    def validate_headers(cls, v: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Ensure headers are properly formatted."""
        if v:
            # Ensure all header values are strings
            return {k: str(v) for k, v in v.items()}
        return v


class CustomExporterConfig(BaseExporterConfig):
    """
    Configuration for custom exporter (CUSTOM tracer type).

    Used when providing your own SpanExporter implementation.
    The actual exporter is passed separately to the initialization method.
    """
    pass  # No additional fields needed - custom exporter is passed separately


# For backward compatibility, keep OTLPCollectorConfig as an alias
OTLPCollectorConfig = RemoteExporterConfig
