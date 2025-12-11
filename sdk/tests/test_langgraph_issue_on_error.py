import unittest
from typing import TypedDict

from langgraph.graph import StateGraph, END, START

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from agent_analytics.instrumentation.traceloop.sdk.tracing.opentelemetry_instrumentation_langchain import (
    LangchainInstrumentor,
)


class GraphState(TypedDict):
    value: int


def failing_node(state: GraphState) -> GraphState:
    """A node that always raises an exception."""
    raise ValueError("This node always fails with a ValueError")
    pass


def build_failing_graph():
    """Build a simple graph with a node that will fail."""
    workflow = StateGraph(GraphState)
    workflow.add_node("failing_node", failing_node)
    workflow.add_edge(START, "failing_node")
    workflow.add_edge("failing_node", END)
    return workflow.compile()


class TestLangGraphIssueRecording(unittest.TestCase):
    """Test that exceptions in LangGraph nodes trigger issue recording."""

    @classmethod
    def setUpClass(cls):
        cls.exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(cls.exporter)

        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        LangchainInstrumentor().instrument()

    def setUp(self):
        self.exporter.clear()

    def test_node_exception_records_issue(self):
        """Test that an exception in a LangGraph node triggers issue recording."""
        graph = build_failing_graph()

        # Create a tracer and start a span
        try:
            graph.invoke({"value": 42})
        except Exception as e:
            print(f"Exception Happened {e}")

        # Verify the exception message
        # self.assertIn("This node always fails", str(context.exception))
        # Get all recorded spans
        spans = self.exporter.get_finished_spans()
        print(f"Total spans recorded: {len(spans)}")

        # Look for issue events in the spans
        issue_found = False
        for span in spans:
            print(f"Span: {span.name}, Events: {len(span.events)}")
            for event in span.events:
                print(f"  Event: {event.name}")
                if event.name.endswith(".issue"):
                    issue_found = True
                    # Verify the issue has relevant attributes
                    attributes = event.attributes
                    print(f"Issue found with attributes: {attributes}")
                    break

        # Assert that at least one issue was recorded
        self.assertTrue(issue_found, "Expected at least one issue to be recorded when node fails")


if __name__ == "__main__":
    unittest.main()
