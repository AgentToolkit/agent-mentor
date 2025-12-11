import logging
from datetime import datetime, timezone
from typing import Collection

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper

from agent_analytics_common.interfaces.issues import Issue, IssueLevel
from agent_analytics.instrumentation.utils import AIEventTracer
from .version import __version__


class LoggerInstrumentation(BaseInstrumentor):
    """
    Instrumentation for Python's standard logging module.

    This instrumentor patches the Logger.handle method to intercept log records
    before they are processed by handlers. When a log record with level >= WARNING
    is detected, it creates an Issue object and captures it using AIEventTracer.
    """

    def instrumentation_dependencies(self) -> Collection[str]:
        return []

    def _instrument(self, **kwargs):
        """Instrument the logging module."""
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        # Save original handle method
        self._original_handle = logging.Logger.handle

        # Patch the Logger.handle method
        wrap_function_wrapper(
            "logging",
            "Logger.handle",
            self._logger_handle_wrapper(tracer)
        )

    def _uninstrument(self, **kwargs):
        """Restore the original Logger.handle method."""
        if hasattr(self, "_original_handle"):
            logging.Logger.handle = self._original_handle

    def _logger_handle_wrapper(self, tracer):
        """Wrapper for Logger.handle method that creates Issues for warnings and errors."""

        def wrapper(wrapped, instance, args, kwargs):
            """
            Wrapper function for Logger.handle

            Args:
                wrapped: Original handle method
                instance: Logger instance
                args: Arguments to handle method
                kwargs: Keyword arguments to handle method
            """
            # The first argument to Logger.handle is the LogRecord
            record = args[0]

            # Process log records with level >= WARNING
            if record.levelno >= logging.WARNING:
                # Map Python logging levels to IssueLevel
                level_map = {
                    logging.CRITICAL: IssueLevel.CRITICAL,
                    logging.ERROR: IssueLevel.ERROR,
                    logging.WARNING: IssueLevel.WARNING,
                }

                issue_level = level_map.get(record.levelno, IssueLevel.WARNING)

                if record.exc_info:
                    # If there's an exception, use it as the effect
                    exc_type, exc_value, _ = record.exc_info
                    effect = [f"{exc_type.__name__}: {str(exc_value)}"]
                else:
                    # Default effect is the log message
                    effect = [record.getMessage()]

                # Create an Issue from the log record
                issue = Issue(
                    name=f"{record.levelname} from {record.name}",
                    description=record.getMessage(),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    level=issue_level,
                    effect=effect,
                )

                # Add any extra attributes as issue attributes
                if hasattr(record, "__dict__"):
                    if issue.attributes is None:
                        issue.attributes = {}

                    for key, value in record.__dict__.items():
                        # Skip standard LogRecord attributes and ones we've already processed
                        if key not in [
                            "name", "msg", "args", "levelname", "levelno",
                            "pathname", "filename", "module", "exc_info",
                            "exc_text", "lineno", "funcName", "created",
                            "msecs", "relativeCreated", "thread", "threadName",
                            "processName", "process", "related_to_ids", "effect"
                        ]:
                            issue.attributes[key] = value

                # Capture the issue using AIEventTracer
                AIEventTracer.capture_issue(issue)

            # Call the original handle method
            return wrapped(*args, **kwargs)

        return wrapper
