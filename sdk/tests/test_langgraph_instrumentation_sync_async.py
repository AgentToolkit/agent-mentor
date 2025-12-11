import unittest
import json
from typing import TypedDict
import typing

from langgraph.graph import StateGraph, END, START

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from agent_analytics.instrumentation.traceloop.sdk.tracing.opentelemetry_instrumentation_langchain import (
    LangchainInstrumentor,
)


class DummyGraphState(TypedDict):
    result: str


def mynode_func(state: DummyGraphState) -> DummyGraphState:
    return state


def build_graph():
    workflow = StateGraph(DummyGraphState)
    workflow.add_node("mynode", mynode_func)
    workflow.add_edge(START, "mynode")
    workflow.add_edge("mynode", END)
    langgraph = workflow.compile()
    return langgraph


# Unit Testing Class
class TestLangGraphSyncAsync(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        # This method runs once before all tests in this class.
        cls.exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(cls.exporter)

        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        LangchainInstrumentor().instrument()

    def setUp(self):
        # This is runs before every test in this class.
        self.exporter.clear()

    def assert_graph_structure_in_langgraph_spans(
        self, spans: typing.Tuple[ReadableSpan, ...]
    ):
        """Ensure all LangGraph.* spans contain a valid graph_structure attribute."""
        langgraph_spans = [span for span in spans if span.name.startswith("LangGraph.")]
        self.assertEqual(len(langgraph_spans), 1, "Expected one LangGraph span")
        for span in langgraph_spans:
            self.assertIn(
                "graph_structure",
                span.attributes,
                f"Missing graph_structure in LangGraph.* span: {span}",
            )
            graph_structure_json = span.attributes["graph_structure"]
            try:
                graph_structure = json.loads(
                    graph_structure_json
                )  # Check if it's a valid JSON string
                self.assertIn("nodes", graph_structure)
                self.assertIn("edges", graph_structure)
                expected_graph_structure = {
                    "nodes": ["mynode"],
                    "edges": [[["mynode"], ["__end__"]], [["__start__"], ["mynode"]]],
                }
                self.assertCountEqual(
                    graph_structure["nodes"], expected_graph_structure["nodes"]
                )
                self.assertCountEqual(
                    graph_structure["edges"], expected_graph_structure["edges"]
                )

            except json.JSONDecodeError:
                self.fail(f"Invalid JSON in graph_structure for span: {span}")

    def assert_action_attributes(
        self, spans: typing.Tuple[ReadableSpan, ...]
    ):
        mynode_spans = [span for span in spans if span.name == "mynode.task"]
        self.assertEqual(len(mynode_spans), 1)
        mynode_span = mynode_spans[0]
        expected_code_id = "test_langgraph_instrumentation_sync_async.py:23:tests.test_langgraph_instrumentation_sync_async:mynode_func"  # noqa: E501
        expected_input_schema = """
{
  "state": {
    "annotation": "<class 'tests.test_langgraph_instrumentation_sync_async.DummyGraphState'>",
    "default": null,
    "kind": "POSITIONAL_OR_KEYWORD"
  }
}
"""
        expected_output_schema = "<class 'tests.test_langgraph_instrumentation_sync_async.DummyGraphState'>"
        self.assertEqual(mynode_span.attributes["gen_ai.action.code.id"], expected_code_id)
        self.assertEqual(
            json.loads(mynode_span.attributes["gen_ai.action.code.input_schema"]),
            json.loads(expected_input_schema))
        self.assertEqual(mynode_span.attributes["gen_ai.action.code.output_schema"], expected_output_schema)

    @unittest.expectedFailure
    def test_invoke_custom_run_name(self):
        # This test is expected to fail because the SDK identifies LangGraph spans by their name prefix,
        # which defaults to "LangGraph". Changing "run_name" in the config alters this prefix.
        #
        # Reference for setting span name via "run_name":
        # https://github.com/langchain-ai/langgraph/blob/c44ec5509550122be3e55eed9abd55b4692ff446/libs/langgraph/langgraph/pregel/__init__.py#L1704C30-L1704C38
        #
        # Reference for the default span name "LangGraph":
        # https://github.com/langchain-ai/langgraph/blob/c44ec5509550122be3e55eed9abd55b4692ff446/libs/langgraph/langgraph/pregel/__init__.py#L336
        graph = build_graph()
        config = {"run_name": "MY_NAME"}
        graph.invoke({"result": "init"}, config=config)

        spans = self.exporter.get_finished_spans()
        self.assert_graph_structure_in_langgraph_spans(spans)

    def test_invoke(self):
        graph = build_graph()
        graph.invoke({"result": "init"})

        spans = self.exporter.get_finished_spans()
        self.assert_graph_structure_in_langgraph_spans(spans)
        self.assert_action_attributes(spans)

    async def test_ainvoke(self):
        graph = build_graph()
        await graph.ainvoke({"result": "init"})

        spans = self.exporter.get_finished_spans()
        self.assert_graph_structure_in_langgraph_spans(spans)

    def test_stream(self):
        graph = build_graph()
        for event in graph.stream({"result": "init"}):
            pass

        spans = self.exporter.get_finished_spans()
        self.assert_graph_structure_in_langgraph_spans(spans)

    async def test_astream(self):
        graph = build_graph()
        async for event in graph.astream({"result": "init"}):
            pass

        spans = self.exporter.get_finished_spans()
        self.assert_graph_structure_in_langgraph_spans(spans)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
