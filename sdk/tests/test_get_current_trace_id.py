import unittest

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Import the utility function
from agent_analytics.instrumentation.utils import get_current_trace_id


class TestGetCurrentTraceId(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure the OpenTelemetry test environment
        cls.exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(cls.exporter)
        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

    def setUp(self):
        self.exporter.clear()

    def test_get_current_trace_id_no_span(self):
        """Test that get_current_trace_id returns None when there is no active span."""
        trace_id = get_current_trace_id()
        self.assertIsNone(trace_id)

    def test_get_current_trace_id_with_span(self):
        """Test that get_current_trace_id returns a valid trace ID when there is an active span."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_span"):
            trace_id = get_current_trace_id()

            # Verify that we got a valid hex string of the correct length
            self.assertIsNotNone(trace_id)
            self.assertEqual(len(trace_id), 32)  # 128-bit trace ID = 32 hex chars
            # Check that it contains only hex characters
            self.assertTrue(all(c in "0123456789abcdef" for c in trace_id))

    def test_get_nested_spans_same_trace_id(self):
        """Test that nested spans have the same trace ID."""
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("parent_span"):
            parent_id = get_current_trace_id()

            with tracer.start_as_current_span("child_span"):
                child_id = get_current_trace_id()

                # Trace ID should be the same for parent and child spans
                self.assertEqual(parent_id, child_id)


if __name__ == "__main__":
    unittest.main()
