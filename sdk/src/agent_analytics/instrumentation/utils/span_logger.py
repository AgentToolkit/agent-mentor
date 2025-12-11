from typing import Dict, Any, Optional, Union
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from enum import Enum
import json
import logging


class SpanLogger:
    AGENT_ANALYTICS_TAG = "agent-analaytics-log"

    class LogLevel(Enum):
        DEBUG = logging.DEBUG
        INFO = logging.INFO
        WARNING = logging.WARNING
        ERROR = logging.ERROR
        CRITICAL = logging.CRITICAL

    @classmethod
    def log(cls, level: Optional['SpanLogger.LogLevel'] = None, data: Union[str, Dict[str, Any]] = "") -> None:
        """
        Logs an event within the current tracing span or creates a new span if none exists.

        Args:
            level (LogLevel, optional): The log level (e.g., LogLevel.DEBUG, LogLevel.INFO).
                                        Defaults to LogLevel.INFO.
            data (Union[str, Dict[str, Any]]): The data to log as event attributes.
                                               Can be a string message or a dictionary of attributes.
        """

        # Set the default log level if not provided
        if level is None:
            level = cls.LogLevel.INFO

        # Validate the log level
        if not isinstance(level, cls.LogLevel):
            # Don't stop user flow
            print(f"WARNING: invalid log level: {level}. Choose from {[e.name for e in cls.LogLevel]}.")
            return

        # Get the current span
        current_span = trace.get_current_span()

        # Flag to indicate new span creation
        new_span = False

        # Check if the current span context is valid
        if current_span.get_span_context().is_valid and current_span.is_recording():
            # Use the existing span for recording
            record_span = current_span
        else:
            # No valid parent span; create a new span
            # TODO: Fix import _get_caller_metadata()
            caller_filename, caller_function = _get_caller_metadata()  # noqa: F821
            tracer = trace.get_tracer(caller_filename)
            span_name = f"{caller_function}.log"
            record_span = tracer.start_span(span_name, kind=SpanKind.INTERNAL)
            new_span = True

        # Prepare event attributes based on data type
        if isinstance(data, str):
            attributes = {
                "log.level": level.name,
                "tag": cls.AGENT_ANALYTICS_TAG,
                "message": data
            }
        elif isinstance(data, dict):
            attributes = {
                "log.level": level.name,
                "tag": cls.AGENT_ANALYTICS_TAG,
                "data": json.dumps(data)
            }
        else:
            print("WARNING: data must be either a string or a dictionary.")

        # Add an event to the span with the specified log level and data
        record_span.add_event(
            name=f"{level.name}",
            attributes=attributes
        )

        # End the span if it was newly created
        if new_span:
            record_span.end()

    @classmethod
    def info(cls, data: Union[str, Dict[str, Any]] = "") -> None:
        cls.log(level=cls.LogLevel.INFO, data=data)

    @classmethod
    def debug(cls, data: Union[str, Dict[str, Any]] = "") -> None:
        cls.log(level=cls.LogLevel.DEBUG, data=data)

    @classmethod
    def warning(cls, data: Union[str, Dict[str, Any]] = "") -> None:
        cls.log(level=cls.LogLevel.WARNING, data=data)

    @classmethod
    def error(cls, data: Union[str, Dict[str, Any]] = "") -> None:
        cls.log(level=cls.LogLevel.ERROR, data=data)

    @classmethod
    def critical(cls, data: Union[str, Dict[str, Any]] = "") -> None:
        cls.log(level=cls.LogLevel.CRITICAL, data=data)
