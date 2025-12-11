import unittest
import json
from datetime import datetime

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import StatusCode

from agent_analytics_common.interfaces.task import TaskKind, TaskStatus, TaskState, TaskInput, TaskOutput
from agent_analytics.instrumentation.reportable import ReportableTask


class TestReportableTask(unittest.TestCase):

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

    def test_basic_task_execution(self):
        """Test basic task execution with automatic lifecycle management."""
        task = ReportableTask(
            name="Test Task",
            description="A test task for unit testing",
            kind=TaskKind.ACTION,
            tags=["test", "unit-test"]
        )

        # Execute task
        with task.span():
            # Simulate some work
            task.output = TaskOutput(
                data_values=["Result 1", "Result 2"],
                data_ranking=[0.9, 0.8],
                metadata={"processed": True}
            )

        # Verify task state
        self.assertEqual(task.status, TaskStatus.SUCCESS)
        self.assertEqual(task.state, TaskState.ENDED)
        self.assertIsNotNone(task.start_time)
        self.assertIsNotNone(task.end_time)
        self.assertGreater(task.end_time, task.start_time)

        # Check spans
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1, "Expected one span for the task")

        task_span = spans[0]
        self.assertEqual(task_span.name, "Test Task.manual.task")
        self.assertEqual(task_span.status.status_code, StatusCode.OK)

        # Check attributes
        attrs = task_span.attributes
        self.assertEqual(attrs.get("gen_ai.task.id"), task.element_id)
        self.assertEqual(attrs.get("gen_ai.task.name"), "Test Task")
        self.assertEqual(attrs.get("gen_ai.task.kind"), "action")
        self.assertIn("test", json.loads(attrs.get("gen_ai.task.tags", "[]")))
        self.assertEqual(attrs.get("gen_ai.task.status"), "success")
        self.assertEqual(attrs.get("gen_ai.task.state"), "ended")

        # Check output attributes
        output_values = json.loads(attrs.get("gen_ai.task.output.data.values", "[]"))
        self.assertEqual(output_values, ["Result 1", "Result 2"])
        output_ranking = json.loads(attrs.get("gen_ai.task.output.data.ranking", "[]"))
        self.assertEqual(output_ranking, [0.9, 0.8])

    def test_task_with_structured_input(self):
        """Test task with structured input parameters."""
        task_input = TaskInput(
            goal="Process customer data and generate insights",
            instructions=["Clean data", "Analyze patterns", "Generate report"],
            examples=["Example 1: Customer segmentation", "Example 2: Churn prediction"],
            data="customer_data.csv",
            metadata={"source": "CRM", "format": "CSV"}
        )

        task = ReportableTask(
            name="Data Analysis Task",
            kind=TaskKind.REASONING,
            input=task_input,
            session_id="session-123"  # Test the new session_id field
        )

        with task.span():
            # Simulate analysis
            task.output = {"insights": ["Pattern A", "Pattern B"]}

        spans = self.exporter.get_finished_spans()
        task_span = spans[0]
        attrs = task_span.attributes

        # Check input attributes
        self.assertEqual(attrs.get("gen_ai.task.input.goal"), "Process customer data and generate insights")
        instructions = json.loads(attrs.get("gen_ai.task.input.instructions", "[]"))
        self.assertEqual(len(instructions), 3)
        self.assertEqual(instructions[0], "Clean data")
        examples = json.loads(attrs.get("gen_ai.task.input.examples", "[]"))
        self.assertEqual(len(examples), 2)
        self.assertEqual(attrs.get("gen_ai.task.input.data"), "customer_data.csv")
        self.assertEqual(attrs.get("gen_ai.task.session.id"), "session-123")

    def test_task_exception_handling(self):
        """Test task exception handling."""
        task = ReportableTask(
            name="Failing Task",
            kind=TaskKind.ACTION,
            tags=["test", "error-handling"]
        )

        # Execute task that will fail
        with self.assertRaises(ValueError):
            with task.span():
                # Simulate some work
                raise ValueError("Simulated task failure")

        # Verify task state
        self.assertEqual(task.status, TaskStatus.FAILURE)
        self.assertEqual(task.state, TaskState.ENDED)
        self.assertIsNotNone(task.start_time)
        self.assertIsNotNone(task.end_time)

        # Check spans
        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        task_span = None
        for span in spans:
            if span.name == "Failing Task.manual.task":
                task_span = span
                break

        self.assertIsNotNone(task_span, "Task span not found")
        self.assertEqual(task_span.status.status_code, StatusCode.ERROR)

        # Check that exception was recorded
        self.assertGreater(len(task_span.events), 0)
        exception_found = False
        for event in task_span.events:
            if event.name == "exception":
                exception_found = True
                break
        self.assertTrue(exception_found, "Exception event not found in span")

    def test_manual_reporting(self):
        """Test manual task reporting without context manager."""
        task = ReportableTask(
            name="Manual Task",
            kind=TaskKind.RETRIEVAL
        )

        # Report always creates a new span for tasks
        task.state = TaskState.IN_PROGRESS
        task.start_time = datetime.now()
        task.report()

        # Final report (creates another span)
        task.status = TaskStatus.SUCCESS
        task.state = TaskState.ENDED
        task.end_time = datetime.now()
        task.output = {"total_processed": 100}
        task.report()

        # Each report() call creates a new span for tasks
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 2, "Expected 2 spans (one for each report call)")

        # All spans should be task spans
        for span in spans:
            self.assertEqual(span.name, "Manual Task.manual.task")
            attrs = span.attributes
            self.assertEqual(attrs.get("gen_ai.task.name"), "Manual Task")

        # Last span should have the final state
        final_span = spans[-1]
        attrs = final_span.attributes
        self.assertEqual(attrs.get("gen_ai.task.status"), "success")
        self.assertEqual(attrs.get("gen_ai.task.state"), "ended")

    def test_nested_tasks(self):
        """Test nested task execution."""
        parent_task = ReportableTask(
            name="Parent Task",
            kind=TaskKind.COORDINATION
        )

        child_task1 = ReportableTask(
            name="Child Task 1",
            kind=TaskKind.ACTION,
            parent_id=parent_task.element_id
        )

        child_task2 = ReportableTask(
            name="Child Task 2",
            kind=TaskKind.ACTION,
            parent_id=parent_task.element_id
        )

        with parent_task.span():
            parent_task.output = {"children": []}

            with child_task1.span():
                child_task1.output = "Result 1"
                parent_task.output["children"].append(child_task1.element_id)

            with child_task2.span():
                child_task2.output = "Result 2"
                parent_task.output["children"].append(child_task2.element_id)

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 3, "Expected 3 spans (1 parent + 2 children)")

        # Find parent span
        parent_span = None
        child_spans = []
        for span in spans:
            if span.name == "Parent Task.manual.task":
                parent_span = span
            else:
                child_spans.append(span)

        self.assertIsNotNone(parent_span)
        self.assertEqual(len(child_spans), 2)

        # Verify parent-child relationships in attributes
        for child_span in child_spans:
            attrs = child_span.attributes
            self.assertEqual(attrs.get("gen_ai.task.parent.id"), parent_task.element_id)

    def test_task_with_feedback(self):
        """Test task with feedback attributes."""
        from agent_analytics_common.interfaces.task import TaskFeedback, FeedbackSource

        task = ReportableTask(
            name="Task with Feedback",
            kind=TaskKind.SYNTHESIS
        )

        with task.span():
            task.output = "Generated summary of the document"

            # Add feedback
            task.feedback = TaskFeedback(
                source=FeedbackSource.HUMAN,
                source_id="user-123",
                rating=0.85,
                value="Good summary but missing key point about conclusion"
            )

        spans = self.exporter.get_finished_spans()
        task_span = spans[0]
        attrs = task_span.attributes

        # Check feedback attributes
        self.assertEqual(attrs.get("gen_ai.task.feedback.source"), "human")
        self.assertEqual(attrs.get("gen_ai.task.feedback.source.id"), "user-123")
        self.assertEqual(attrs.get("gen_ai.task.feedback.rating"), 0.85)
        self.assertEqual(attrs.get("gen_ai.task.feedback.value"),
                         "Good summary but missing key point about conclusion")

    def test_as_task_decorator(self):
        """Test the as_task decorator for automatic task creation and management."""

        @ReportableTask.as_task(name="Process Data", kind=TaskKind.ACTION)
        def process_data(input_value):
            """Process some data."""
            return input_value * 2

        # Execute the decorated function
        result = process_data(5)

        # Verify the result
        self.assertEqual(result, 10)

        # Check that a task span was created
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1, "Expected one span for the decorated function")

        task_span = spans[0]
        self.assertEqual(task_span.name, "Process Data.manual.task")
        self.assertEqual(task_span.status.status_code, StatusCode.OK)

        # Check task attributes
        attrs = task_span.attributes
        self.assertEqual(attrs.get("gen_ai.task.name"), "Process Data")
        self.assertEqual(attrs.get("gen_ai.task.kind"), "action")
        self.assertEqual(attrs.get("gen_ai.task.status"), "success")
        self.assertEqual(attrs.get("gen_ai.task.state"), "ended")

        # Check that input was captured
        input_data = attrs.get("gen_ai.task.input.data")
        self.assertIsNotNone(input_data)
        self.assertIn("5", input_data)

        # Check that output was captured
        output_values = json.loads(attrs.get("gen_ai.task.output.data.values", "[]"))
        self.assertEqual(len(output_values), 1)
        self.assertEqual(output_values[0], "10")

    def test_as_task_decorator_with_default_name(self):
        """Test the as_task decorator using function name as default."""

        @ReportableTask.as_task()
        def my_custom_task(x, y):
            """Add two numbers."""
            return x + y

        # Execute the decorated function
        result = my_custom_task(3, 7)

        # Verify the result
        self.assertEqual(result, 10)

        # Check span
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)

        task_span = spans[0]
        # Should use function name as task name
        self.assertEqual(task_span.name, "my_custom_task.manual.task")

        attrs = task_span.attributes
        self.assertEqual(attrs.get("gen_ai.task.name"), "my_custom_task")
        self.assertEqual(attrs.get("gen_ai.task.kind"), "action")  # Default kind

    def test_as_task_decorator_with_exception(self):
        """Test the as_task decorator handles exceptions properly."""

        @ReportableTask.as_task(name="Failing Task", kind=TaskKind.REASONING)
        def failing_task():
            """A task that fails."""
            raise ValueError("Task execution failed")

        # Execute the decorated function - should raise exception
        with self.assertRaises(ValueError):
            failing_task()

        # Check span
        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        # Find the task span
        task_span = None
        for span in spans:
            if "Failing Task" in span.name:
                task_span = span
                break

        self.assertIsNotNone(task_span, "Task span not found")
        self.assertEqual(task_span.status.status_code, StatusCode.ERROR)

        # Check that exception was recorded
        exception_found = False
        for event in task_span.events:
            if event.name == "exception":
                exception_found = True
                break
        self.assertTrue(exception_found, "Exception event not found in span")

        # Check task status
        attrs = task_span.attributes
        self.assertEqual(attrs.get("gen_ai.task.status"), "failure")
        self.assertEqual(attrs.get("gen_ai.task.state"), "ended")

    def test_generate_class_name_element_id_prefix(self):
        """Test that generate_class_name is used for element_id prefix."""
        task = ReportableTask(kind=TaskKind.ACTION)

        # Verify element_id has correct prefix from generate_class_name
        self.assertTrue(task.element_id.startswith("Task-"))

        # Verify in span attributes
        with task.span():
            pass

        spans = self.exporter.get_finished_spans()
        task_span = spans[0]
        attrs = task_span.attributes

        # Check element_id in attributes starts with correct prefix
        element_id = attrs.get("gen_ai.task.id")
        self.assertIsNotNone(element_id)
        self.assertTrue(element_id.startswith("Task-"))


if __name__ == "__main__":
    unittest.main()
