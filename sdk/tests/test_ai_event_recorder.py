import unittest
from datetime import datetime
import uuid

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from agent_analytics_common.interfaces.resources import ResourceCategory
from agent_analytics_common.interfaces.annotations import DataAnnotation
from agent_analytics_common.interfaces.issues import IssueLevel
from agent_analytics_common.interfaces.metric import MetricType
from agent_analytics.instrumentation.utils import AIEventRecorder


class TestAIEventRecorder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(cls.exporter)
        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

    def setUp(self):
        self.exporter.clear()

    def generate_short_uuid(self):
        return str(uuid.uuid4())[:8]

    def test_record_resource(self):
        """Test recording a resource."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_record_resource"):
            resource = AIEventRecorder.record_resource(
                name="Test Resource",
                description="A test resource for unit testing",
                category=ResourceCategory.TEXT,
                format="txt",
                payload="This is a test payload"
            )

        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events
        self.assertGreaterEqual(len(events), 1)

        resource_event = None
        for event in events:
            if event.name.endswith(".resource"):
                resource_event = event
                break

        self.assertIsNotNone(resource_event, "No resource event found in the span")

        attributes = resource_event.attributes
        self.assertEqual(attributes.get("name"), "Test Resource")
        self.assertEqual(attributes.get("category"), str(ResourceCategory.TEXT))
        self.assertEqual(attributes.get("format"), "txt")
        self.assertIsNotNone(attributes.get("payload"))

        # Verify the returned resource object
        self.assertEqual(resource.name, "Test Resource")
        self.assertEqual(resource.description, "A test resource for unit testing")
        self.assertEqual(resource.category, ResourceCategory.TEXT)
        self.assertEqual(resource.format, "txt")
        self.assertEqual(resource.payload, "This is a test payload")

    def test_record_data_annotation(self):
        """Test recording a data annotation."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_record_data_annotation"):
            annotation = AIEventRecorder.record_data_annotation(
                name="Test Annotation",
                description="A test annotation for unit testing",
                path_to_string="/data/text",
                segment_start=0,
                segment_end=10,
                annotation_type=DataAnnotation.Type.CODE_SNIPPET,
                annotation_title="Code Example",
                annotation_content="print('Hello World')"
            )

        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events
        self.assertGreaterEqual(len(events), 1)

        annotation_event = None
        for event in events:
            if event.name.endswith(".data_annotation"):
                annotation_event = event
                break

        self.assertIsNotNone(annotation_event, "No data annotation event found in the span")

        attributes = annotation_event.attributes
        self.assertEqual(attributes.get("name"), "Test Annotation")
        self.assertEqual(attributes.get("path_to_string"), "/data/text")
        self.assertEqual(attributes.get("segment_start"), 0)
        self.assertEqual(attributes.get("segment_end"), 10)
        self.assertEqual(attributes.get("annotation_type"), str(DataAnnotation.Type.CODE_SNIPPET))
        self.assertEqual(attributes.get("annotation_title"), "Code Example")
        self.assertEqual(attributes.get("annotation_content"), "print('Hello World')")

        # Verify the returned annotation object
        self.assertEqual(annotation.name, "Test Annotation")
        self.assertEqual(annotation.description, "A test annotation for unit testing")
        self.assertEqual(annotation.path_to_string, "/data/text")
        self.assertEqual(annotation.segment_start, 0)
        self.assertEqual(annotation.segment_end, 10)
        self.assertEqual(annotation.annotation_type, DataAnnotation.Type.CODE_SNIPPET)
        self.assertEqual(annotation.annotation_title, "Code Example")
        self.assertEqual(annotation.annotation_content, "print('Hello World')")

    def test_record_metric(self):
        """Test recording a metric."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_record_metric"):
            metric = AIEventRecorder.record_metric(
                name="Test Metric",
                description="A test metric for unit testing",
                value=42.0,
                timestamp=datetime.now().isoformat(),
                related_to_ids=["resource-123", "event-456"]
            )

        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events
        self.assertGreaterEqual(len(events), 1)

        metric_event = None
        for event in events:
            if event.name.endswith(".metric"):
                metric_event = event
                break

        self.assertIsNotNone(metric_event, "No metric event found in the span")

        attributes = metric_event.attributes
        self.assertEqual(attributes.get("name"), "Test Metric")
        self.assertEqual(attributes.get("value"), 42.0)
        self.assertIsNotNone(attributes.get("timestamp"))
        self.assertIn("resource-123", attributes.get("related_to_ids"))
        self.assertIn("event-456", attributes.get("related_to_ids"))

        # Verify the returned metric object
        self.assertEqual(metric.name, "Test Metric")
        self.assertEqual(metric.description, "A test metric for unit testing")
        self.assertEqual(metric.value, 42.0)
        self.assertIsNotNone(metric.timestamp)
        self.assertEqual(metric.related_to_ids, ["resource-123", "event-456"])
        self.assertEqual(metric.metric_type, MetricType.NUMERIC)

    def test_record_issue(self):
        """Test recording an issue."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_record_issue"):
            issue = AIEventRecorder.record_issue(
                name="Test Issue",
                description="A test issue for unit testing",
                level=IssueLevel.ERROR,
                timestamp=datetime.now().isoformat(),
                related_to_ids=["resource-123", "event-456"],
                effect=["System failure", "Data corruption"]
            )

        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events
        self.assertGreaterEqual(len(events), 1)

        issue_event = None
        for event in events:
            if event.name.endswith(".issue"):
                issue_event = event
                break

        self.assertIsNotNone(issue_event, "No issue event found in the span")

        attributes = issue_event.attributes
        self.assertEqual(attributes.get("name"), "Test Issue")
        self.assertEqual(attributes.get("level"), str(IssueLevel.ERROR))
        self.assertIsNotNone(attributes.get("timestamp"))
        self.assertIn("resource-123", attributes.get("related_to_ids"))
        self.assertIn("event-456", attributes.get("related_to_ids"))
        self.assertIn("System failure", attributes.get("effect"))
        self.assertIn("Data corruption", attributes.get("effect"))

        # Verify the returned issue object
        self.assertEqual(issue.name, "Test Issue")
        self.assertEqual(issue.description, "A test issue for unit testing")
        self.assertEqual(issue.level, IssueLevel.ERROR)
        self.assertIsNotNone(issue.timestamp)
        self.assertEqual(issue.related_to_ids, ["resource-123", "event-456"])
        self.assertEqual(issue.effect, ["System failure", "Data corruption"])

    def test_complex_scenario(self):
        """Test a complex scenario with multiple related records."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_complex_scenario"):
            # Create resources
            resource1 = AIEventRecorder.record_resource(
                name="Input Data",
                category=ResourceCategory.TEXT,
                payload="Sample input data"
            )

            resource2 = AIEventRecorder.record_resource(
                name="Output Data",
                category=ResourceCategory.TEXT,
                payload="Processed output data"
            )

            # Create a metric related to the resources
            metric = AIEventRecorder.record_metric(
                name="Processing Time",
                value=150.5,
                related_to_ids=[resource1.element_id, resource2.element_id]
            )

            # Create an annotation for the output
            annotation = AIEventRecorder.record_data_annotation(
                name="Output Analysis",
                path_to_string="/output",
                annotation_type=DataAnnotation.Type.ANALYTICAL_INSIGHT,
                annotation_content="The output shows improved performance"
            )

            # Create an issue related to all previous elements
            _ = AIEventRecorder.record_issue(
                name="Performance Warning",
                level=IssueLevel.WARNING,
                description="Processing time exceeds recommended threshold",
                related_to_ids=[
                    resource1.element_id,
                    resource2.element_id,
                    metric.element_id,
                    annotation.element_id
                ],
                effect=["May cause delays in subsequent processing"]
            )

        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events
        self.assertGreaterEqual(len(events), 5)  # 2 resources + 1 metric + 1 annotation + 1 issue

        # Count the events by type
        resource_events = 0
        metric_events = 0
        annotation_events = 0
        issue_events = 0

        for event in events:
            if event.name.endswith(".resource"):
                resource_events += 1
            elif event.name.endswith(".metric"):
                metric_events += 1
            elif event.name.endswith(".data_annotation"):
                annotation_events += 1
            elif event.name.endswith(".issue"):
                issue_events += 1

        self.assertEqual(resource_events, 2, "Expected 2 resource events")
        self.assertEqual(metric_events, 1, "Expected 1 metric event")
        self.assertEqual(annotation_events, 1, "Expected 1 annotation event")
        self.assertEqual(issue_events, 1, "Expected 1 issue event")

        # Find the issue event
        issue_event = None
        for event in events:
            if event.name.endswith(".issue"):
                issue_event = event
                break

        self.assertIsNotNone(issue_event, "No issue event found in the span")

        # Check that the issue event has the correct related_to_ids
        attributes = issue_event.attributes
        related_ids_attr = attributes.get("related_to_ids")

        self.assertIsNotNone(related_ids_attr, "related_to_ids attribute not found")

        # Since related_to_ids is serialized as a string, we need to check if each ID is in the string
        self.assertIn(resource1.element_id, related_ids_attr)
        self.assertIn(resource2.element_id, related_ids_attr)
        self.assertIn(metric.element_id, related_ids_attr)
        self.assertIn(annotation.element_id, related_ids_attr)


if __name__ == "__main__":
    unittest.main()
