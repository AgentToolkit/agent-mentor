import unittest
import json
from datetime import datetime
from enum import Enum

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Import your start_trace decorator - adjust the import path as needed
from agent_analytics.instrumentation.utils.tracing_utils import start_trace


# Test classes for complex attribute testing
class TestEnum(Enum):
    VALUE1 = "value1"
    VALUE2 = "value2"


class TestPydanticLike:
    def model_dump(self):
        return {"field1": "value1", "field2": 123}


class TestStartTraceDecorator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up OpenTelemetry for testing
        cls.exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(cls.exporter)
        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

    def setUp(self):
        # Clear spans before each test
        self.exporter.clear()

    def test_basic_trace_creation(self):
        # Define test function with the decorator
        @start_trace(sessionid="test-session", userid="test-user")
        def test_function():
            return "test result"

        # Call the function
        result = test_function()

        # Verify function executed correctly
        self.assertEqual(result, "test result")

        # Get spans and verify
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1, "Expected one span to be created")

        span = spans[0]
        # Verify it's a root span (no parent)
        self.assertIsNone(span.parent)
        # Verify span name
        self.assertEqual(span.name, "root")
        # Verify attributes
        self.assertEqual(span.attributes.get("session.id"), "test-session")
        self.assertEqual(span.attributes.get("user.id"), "test-user")

    def test_custom_span_name(self):
        @start_trace(sessionid="test-session", userid="test-user", root_span_name="custom-operation")
        def test_function():
            return "test result"

        test_function()

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].name, "custom-operation")

    def test_complex_attributes(self):
        # Test with various complex attribute types
        test_datetime = datetime.now()
        test_enum = TestEnum.VALUE1
        test_dict = {"key1": "value1", "key2": 123}
        test_list = ["item1", "item2", 123]
        test_pydantic = TestPydanticLike()

        @start_trace(
            sessionid=test_dict,
            userid=test_enum,
            attributes={
                "datetime": test_datetime,
                "enum": test_enum,
                "dict": test_dict,
                "list": test_list,
                "pydantic": test_pydantic
            }
        )
        def test_function():
            return "test result"

        test_function()

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)

        attributes = spans[0].attributes

        # Verify complex attributes were properly formatted
        self.assertEqual(attributes.get("session.id"), json.dumps(test_dict))
        self.assertEqual(attributes.get("user.id"), str(test_enum))
        self.assertEqual(attributes.get("datetime"), test_datetime.isoformat())
        self.assertEqual(attributes.get("enum"), str(test_enum))
        self.assertEqual(attributes.get("dict"), json.dumps(test_dict))
        self.assertEqual(attributes.get("list"), ", ".join(["item1", "item2", "123"]))

        # Verify Pydantic-like object was properly serialized
        pydantic_attr = attributes.get("pydantic")
        self.assertIsNotNone(pydantic_attr)
        # Should be JSON string of the model_dump output
        self.assertEqual(json.loads(pydantic_attr), {"field1": "value1", "field2": 123})

    def test_independence_from_parent_trace(self):
        # First create a parent span
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("parent_span") as parent:
            # Call our decorated function within this span
            @start_trace(sessionid="test-session", userid="test-user")
            def test_function():
                # Get current span and verify it's our new trace, not the parent
                current = trace.get_current_span()
                self.assertNotEqual(current.get_span_context().span_id, parent.get_span_context().span_id)
                return "test result"

            test_function()

        # Should have two spans - parent and our new trace
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 2)

        # Find our decorator's span
        decorator_span = None
        for span in spans:
            if span.name == "root":
                decorator_span = span
                break

        self.assertIsNotNone(decorator_span, "Decorator span not found")
        # Verify it's a root span (no parent)
        self.assertIsNone(decorator_span.parent)

    def test_multiple_independent_traces(self):
        # Create an initial parent span
        tracer = trace.get_tracer(__name__)

        # List to store the trace IDs we observe
        observed_trace_ids = set()

        with tracer.start_as_current_span("parent_span") as parent:
            parent_trace_id = parent.get_span_context().trace_id
            observed_trace_ids.add(parent_trace_id)

            # Add a child to the parent span
            with tracer.start_as_current_span("parent_child_span"):
                # First decorated function - should start a new trace
                @start_trace(sessionid="session-1", userid="user-1")
                def first_trace_function():
                    # Get current span (root of first new trace)
                    current = trace.get_current_span()
                    first_trace_id = current.get_span_context().trace_id

                    # Verify it's a different trace than the parent
                    self.assertNotEqual(first_trace_id, parent_trace_id)
                    observed_trace_ids.add(first_trace_id)

                    # Add a child span to this trace
                    with tracer.start_as_current_span("first_trace_child"):
                        pass

                    return "result-1"

                # Second decorated function - should start another new trace
                @start_trace(sessionid="session-2", userid="user-2")
                def second_trace_function():
                    # Get current span (root of second new trace)
                    current = trace.get_current_span()
                    second_trace_id = current.get_span_context().trace_id

                    # Verify it's a different trace than the parent and first trace
                    self.assertNotEqual(second_trace_id, parent_trace_id)
                    self.assertNotIn(second_trace_id, observed_trace_ids)
                    observed_trace_ids.add(second_trace_id)

                    # Add a child span to this trace
                    with tracer.start_as_current_span("second_trace_child"):
                        pass

                    return "result-2"

                # Third decorated function - should start a third new trace
                @start_trace(sessionid="session-3", userid="user-3")
                def third_trace_function():
                    # Get current span (root of third new trace)
                    current = trace.get_current_span()
                    third_trace_id = current.get_span_context().trace_id

                    # Verify it's a different trace than all previous traces
                    self.assertNotEqual(third_trace_id, parent_trace_id)
                    self.assertNotIn(third_trace_id, observed_trace_ids)
                    observed_trace_ids.add(third_trace_id)

                    # Add a child span to this trace
                    with tracer.start_as_current_span("third_trace_child"):
                        pass

                    return "result-3"

                # Execute all three decorated functions
                result1 = first_trace_function()
                result2 = second_trace_function()
                result3 = third_trace_function()

                # Verify function results
                self.assertEqual(result1, "result-1")
                self.assertEqual(result2, "result-2")
                self.assertEqual(result3, "result-3")

        # Should have 7 spans - 2 from parent trace + 2 each from 3 new traces
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 8)

        # Verify we have 4 unique trace IDs (parent + 3 new traces)
        trace_ids = {span.context.trace_id for span in spans}
        self.assertEqual(len(trace_ids), 4, "Expected 4 unique trace IDs")

        # Group spans by trace ID
        traces = {}
        for span in spans:
            trace_id = span.context.trace_id
            if trace_id not in traces:
                traces[trace_id] = []
            traces[trace_id].append(span)

        # Verify each trace has at least 2 spans
        for trace_id, trace_spans in traces.items():
            self.assertGreaterEqual(len(trace_spans), 2, f"Trace {trace_id} should have at least 2 spans")

        # Find all root spans from the decorator
        decorator_roots = [span for span in spans if span.name == "root" and span.parent is None]
        self.assertEqual(len(decorator_roots), 3, "Expected 3 root spans from the decorator")

        # Verify each root has the correct attributes
        expected_sessions = ["session-1", "session-2", "session-3"]
        expected_users = ["user-1", "user-2", "user-3"]

        # Sort roots by session ID to match with expected values
        decorator_roots.sort(key=lambda span: span.attributes.get("session.id", ""))

        for i, root in enumerate(decorator_roots):
            self.assertEqual(root.attributes.get("session.id"), expected_sessions[i])
            self.assertEqual(root.attributes.get("user.id"), expected_users[i])


if __name__ == "__main__":
    unittest.main()
