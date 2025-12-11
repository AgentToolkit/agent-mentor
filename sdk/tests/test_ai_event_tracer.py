import unittest
import json
from datetime import datetime
import uuid

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from agent_analytics_common.interfaces.resources import Resource, ResourceCategory
from agent_analytics_common.interfaces.events import AIEvent
from agent_analytics.instrumentation.utils import AIEventTracer


class TestAIEventTracer(unittest.TestCase):
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

    def test_capture_resource(self):
        resource = Resource(
            name="Test Resource",
            description="A test resource for unit testing",
            category=ResourceCategory.TEXT,
            format="txt",
            payload="This is a test payload"
        )

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_capture_resource"):
            AIEventTracer.capture_resource(resource)

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

    def test_capture_ai_event(self):
        ai_event = AIEvent(
            name="Test Event",
            description="A test event for unit testing",
            status=AIEvent.Status.START,
            timestamp=datetime.now().isoformat(),
        )

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_capture_ai_event"):
            AIEventTracer.capture_ai_event(ai_event)

        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events
        self.assertGreaterEqual(len(events), 1)

        ai_event_span_event = None
        for event in events:
            if event.name.endswith(".ai_event"):
                ai_event_span_event = event
                break

        self.assertIsNotNone(ai_event_span_event, "No AI event found in the span")

        attributes = ai_event_span_event.attributes
        self.assertEqual(attributes.get("name"), "Test Event")
        self.assertEqual(attributes.get("status"), str(AIEvent.Status.START))

    def test_capture_ai_event_with_resources(self):

        ai_event = AIEvent(
            name="Test Step Completion",
            description="A test event with resources",
            timestamp=datetime.now().isoformat(),
            status=AIEvent.Status.END,
        )

        resource_list = []

        image_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg..."
        image_resource = Resource(
            category=ResourceCategory.IMAGE,
            format="base64",
            payload=image_data,
        )
        resource_list.append(image_resource.element_id)

        json_data = '{"key": "value", "number": 42}'
        is_json_string = True
        try:
            json.loads(json_data)
        except Exception:
            is_json_string = False

        data_resource = Resource(
            category=ResourceCategory.JSONSTRING if is_json_string else ResourceCategory.TEXT,
            payload=json_data,
        )
        resource_list.append(data_resource.element_id)

        text_data = "This is plain text data that isn't JSON"
        text_resource = Resource(
            category=ResourceCategory.TEXT,
            payload=text_data,
        )
        resource_list.append(text_resource.element_id)

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_capture_ai_event_with_resources"):
            AIEventTracer.capture_resource(image_resource)
            AIEventTracer.capture_resource(data_resource)
            AIEventTracer.capture_resource(text_resource)

            ai_event.resources = resource_list
            AIEventTracer.capture_ai_event(ai_event)

        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        events = main_span.events
        self.assertGreaterEqual(len(events), 4)

        resource_events = []
        ai_event_found = None

        for event in events:
            if event.name.endswith(".resource"):
                resource_events.append(event)
            elif event.name.endswith(".ai_event"):
                ai_event_found = event

        self.assertEqual(len(resource_events), 3, "Expected 3 resource events")
        self.assertIsNotNone(ai_event_found, "AI event not found")

        ai_event_attrs = ai_event_found.attributes
        self.assertEqual(ai_event_attrs.get("status"), str(AIEvent.Status.END))

        resources = ai_event.resources
        self.assertIsNotNone(resources, "Resources attribute not found in AI event")

        self.assertEqual(len(resources), 3, "Expected 3 resource IDs in the resources attribute")
        for resource_id in resource_list:
            self.assertIn(resource_id, resources, f"Resource ID {resource_id} not found in resources attribute")

    def test_capture_issue_with_related_elements(self):
        """Test capturing an issue with related resources and events."""
        from agent_analytics_common.interfaces.issues import Issue, IssueLevel

        # Create resources that will be related to the issue
        resource_ids = []
        for i in range(2):
            resource = Resource(
                name=f"Related Resource {i}",
                description="A resource related to the test issue",
                category=ResourceCategory.TEXT,
                format="txt",
                payload=f"This resource {i} is related to the issue"
            )
            resource_ids.append(resource.element_id)

        # Create an AI event that will be related to the issue
        ai_event = AIEvent(
            name="Related Event",
            description="An event related to the test issue",
            status=AIEvent.Status.FAILURE,
            timestamp=datetime.now().isoformat()
        )

        # Create the issue with relationships to the resources and event
        issue = Issue(
            name="Complex Test Issue",
            description="A test issue with related elements",
            level=IssueLevel.ERROR,
            timestamp=datetime.now().isoformat(),
            related_to_ids=[*resource_ids, ai_event.element_id],
            effect=["System failure due to related resources and events"]
        )

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_capture_issue_with_related_elements"):
            # Capture all related elements first
            for i, resource_id in enumerate(resource_ids):
                resource = Resource(
                    name=f"Related Resource {i}",
                    description="A resource related to the test issue",
                    category=ResourceCategory.TEXT,
                    format="txt",
                    payload=f"This resource {i} is related to the issue"
                )
                AIEventTracer.capture_resource(resource)

            AIEventTracer.capture_ai_event(ai_event)

            # Finally capture the issue
            AIEventTracer.capture_issue(issue)

        spans = self.exporter.get_finished_spans()
        self.assertGreaterEqual(len(spans), 1)

        main_span = spans[-1]
        print(main_span)
        events = main_span.events
        self.assertGreaterEqual(len(events), 4)  # 2 resources + 1 AI event + 1 issue

        # Find all the events
        resource_events = []
        ai_event_found = None
        issue_event = None

        for event in events:
            if event.name.endswith(".resource"):
                resource_events.append(event)
            elif event.name.endswith(".ai_event"):
                ai_event_found = event
            elif event.name.endswith(".issue"):
                issue_event = event

        self.assertEqual(len(resource_events), 2, "Expected 2 resource events")
        self.assertIsNotNone(ai_event_found, "AI event not found")
        self.assertIsNotNone(issue_event, "Issue event not found")

        # Validate issue attributes
        issue_attrs = issue_event.attributes
        self.assertEqual(issue_attrs.get("level"), str(IssueLevel.ERROR))
        self.assertEqual(issue_attrs.get("effect"), "System failure due to related resources and events")

        # Validate that related_to_ids contains references to all created elements
        related_ids_attr = issue_attrs.get("related_to_ids")
        self.assertIsNotNone(related_ids_attr, "related_to_ids attribute not found")

        # Since related_to_ids is serialized as a string, we need to check if each ID is in the string
        for resource_id in resource_ids:
            self.assertIn(resource_id, related_ids_attr, f"Resource ID {resource_id} not found in related_to_ids")

        self.assertIn(ai_event.element_id, related_ids_attr,
                      f"AI Event ID {ai_event.element_id} not found in related_to_ids")


if __name__ == "__main__":
    unittest.main()
