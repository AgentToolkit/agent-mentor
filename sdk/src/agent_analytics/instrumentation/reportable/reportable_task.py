# reportable_task.py

from typing import Callable, Any, Optional
from datetime import datetime
from contextlib import contextmanager
from functools import wraps
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Span

from agent_analytics_common.interfaces.task import Task, TaskStatus, TaskState, TaskKind
from agent_analytics_common.interfaces.issues import IssueLevel
from agent_analytics.instrumentation.utils import AIEventRecorder
from .reportable_element import ReportableElement


class ReportableTask(Task, ReportableElement):
    """
    A Task that can report its state and attributes to OpenTelemetry spans.
    Combines Task functionality with OpenTelemetry reporting capabilities.
    """

    @classmethod
    def generate_class_name(cls) -> str:
        """
        Generate the name for this element type.

        This method is used to generate the prefix for the element_id
        (e.g., "Task-{uuid}") and for span naming.

        Returns:
            "Task" - the element type name
        """
        return "Task"

    def _report_to_span(self, span: Span) -> None:
        """
        Report task attributes to the provided span.
        Internal method used by both report() and span() methods.

        Args:
            span: The OpenTelemetry span to report to
        """
        # Get all OTEL attributes from the task using existing method
        otel_attributes = self.to_otel_attributes()

        # Prepare all attribute values for OTEL
        prepared_attributes = {}
        for key, value in otel_attributes.items():
            prepared_value = self.prepare_attribute_value(value)
            if prepared_value is not None:
                prepared_attributes[key] = prepared_value

        # Set all attributes on the span
        span.set_attributes(prepared_attributes)

        # Set span status if task has ended
        if self.state == TaskState.ENDED and self.status:
            self._set_span_status(span)

    def report(self) -> None:
        """
        Report this task to OpenTelemetry span attributes.
        Always creates a new span and reports attributes within it.
        Uses the existing to_otel_attributes() method to get all attributes.
        """
        span_name = self._get_span_name()
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span(span_name) as span:
            self._report_to_span(span)

    def _get_span_name(self) -> str:
        span_name = f"{self.name}.manual.task" if self.name else "manual.task"
        return span_name

    def _set_span_status(self, span: Span) -> None:
        """Set OpenTelemetry span status based on task status."""
        if self.status == TaskStatus.SUCCESS:
            span.set_status(Status(StatusCode.OK))  # No description for OK status
        elif self.status == TaskStatus.FAILURE:
            error_message = "Task failed"
            span.set_status(Status(StatusCode.ERROR, error_message))
        elif self.status == TaskStatus.CANCELLED:
            span.set_status(Status(StatusCode.ERROR, "Task was cancelled"))
        elif self.status == TaskStatus.TIMEOUT:
            span.set_status(Status(StatusCode.ERROR, "Task timed out"))
        elif self.status == TaskStatus.UNKNOWN:
            span.set_status(Status(StatusCode.UNSET))

    @contextmanager
    def span(self):
        """
        Context manager for task execution with automatic lifecycle management and OpenTelemetry reporting.
        Always creates a new span for tasks (they are significant units of work).

        Example:
            task = ReportableTask(name="Process Data", kind=TaskKind.ACTION)
            with task.span():
                # Task automatically starts, reports, and manages lifecycle
                task.output = process_data()
                # Status is automatically set to SUCCESS if no exception
        """
        # Set start time and lifecycle state
        self.start_time = datetime.now()
        self.state = TaskState.IN_PROGRESS

        # Always create a new span for tasks
        span_name = self._get_span_name()
        tracer = trace.get_tracer(__name__)
        span_ctx = tracer.start_as_current_span(span_name)
        span = span_ctx.__enter__()

        # Report initial state directly to the span (no child span)
        self._report_to_span(span)

        try:
            yield span
            # If no explicit status was set, assume success
            if not self.status:
                self.status = TaskStatus.SUCCESS
                self.state = TaskState.ENDED
        except Exception as e:
            # Capture exception in task
            self.status = TaskStatus.FAILURE
            self.state = TaskState.ENDED

            # Record exception in span
            span.record_exception(e)

            # Create and record an issue using AIEventRecorder
            AIEventRecorder.record_issue(
                name=f"Task Error: {self.name or self.element_id}",
                description=str(e),
                level=IssueLevel.ERROR,
                related_to_ids=[self.element_id],
                tags=self.tags,
                attributes={
                    "task_name": self.name,
                    "task_kind": self.kind.value if self.kind else None,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e)
                }
            )

            raise
        finally:
            # Always set end time
            self.end_time = datetime.now()
            # Ensure state is ENDED
            if self.state != TaskState.ENDED:
                self.state = TaskState.ENDED
            # Report final state directly to the span (no child span)
            self._report_to_span(span)

            # Clean up span context
            span_ctx.__exit__(None, None, None)

    def update(self, use_current_span: bool = False) -> None:
        """
        Update the current span with the latest task state.
        Useful for reporting progress during long-running tasks.
        """
        self.report(use_current_span=use_current_span)

    @staticmethod
    def as_task(
        name: Optional[str] = None,
        kind: Optional[TaskKind] = None,
        tags: Optional[list] = None,
        **task_kwargs
    ):
        """
        Decorator to automatically create and manage a ReportableTask for a function.
        Always creates a new span for the task.

        Args:
            name: Task name (defaults to function name)
            kind: Task kind (defaults to ACTION)
            tags: Task tags
            **task_kwargs: Additional kwargs passed to ReportableTask constructor

        Example:
            @ReportableTask.as_task(name="Process Data", kind=TaskKind.ACTION)
            def process_data(input_data):
                return transform(input_data)

            # Or with dynamic task creation
            @ReportableTask.as_task()
            def process_data(input_data):
                return transform(input_data)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                # Create task with provided or default values
                task_name = name or func.__name__
                task_kind = kind or TaskKind.ACTION
                task_tags = tags or []

                # Create the task
                task = ReportableTask(
                    name=task_name,
                    kind=task_kind,
                    tags=task_tags,
                    **task_kwargs
                )

                # Set input if provided
                if args or kwargs:
                    task.input = {
                        "args": args,
                        "kwargs": kwargs
                    }

                # Execute function within task span
                with task.span():
                    try:
                        result = func(*args, **kwargs)
                        # Set output on success
                        task.output = result
                        return result
                    except Exception as e:
                        # Exception handling is done by the context manager
                        raise e

            return wrapper
        return decorator
