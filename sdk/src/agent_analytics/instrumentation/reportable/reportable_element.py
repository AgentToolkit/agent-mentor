# reportable_element.py

import json
from typing import Any
from enum import Enum
from datetime import datetime
from contextlib import contextmanager
from abc import abstractmethod
from opentelemetry import trace

from agent_analytics_common.interfaces.elements import Element


class ReportableElement(Element):
    """Base class for elements that can be reported to OpenTelemetry spans."""

    @classmethod
    @abstractmethod
    def generate_class_name(cls) -> str:
        """
        Generate the name for this element type.

        Must be implemented by subclasses to return the element type name
        (e.g., "Action", "Task", "Agent", etc.).

        This method is used to:
        - Generate the prefix for element_id (e.g., "Action-{uuid}")
        - Generate span names (e.g., "action.{element_id}")

        Returns:
            The element type name as a string.

        Example:
            class ReportableAction(ReportableElement):
                @classmethod
                def generate_class_name(cls) -> str:
                    return "Action"
        """
        raise NotImplementedError("Subclasses must implement generate_class_name()")

    def prepare_attribute_value(self, value: Any) -> Any:
        """Prepare a value for OpenTelemetry attributes."""
        if value is None:
            return None
        elif isinstance(value, (str, bool, int, float)):
            return value
        elif isinstance(value, Enum):
            return str(value.value)
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, (list, dict)):
            return json.dumps(value)
        elif hasattr(value, 'model_dump'):
            return json.dumps(value.model_dump())
        else:
            return str(value)

    def _get_span_name(self) -> str:
        """
        Get span name for this element.
        Should be overridden by subclasses to provide specific naming.
        """
        element_type = self.generate_class_name().lower()
        return f"{self.name or element_type}.{self.element_id}"

    def report(self) -> None:
        """
        Report this element to OpenTelemetry. To be implemented by subclasses.
        Always creates a new span and reports attributes within it.
        """
        raise NotImplementedError("Subclasses must implement report()")

    @contextmanager
    def span(self):
        """
        Context manager for creating a span for this element.
        Always creates a new span and reports on both entry and exit to capture initial and final state.
        """
        span_name = self._get_span_name()
        tracer = trace.get_tracer(__name__)
        span_ctx = tracer.start_as_current_span(span_name)
        span = span_ctx.__enter__()

        # Report initial state
        self.report()

        try:
            yield span
        finally:
            # Report final state
            self.report()
            span_ctx.__exit__(None, None, None)
