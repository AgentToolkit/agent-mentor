import unittest
import json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from agent_analytics.instrumentation.traceloop.sdk.tracing.opentelemetry_instrumentation_langchain import (
    LangchainInstrumentor,
)

from langchain_core.tools import BaseTool, StructuredTool, tool


class Addition(BaseTool):
    name: str = "addition"
    description: str = "Add one number to another."

    def _run(self, first_number: int, second_number: int) -> int:
        return first_number + second_number

    async def _arun(self, first_number: int, second_number: int) -> int:
        return first_number + second_number


@tool("subtraction")
def subtraction(first_number: int, second_number: int) -> int:
    """Subtract one number from another.

    :param first_number: The minuend (the number from which another number is to be subtracted).
    :param second_number: The subtrahend (the number to be subtracted from first_number).
    :return: The difference of first_number and second_number.
    """

    return first_number - second_number


@tool("subtraction")
async def asubtraction(first_number: int, second_number: int) -> int:
    """Subtract one number from another.

    :param first_number: The minuend (the number from which another number is to be subtracted).
    :param second_number: The subtrahend (the number to be subtracted from first_number).
    :return: The difference of first_number and second_number.
    """

    return first_number - second_number


def multiplication(first_number: int, second_number: int) -> int:
    """Multiply two numbers.

    :param first_number: The first factor.
    :param second_number: The second factor.
    :return: The product of first_number and second_number.
    """

    return first_number * second_number


async def amultiplication(first_number: int, second_number: int) -> int:
    """Multiply two numbers.

    :param first_number: The first factor.
    :param second_number: The second factor.
    :return: The product of first_number and second_number.
    """

    return first_number * second_number

DEFAULT_INPUT = {"first_number": 1, "second_number": 2}
EXPECTED_INPUT_SCHEMA = json.loads(
    """
{
  "first_number": {
    "annotation": "<class 'int'>",
    "default": null,
    "kind": "POSITIONAL_OR_KEYWORD"
  },
  "second_number": {
    "annotation": "<class 'int'>",
    "default": null,
    "kind": "POSITIONAL_OR_KEYWORD"
  }
}
"""
)


# Unit Testing Class
class TestLangChainTools(unittest.IsolatedAsyncioTestCase):

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

    def assert_single_tool_span(self, spans, expected_code_id):
        self.assertEqual(len(spans), 1, "Expected one tool span")
        span = spans[0]
        self.assertEqual(span.attributes.get("gen_ai.action.code.id"), expected_code_id)
        self.assertEqual(
            json.loads(span.attributes.get("gen_ai.action.code.input_schema")),
            EXPECTED_INPUT_SCHEMA,
        )
        self.assertEqual(
            span.attributes.get("gen_ai.action.code.output_schema"), "<class 'int'>"
        )

    def test_tool_subclass(self):
        tool = Addition()
        expected_code_id = "test_langchain_tools_instrumentation.py:20:tests.test_langchain_tools_instrumentation:Addition._run"  # noqa: E501

        tool.invoke(DEFAULT_INPUT)
        spans = self.exporter.get_finished_spans()
        self.assert_single_tool_span(spans, expected_code_id)

    def test_tool_decorator(self):
        tool = subtraction
        expected_code_id = "test_langchain_tools_instrumentation.py:27:tests.test_langchain_tools_instrumentation:subtraction"  # noqa: E501

        tool.invoke(DEFAULT_INPUT)
        spans = self.exporter.get_finished_spans()
        self.assert_single_tool_span(spans, expected_code_id)

    def test_tool_from_function(self):
        tool = StructuredTool.from_function(
            func=multiplication, coroutine=amultiplication
        )
        expected_code_id = "test_langchain_tools_instrumentation.py:51:tests.test_langchain_tools_instrumentation:multiplication"  # noqa: E501

        tool.invoke(DEFAULT_INPUT)
        spans = self.exporter.get_finished_spans()
        self.assert_single_tool_span(spans, expected_code_id)

    async def test_async_tool_subclass(self):
        tool = Addition()
        expected_code_id = "test_langchain_tools_instrumentation.py:23:tests.test_langchain_tools_instrumentation:Addition._arun"  # noqa: E501

        await tool.ainvoke(DEFAULT_INPUT)
        spans = self.exporter.get_finished_spans()
        self.assert_single_tool_span(spans, expected_code_id)

    async def test_async_tool_decorator(self):
        tool = asubtraction
        expected_code_id = "test_langchain_tools_instrumentation.py:39:tests.test_langchain_tools_instrumentation:asubtraction"  # noqa: E501

        await tool.ainvoke(DEFAULT_INPUT)
        spans = self.exporter.get_finished_spans()
        self.assert_single_tool_span(spans, expected_code_id)

    async def test_async_tool_from_function(self):
        tool = StructuredTool.from_function(
            func=multiplication, coroutine=amultiplication
        )
        expected_code_id = "test_langchain_tools_instrumentation.py:62:tests.test_langchain_tools_instrumentation:amultiplication"  # noqa: E501

        await tool.ainvoke(DEFAULT_INPUT)
        spans = self.exporter.get_finished_spans()
        self.assert_single_tool_span(spans, expected_code_id)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
