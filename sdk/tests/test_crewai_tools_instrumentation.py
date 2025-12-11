import unittest
import json
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from dotenv import load_dotenv
load_dotenv()

# Disable CrewAI telemetry to prevent interference with tests, as CrewAI sets the global tracer provider.
# We set the environment variable before importing any CrewAI modules to ensure it's applied.
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

from agent_analytics.instrumentation.traceloop.sdk.tracing.opentelemetry_instrumentation_crewai import (  # noqa: E402
    CrewAIInstrumentation,
)
from crewai.tools import tool  # noqa: E402
from crewai.tools.base_tool import BaseTool  # noqa: E402
from crewai.tools.structured_tool import CrewStructuredTool  # noqa: E402


class Addition(BaseTool):
    name: str = "addition"
    description: str = "Add one number to another."

    def _run(self, first_number: int, second_number: int) -> int:
        return first_number + second_number


@tool("subtraction")
def subtraction(first_number: int, second_number: int):
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


class TestCrewAITools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This method runs once before all tests in this class.
        cls.exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(cls.exporter)

        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        CrewAIInstrumentation().instrument()

    def setUp(self):
        # This is runs before every test in this class.
        self.exporter.clear()

    def invoke_and_assert_tool_span(
        self, structured_tool: CrewStructuredTool, expected_code_id: str, has_output_schema=True
    ):
        structured_tool.invoke({"first_number": 1, "second_number": 2})
        spans = self.exporter.get_finished_spans()

        self.assertEqual(len(spans), 1, "Expected one tool span")
        span = spans[0]

        self.assertEqual(span.attributes["gen_ai.action.code.id"], expected_code_id)
        self.assertEqual(
            json.loads(span.attributes["gen_ai.action.code.input_schema"]),
            EXPECTED_INPUT_SCHEMA,
        )

        if has_output_schema:
            self.assertEqual(
                span.attributes["gen_ai.action.code.output_schema"], "<class 'int'>"
            )
        else:
            self.assertNotIn("gen_ai.action.code.output_schema", span.attributes)

    def test_tool_subclass(self):
        tool = Addition()
        expected_code_id = "test_crewai_tools_instrumentation.py:29:tests.test_crewai_tools_instrumentation:Addition._run"  # noqa: E501

        structured_tool = tool.to_structured_tool()
        self.invoke_and_assert_tool_span(structured_tool, expected_code_id)

    def test_tool_decorator(self):
        tool = subtraction
        expected_code_id = "test_crewai_tools_instrumentation.py:33:tests.test_crewai_tools_instrumentation:subtraction"

        structured_tool = tool.to_structured_tool()
        self.invoke_and_assert_tool_span(
            structured_tool, expected_code_id, has_output_schema=False
        )

    def test_tool_from_function(self):
        structured_tool = CrewStructuredTool.from_function(multiplication)
        expected_code_id = "test_crewai_tools_instrumentation.py:45:tests.test_crewai_tools_instrumentation:multiplication"  # noqa: E501

        self.invoke_and_assert_tool_span(structured_tool, expected_code_id)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
