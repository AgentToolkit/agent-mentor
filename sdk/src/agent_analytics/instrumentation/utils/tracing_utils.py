from typing import Dict, Any, Optional

from opentelemetry import trace, context
from opentelemetry.trace import Status, StatusCode

from functools import wraps
import inspect


def _get_caller_metadata():
    # Get caller function
    # TODO: remove hardcoded
    caller_frame = inspect.stack()[2]
    caller_filename = caller_frame.filename
    caller_function = caller_frame.function
    return caller_filename, caller_function


def _prepare_attribute_for_otel(value: Any) -> Any:
    """
    Prepares values for OpenTelemetry attributes.

    OpenTelemetry supports these attribute types:
    - str: String values
    - bool: Boolean values
    - int: Integer values (64-bit)
    - float: Floating point values (64-bit)
    - list of the above types: Will be converted to comma-separated strings or JSON
    - dict: Will be converted to JSON string

    Complex types are handled by:
    - Enum: Converted to string representation
    - datetime: Converted to ISO format string
    - Pydantic models: Converted to JSON strings
    - Other objects: Converted to string representation
    """
    import json
    import datetime
    from enum import Enum

    if value is None:
        return None
    elif isinstance(value, (str, bool, int, float)):
        return value
    elif isinstance(value, Enum):
        return str(value)
    elif isinstance(value, datetime.datetime):
        return value.isoformat()
    elif isinstance(value, list):
        if all(isinstance(item, (str, bool, int, float)) for item in value):
            return ", ".join(str(item) for item in value)
        else:
            try:
                return json.dumps([_prepare_attribute_for_otel(item) for item in value])
            except (TypeError, ValueError):
                return str(value)
    elif isinstance(value, dict):
        try:
            return json.dumps({k: _prepare_attribute_for_otel(v) for k, v in value.items()})
        except (TypeError, ValueError):
            return str(value)
    else:
        try:
            # Try to convert to dict if it's a Pydantic model
            if hasattr(value, "model_dump"):  # Pydantic v2
                return json.dumps(value.model_dump())
            elif hasattr(value, "dict"):  # Pydantic v1
                return json.dumps(value.dict())
            # Otherwise, use default JSON serialization
            return json.dumps(value)
        except (TypeError, ValueError):
            return str(value)


def record_span_attributes(attributes: Dict[str, Any]) -> None:
    """
    Records custom attributes directly on the current span or creates a new span if needed.

    This function will:
    1. Try to get the current active span
    2. If no active span exists, create a new span named after the calling function
    3. Convert attribute values to OpenTelemetry-compatible types
    4. Add the attributes directly to the span
    5. End the span if it was created by this function

    Args:
        attributes: Dictionary of attribute name-value pairs to record as span attributes

    Supported attribute value types:
    - Simple types: str, bool, int, float
    - Complex types (converted automatically):
      - Enum: Converted to string
      - datetime: Converted to ISO format string
      - list: Converted to comma-separated string or JSON
      - dict: Converted to JSON string
      - Pydantic models: Converted to JSON string
      - Other objects: Converted to string representation

    Example:
        record_span_attributes({
            "operation_name": "process_data",
            "user_id": 12345,
            "timestamp": datetime.datetime.now(),
            "is_successful": True,
            "processing_time_ms": 123.45,
            "tags": ["important", "customer"],
            "metadata": {"source": "api", "version": "1.0"}
        })

    Note:
        If the current span doesn't exist, a new span will be created and then
        closed after the attributes are recorded. If you want to add attributes
        to a span that persists, you need to create it yourself using the
        OpenTelemetry API before calling this function.
    """
    # Get the current span
    current_span = trace.get_current_span()

    # Check if the current span context is valid
    if current_span.get_span_context().is_valid and current_span.is_recording():
        # Use existing span
        # Process attributes to ensure they are OpenTelemetry compatible
        for key, value in attributes.items():
            processed_value = _prepare_attribute_for_otel(value)
            if processed_value is not None:  # Only add non-None values
                current_span.set_attribute(key, processed_value)
    else:
        # No valid parent span; create a new span with context manager
        caller_filename, caller_function = _get_caller_metadata()
        tracer = trace.get_tracer(caller_filename)
        span_name = f"{caller_function}.attributes"

        with tracer.start_as_current_span(span_name) as record_span:
            # Process attributes to ensure they are OpenTelemetry compatible
            for key, value in attributes.items():
                processed_value = _prepare_attribute_for_otel(value)
                if processed_value is not None:  # Only add non-None values
                    record_span.set_attribute(key, processed_value)


def start_trace(sessionid=None, userid=None, root_span_name="root", trace_name=None, attributes=None):
    """
    Decorator to create a new trace with given parameters.
    Creates a completely new context so OpenTelemetry will start a new trace.

    Args:
        sessionid: Session ID to add as span attribute
        userid: User ID to add as span attribute
        root_span_name: Name for the root span, defaults to "root"
        attributes: Additional attributes to add to the span (optional dict)
    """
    def decorator(wrapped):
        @wraps(wrapped)
        def wrapper(*args, **kwargs):
            # Get a tracer
            caller_filename = inspect.getmodule(wrapped).__name__
            tracer = trace.get_tracer(caller_filename)

            # Create a new empty context
            empty_context = context.Context()

            # Attach the empty context to start a new trace
            token = context.attach(empty_context)

            try:
                # Start a new span which will be a root span since we're using an empty context
                with tracer.start_as_current_span(root_span_name) as span:
                    # Set the session and user attributes
                    span.set_attribute("session.id", _prepare_attribute_for_otel(sessionid))
                    span.set_attribute("user.id", _prepare_attribute_for_otel(userid))
                    span.set_attribute("trace.name", _prepare_attribute_for_otel(trace_name))
                    # Add any additional attributes
                    if attributes:
                        for key, value in attributes.items():
                            processed_value = _prepare_attribute_for_otel(value)
                            if processed_value is not None:
                                span.set_attribute(key, processed_value)

                    # Execute the wrapped function
                    try:
                        result = wrapped(*args, **kwargs)
                        return result
                    except Exception as e:
                        # Record the exception in the span
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise
            finally:
                # Restore the original context
                context.detach(token)

        return wrapper

    return decorator


def get_current_trace_id() -> Optional[str]:
    """
    Returns the current trace ID as a hex string if available.

    Returns:
        Optional[str]: The current trace ID as a hexadecimal string, or None if no active trace.
    """
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()

    if not span_context.is_valid:
        return None

    # Convert the trace ID to a hexadecimal string
    # trace_id is stored as an integer internally
    trace_id_hex = format(span_context.trace_id, '032x')

    return trace_id_hex
