import unittest
import logging
import uuid

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from agent_analytics_common.interfaces.issues import IssueLevel
from agent_analytics.instrumentation.traceloop.sdk.tracing.opentelemetry_instrumentation_logger import (
    LoggerInstrumentation,
)


class TestLoggerInstrumentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up OpenTelemetry tracing
        cls.exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(cls.exporter)
        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        # Create and instrument the logger
        cls.instrumentor = LoggerInstrumentation()
        cls.instrumentor.instrument()

        # Set up a logger for testing
        cls.logger = logging.getLogger("test_logger")
        cls.logger.setLevel(logging.DEBUG)
        cls.logger.propagate = False
        # Ensure the logger has a handler to avoid "No handlers found" warnings
        handler = logging.StreamHandler()
        cls.logger.addHandler(handler)

    @classmethod
    def tearDownClass(cls):
        # Clean up instrumentation
        cls.instrumentor.uninstrument()

    def setUp(self):
        # Clear the exporter before each test
        self.exporter.clear()

    def generate_short_uuid(self):
        return str(uuid.uuid4())[:8]

    def test_warning_creates_issue(self):
        # Create a span to capture the events
        # tracer = trace.get_tracer(__name__)
        # with tracer.start_as_current_span("test_warning_creates_issue"):
        #     # Log a warning message
        self.logger.warning("This is a test warning")

        # Check that the issue was captured
        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events

        print(main_span.name)
        # Find the issue event
        issue_event = None
        for event in events:
            if event.name.endswith(".issue"):
                issue_event = event
                break

        self.assertIsNotNone(issue_event, "No issue event found in the span")
        attributes = issue_event.attributes

        # Verify the issue attributes
        self.assertEqual(attributes.get("level"), str(IssueLevel.WARNING))
        self.assertEqual(attributes.get("description"), "This is a test warning")
        self.assertTrue(attributes.get("name").startswith("WARNING from test_logger"))

    def test_error_creates_issue(self):
        # Create a span to capture the events
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_error_creates_issue"):
            # Log an error message
            self.logger.error("This is a test error")

        # Check that the issue was captured
        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events

        # Find the issue event
        issue_event = None
        for event in events:
            if event.name.endswith(".issue"):
                issue_event = event
                break

        self.assertIsNotNone(issue_event, "No issue event found in the span")
        attributes = issue_event.attributes

        # Verify the issue attributes
        self.assertEqual(attributes.get("level"), str(IssueLevel.ERROR))
        self.assertEqual(attributes.get("description"), "This is a test error")

    def test_exception_creates_issue(self):
        # Create a span to capture the events
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_exception_creates_issue"):
            try:
                # Raise an exception
                raise ValueError("Test exception")
            except Exception:
                # Log the exception
                self.logger.exception("An error occurred")

        # Check that the issue was captured
        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events

        # Find the issue event
        issue_event = None
        for event in events:
            if event.name.endswith(".issue"):
                issue_event = event
                break

        self.assertIsNotNone(issue_event, "No issue event found in the span")
        attributes = issue_event.attributes

        # Verify the issue attributes
        self.assertEqual(attributes.get("level"), str(IssueLevel.ERROR))
        self.assertEqual(attributes.get("description"), "An error occurred")

        # Check that the effect contains the exception info
        effect_attr = attributes.get("effect")
        self.assertIsNotNone(effect_attr)
        self.assertIn("ValueError: Test exception", effect_attr)

    def test_info_doesnt_create_issue(self):
        # Create a span to capture the events
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_info_doesnt_create_issue"):
            # Log an info message
            self.logger.info("This is an info message")

        # Check that no issue was captured
        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events

        # Verify no issue events
        issue_events = [event for event in events if event.name.endswith(".issue")]
        self.assertEqual(len(issue_events), 0, "Expected no issue events for INFO level")


if __name__ == "__main__":
    unittest.main()
