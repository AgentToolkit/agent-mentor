import unittest
from typing import TypedDict
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from agent_analytics.instrumentation import agent_analytics_sdk
from agent_analytics.instrumentation.configs import CustomExporterConfig
from dotenv import load_dotenv

load_dotenv()

# Check if LangGraph is available
try:
    from langgraph.graph import StateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


# Define a state schema for our test graph
class GraphState(TypedDict):
    result: int
    input_a: int
    input_b: int


class TestNewTraceOnWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Skip all tests if LangGraph is not available
        if not LANGGRAPH_AVAILABLE:
            raise unittest.SkipTest("LangGraph not available, skipping tests")

        cls.exporter = InMemorySpanExporter()
        config = CustomExporterConfig(
            resource_attributes={"service.name": "test-service"},
            new_trace_on_workflow=False,
        )
        agent_analytics_sdk.initialize_observability(
            config=config,
            custom_exporter=cls.exporter,
        )

    def tearDown(self):
        # Clear the exporter
        self.exporter.clear()

    def _create_and_execute_graph(self):
        """Create a simple LangGraph workflow and invoke it twice."""
        # Define a simple node function
        def add_node(state: GraphState):
            # Simple addition function that uses values from the state
            return {"result": state["input_a"] + state["input_b"],
                    "input_a": state["input_a"],
                    "input_b": state["input_b"]}

        # Create a simple graph
        builder = StateGraph(GraphState)
        builder.add_node("add", add_node)
        builder.set_entry_point("add")
        builder.set_finish_point("add")

        # Build the graph
        graph = builder.compile()

        # Execute the workflow twice with different inputs
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test"):
            result1 = graph.invoke({"result": 0, "input_a": 1, "input_b": 2})
            result2 = graph.invoke({"result": 0, "input_a": 3, "input_b": 4})

        return result1, result2

    def test_without_new_trace_on_workflow(self):
        """Test that new_trace_on_workflow=False maintains trace context across workflow invocations."""

        # Run workflow
        self._create_and_execute_graph()

        # Get all spans
        spans = self.exporter.get_finished_spans()

        invoke_spans = [span for span in spans if span.name == "LangGraph.workflow"]

        # We should have at least 2 invocation spans from our two invoke calls
        self.assertEqual(
            len(invoke_spans), 2,
            "Expected at least 2 spans for CompiledGraph.invoke"
        )

        # Without new_trace_on_workflow, all spans should share the same trace ID as the parent
        trace_ids = {span.context.trace_id for span in spans}
        self.assertEqual(
            len(trace_ids), 1,
            "With new_trace_on_workflow=False, all spans should have the same trace ID"
        )


if __name__ == "__main__":
    unittest.main()
