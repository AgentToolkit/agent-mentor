# reportable_action.py

from datetime import datetime
from contextlib import contextmanager
from typing import Any, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Span

from agent_analytics_common.interfaces.action import Action, ActionCode
from agent_analytics_common.interfaces.issues import IssueLevel
from agent_analytics.instrumentation.utils import AIEventRecorder
from .reportable_element import ReportableElement


class ReportableAction(Action, ReportableElement):
    """
    An Action that can report its state and attributes to OpenTelemetry spans.
    Combines Action functionality with OpenTelemetry reporting capabilities.

    The action automatically generates a code_id based on the calling function
    if not explicitly provided during initialization.
    """

    @classmethod
    def generate_class_name(cls) -> str:
        """
        Generate the name for this element type.

        This method is used to generate the prefix for the element_id
        (e.g., "Action-{uuid}") and for span naming.

        Returns:
            "Action" - the element type name
        """
        return "Action"

    def __init__(self, **data: Any):
        """
        Initialize a ReportableAction with automatic code_id generation.

        If no code_id is provided (either via code.id or code parameter),
        the action will automatically generate one by inspecting the call stack
        to identify the calling function.

        Args:
            **data: All keyword arguments for Action/Element initialization
        """
        from agent_analytics.instrumentation.utils.common import get_caller_code_id

        # Check if code_id is already provided
        has_code_id = False
        if 'code' in data and data['code'] is not None:
            if isinstance(data['code'], ActionCode):
                has_code_id = data['code'].id is not None
            elif isinstance(data['code'], dict):
                has_code_id = data['code'].get('id') is not None

        # Call parent constructor
        super().__init__(**data)

        # Auto-generate code_id if not provided
        if not has_code_id:
            auto_code_id = get_caller_code_id(skip_frames=0)
            if self.code is None:
                self.code = ActionCode(id=auto_code_id)
            else:
                self.code.id = auto_code_id

    def _report_to_span(self, span: Span) -> None:
        """
        Report action attributes to the provided span.
        Internal method used by both report() and span() methods.

        Args:
            span: The OpenTelemetry span to report to
        """
        # Get all OTEL attributes from the action using existing method
        otel_attributes = self.to_otel_attributes()

        # Prepare all attribute values for OTEL
        prepared_attributes = {}
        for key, value in otel_attributes.items():
            prepared_value = self.prepare_attribute_value(value)
            if prepared_value is not None:
                prepared_attributes[key] = prepared_value

        # Set all attributes on the span
        span.set_attributes(prepared_attributes)

    def report(self, use_current_span: bool = False) -> None:
        """
        Report this action to OpenTelemetry span attributes.

        Args:
            use_current_span: If True, reports to the current active span if one exists.
                            If False, always creates a new span.

        Uses the existing to_otel_attributes() method to get all attributes.
        """
        # Try to get the current span if requested
        current_span = trace.get_current_span() if use_current_span else None

        # Check if we have a valid recording span
        if current_span and current_span.is_recording():
            # Report to the current span
            self._report_to_span(current_span)
        else:
            # Create a new span
            span_name = self._get_span_name()
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(span_name) as span:
                self._report_to_span(span)

    def _get_span_name(self) -> str:
        """Generate low-cardinality span name following OTEL conventions."""
        span_name = f"{self.name}.manual.action" if self.name else "manual.action"
        return span_name

    @contextmanager
    def span(self):
        """
        Context manager for action execution with automatic lifecycle management and OpenTelemetry reporting.
        Always creates a new span for actions.

        Example:
            action = ReportableAction(
                name="Search Web",
                kind=ActionKind.TOOL,
                description="Search the web for information"
            )
            with action.span():
                # Action automatically executes and reports
                action.output = search_web(action.input)
        """
        # Set start time
        self.start_time = datetime.now()

        # Always create a new span for actions
        span_name = self._get_span_name()
        tracer = trace.get_tracer(__name__)
        span_ctx = tracer.start_as_current_span(span_name)
        span = span_ctx.__enter__()

        # Add span attributes for action kind
        span.set_attribute("gen_ai.action.kind", self.kind.value)

        # Report initial state directly to the span (no child span)
        self._report_to_span(span)

        try:
            yield span
            # Action completed successfully
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            # Record exception in span
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, f"Action failed: {str(e)}"))

            # Create and record an issue using AIEventRecorder
            AIEventRecorder.record_issue(
                name=f"Action Error: {self.name or self.description or self.element_id}",
                description=str(e),
                level=IssueLevel.ERROR,
                related_to_ids=[self.element_id],
                tags=self.tags,
                attributes={
                    "action_name": self.name,
                    "action_kind": self.kind.value,
                    "action_description": self.description,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e)
                }
            )

            raise
        finally:
            # Always set end time
            self.end_time = datetime.now()
            # Report final state directly to the span (no child span)
            self._report_to_span(span)

            # Clean up span context
            span_ctx.__exit__(None, None, None)

    def update(self, use_current_span: bool = False) -> None:
        """
        Update the current span with the latest action state.
        Useful for reporting progress during long-running actions.
        """
        self.report(use_current_span=use_current_span)

    def update_code_id(self, code_id: Optional[str] = None) -> None:
        """
        Update the action's code_id.

        Args:
            code_id: The new code_id to set. If None, regenerates the code_id
                    based on the current calling function.
        """
        from agent_analytics.instrumentation.utils.common import get_caller_code_id

        if code_id is None:
            # Auto-generate from caller
            code_id = get_caller_code_id(skip_frames=0)

        # Ensure code object exists
        if self.code is None:
            self.code = ActionCode(id=code_id)
        else:
            self.code.id = code_id
