import unittest
import json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import StatusCode

from agent_analytics_common.interfaces.action import ActionKind, CommandType
from agent_analytics.instrumentation.reportable import ReportableAction


class TestReportableAction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up OpenTelemetry for testing."""
        cls.exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(cls.exporter)
        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

    def setUp(self):
        """Clear spans before each test."""
        self.exporter.clear()

    def test_basic_action_execution(self):
        """Test basic action execution with automatic lifecycle management."""
        action = ReportableAction(
            name="Test Tool Action",
            kind=ActionKind.TOOL,
            description="A test action for unit testing",
            tags=["test", "unit-test"]
        )

        # Execute action
        with action.span():
            # Simulate some work
            pass

        # Check spans
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1, "Expected one span for the action")

        action_span = spans[0]
        self.assertEqual(action_span.name, "Test Tool Action.manual.action")
        self.assertEqual(action_span.status.status_code, StatusCode.OK)

        # Check attributes
        attrs = action_span.attributes
        self.assertEqual(attrs.get("gen_ai.action.kind"), "tool")
        self.assertEqual(attrs.get("gen_ai.action.description"), "A test action for unit testing")

    def test_action_with_code_info(self):
        """Test action with code information."""
        action = ReportableAction(
            name="Code Action",
            kind=ActionKind.LLM,
            description="Action with code metadata"
        )

        # Set code information
        action.set_code(
            id="test.module:42:function",
            language="python",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            body="def function(query): return process(query)"
        )

        with action.span():
            pass

        spans = self.exporter.get_finished_spans()
        action_span = spans[0]
        attrs = action_span.attributes

        # Check code attributes
        self.assertEqual(attrs.get("gen_ai.action.code.id"), "test.module:42:function")
        self.assertEqual(attrs.get("gen_ai.action.code.language"), "python")
        self.assertIsNotNone(attrs.get("gen_ai.action.code.input_schema"))
        self.assertIsNotNone(attrs.get("gen_ai.action.code.output_schema"))
        self.assertEqual(attrs.get("gen_ai.action.code.body"), "def function(query): return process(query)")

    def test_action_with_guardrails_and_artifacts(self):
        """Test action with guardrails and artifacts."""
        action = ReportableAction(
            name="Guarded Action",
            kind=ActionKind.LLM,
            description="Action with safety checks",
            is_generated=False
        )

        # Add guardrails
        action.add_guardrail("safety.checks:1:no_pii")
        action.add_guardrail("safety.checks:2:content_filter")

        # Add artifacts
        action.add_artifact("artifact-001")
        action.add_artifact("artifact-002")

        with action.span():
            pass

        spans = self.exporter.get_finished_spans()
        action_span = spans[0]
        attrs = action_span.attributes

        # Check guardrail and artifact attributes
        guardrails = json.loads(attrs.get("gen_ai.action.guardrail.code.ids", "[]"))
        self.assertEqual(len(guardrails), 2)
        self.assertIn("safety.checks:1:no_pii", guardrails)

        artifacts = json.loads(attrs.get("gen_ai.action.artifact.ids", "[]"))
        self.assertEqual(len(artifacts), 2)
        self.assertIn("artifact-001", artifacts)

        self.assertFalse(attrs.get("gen_ai.action.is_generated"))

    def test_command_action(self):
        """Test action with command lifecycle."""
        action = ReportableAction(
            name="Load Module",
            kind=ActionKind.OTHER
        )

        # Set command
        action.set_command(
            type=CommandType.LOAD,
            code_id="module.loader:1:load_action"
        )

        with action.span():
            pass

        spans = self.exporter.get_finished_spans()
        action_span = spans[0]
        attrs = action_span.attributes

        # Check command attributes
        self.assertEqual(attrs.get("gen_ai.action.command.type"), "load")
        self.assertEqual(attrs.get("gen_ai.action.command.code.id"), "module.loader:1:load_action")

    def test_action_exception_handling(self):
        """Test action exception handling."""
        action = ReportableAction(
            name="Failing Action",
            kind=ActionKind.ML,
            description="Action that will fail"
        )

        # Execute action that will fail
        with self.assertRaises(RuntimeError):
            with action.span():
                raise RuntimeError("Model inference failed")

        # Check spans
        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        action_span = None
        for span in spans:
            if "Failing Action" in span.name:
                action_span = span
                break

        self.assertIsNotNone(action_span, "Action span not found")
        self.assertEqual(action_span.status.status_code, StatusCode.ERROR)
        self.assertIn("Model inference failed", action_span.status.description)

        # Check that exception was recorded
        exception_found = False
        for event in action_span.events:
            if event.name == "exception":
                exception_found = True
                break
        self.assertTrue(exception_found, "Exception event not found in span")

    def test_different_action_kinds(self):
        """Test different action kinds."""
        action_kinds = [
            (ActionKind.TOOL, "tool"),
            (ActionKind.LLM, "llm"),
            (ActionKind.ML, "ml"),
            (ActionKind.VECTOR_DB, "vector_db"),
            (ActionKind.GUARDRAIL, "guardrail"),
            (ActionKind.HUMAN, "human"),
            (ActionKind.OTHER, "other")
        ]

        for kind_enum, kind_str in action_kinds:
            self.exporter.clear()

            action = ReportableAction(
                name=f"Test {kind_str}",
                kind=kind_enum,
                description=f"Testing {kind_str} action"
            )

            with action.span():
                pass

            spans = self.exporter.get_finished_spans()
            self.assertEqual(len(spans), 1)
            attrs = spans[0].attributes
            self.assertEqual(attrs.get("gen_ai.action.kind"), kind_str)

    def test_manual_reporting_with_new_span(self):
        """Test manual action reporting creates a new span when called standalone."""
        action = ReportableAction(
            name="Manual Action",
            kind=ActionKind.VECTOR_DB
        )

        # Report creates a new span when called standalone
        action.report(use_current_span=False)

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1, "Expected report() to create a new span")
        self.assertEqual(spans[0].name, "Manual Action.manual.action")

    def test_manual_reporting_with_existing_span(self):
        """Test manual action reporting uses existing span when requested."""
        action = ReportableAction(
            name="Manual Action",
            kind=ActionKind.VECTOR_DB
        )

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("manual_operation"):
            # Report action state (uses current span)
            action.report(use_current_span=True)

            # Update and report again
            action.add_artifact("search-results-001")
            action.update(use_current_span=True)

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1, "Expected only the manual_operation span")

        manual_span = spans[0]
        self.assertEqual(manual_span.name, "manual_operation")
        attrs = manual_span.attributes

        # Should have action attributes reported to the manual_operation span
        self.assertEqual(attrs.get("gen_ai.action.kind"), "vector_db")
        self.assertEqual(attrs.get("gen_ai.action.name"), "Manual Action")
        artifacts = json.loads(attrs.get("gen_ai.action.artifact.ids", "[]"))
        self.assertIn("search-results-001", artifacts)

    def test_action_with_no_name(self):
        """Test action span naming when no name is provided."""
        action = ReportableAction(
            kind=ActionKind.TOOL,
            description="This is a long description"
        )

        with action.span():
            pass

        spans = self.exporter.get_finished_spans()
        action_span = spans[0]

        # When no name is provided, should use default "manual.action"
        self.assertEqual(action_span.name, "manual.action")

        # Description should still be in attributes
        attrs = action_span.attributes
        self.assertEqual(attrs.get("gen_ai.action.description"), "This is a long description")

    def test_automatic_code_id_generation(self):
        """Test that code_id is automatically generated when not provided."""
        action = ReportableAction(
            name="Auto Code ID",
            kind=ActionKind.TOOL,
            description="Action with auto-generated code_id"
        )

        # Should have auto-generated code_id
        self.assertIsNotNone(action.code, "Code object should be created automatically")
        self.assertIsNotNone(action.code.id, "Code ID should be auto-generated")

        # Code ID should contain this test function info
        self.assertIn("test_reportable_action.py", action.code.id)
        self.assertIn("test_automatic_code_id_generation", action.code.id)

        with action.span():
            pass

        # Verify it's in the span
        spans = self.exporter.get_finished_spans()
        action_span = spans[0]
        attrs = action_span.attributes
        self.assertIsNotNone(attrs.get("gen_ai.action.code.id"))
        self.assertIn("test_automatic_code_id_generation", attrs.get("gen_ai.action.code.id"))

    def test_explicit_code_id_preserved(self):
        """Test that explicit code_id is preserved and not overwritten."""
        from agent_analytics_common.interfaces.action import ActionCode

        explicit_code_id = "my.module:123:my_function"
        action = ReportableAction(
            name="Explicit Code ID",
            kind=ActionKind.LLM,
            code=ActionCode(id=explicit_code_id)
        )

        # Should preserve the explicit code_id
        self.assertEqual(action.code.id, explicit_code_id)

        with action.span():
            pass

        # Verify in span
        spans = self.exporter.get_finished_spans()
        action_span = spans[0]
        attrs = action_span.attributes
        self.assertEqual(attrs.get("gen_ai.action.code.id"), explicit_code_id)

    def test_update_code_id(self):
        """Test updating code_id after action creation."""
        action = ReportableAction(
            name="Update Code ID",
            kind=ActionKind.TOOL
        )

        # Get initial auto-generated code_id
        initial_code_id = action.code.id
        self.assertIsNotNone(initial_code_id)

        # Update with explicit code_id
        new_code_id = "updated.module:456:updated_function"
        action.update_code_id(new_code_id)
        self.assertEqual(action.code.id, new_code_id)

        with action.span():
            pass

        # Verify updated code_id in span
        spans = self.exporter.get_finished_spans()
        action_span = spans[0]
        attrs = action_span.attributes
        self.assertEqual(attrs.get("gen_ai.action.code.id"), new_code_id)

    def test_code_id_from_different_context(self):
        """Test code_id generation from different calling contexts."""

        def helper_function():
            """Helper function to test code_id generation."""
            return ReportableAction(
                name="From Helper",
                kind=ActionKind.TOOL
            )

        action = helper_function()

        # Should contain helper function info
        self.assertIsNotNone(action.code)
        self.assertIsNotNone(action.code.id)
        self.assertIn("helper_function", action.code.id)

    def test_generate_class_name_element_id_prefix(self):
        """Test that generate_class_name is used for element_id prefix."""
        action = ReportableAction(kind=ActionKind.TOOL)

        # Verify element_id has correct prefix from generate_class_name
        self.assertTrue(action.element_id.startswith("Action-"))

        # Verify in span attributes
        with action.span():
            pass

        spans = self.exporter.get_finished_spans()
        action_span = spans[0]
        attrs = action_span.attributes

        # Check element_id in attributes starts with correct prefix
        element_id = attrs.get("gen_ai.action.id")
        self.assertIsNotNone(element_id)
        self.assertTrue(element_id.startswith("Action-"))


if __name__ == "__main__":
    unittest.main()
