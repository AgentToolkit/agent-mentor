import unittest
import os
import shutil
import json

from crewai.tools import tool
from crewai import Agent, Task, Crew, Process
from crewai import LLM
from crewai.tools.base_tool import BaseTool
from opentelemetry import trace
from agent_analytics.instrumentation import agent_analytics_sdk
from agent_analytics.instrumentation.configs import LogExporterConfig
from dotenv import load_dotenv
load_dotenv()

LOG_FILENAME = "test_crewai"
# Global log file path
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "log", f"{LOG_FILENAME}.log")


# Function to run CrewAI
def run_crewai():
    azure_llm = LLM(
        model="azure/gpt-4o",
        base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"]
    )

    class Addition(BaseTool):
        name: str = "addition"
        description: str = "addition"

        def _run(self, first_number: int, second_number: int) -> str:
            # def print_call_stack():
            #     """Prints the call stack with function names, line numbers, and file names using the inspect module."""  # noqa: E501
            #     import inspect
            #     print("Call Stack:")
            #     stack = inspect.stack()
            #     for frame_info in stack[1:]:  # Exclude the current function call
            #         frame = frame_info.frame
            #         print(f"File: {frame_info.filename}, Line: {frame_info.lineno}, Function: {frame_info.function}")
            # print_call_stack()
            # print(f"Addition({first_number},{second_number})")
            return first_number + second_number

    @tool("subtraction")
    def subtraction(first_number: int, second_number: int):
        """Subtract one number from another.

        :param first_number: The minuend (the number from which another number is to be subtracted).
        :param second_number: The subtrahend (the number to be subtracted from first_number).
        :return: The difference of first_number and second_number.
        """

        # print(f"subtraction({first_number},{second_number})")
        return first_number - second_number

    @tool("multiplication")
    def multiplication(first_number: int, second_number: int):
        """Multiply two numbers.

        :param first_number: The first factor.
        :param second_number: The second factor.
        :return: The product of first_number and second_number.
        """

        # print(f"multiplication({first_number},{second_number})")
        return first_number * second_number

    @tool("division")
    def division(first_number: int, second_number: int):
        """Divide one number by another.

        :param first_number: The dividend (the number to be divided).
        :param second_number: The divisor (the number by which x is to be divided).
        :return: The quotient of first_number divided by second_number.
        """
        # print(f"division({first_number},{second_number})")
        return first_number / second_number

    tools = [Addition(), subtraction, multiplication, division]

    calculator = Agent(
        role="""
            You are an expert mathematician responsible for calculating mathematical expressions.
        """,
        goal="""
            Your goal is to evaluate an arithmetic expression containing both constants and predefined variables and provide the result.

            Instructions:
            - You will receive:
            - A list of predefined variables along with their respective values.
            - An arithmetic expression to evaluate.
            - Follow these rules:
            - First, replace the variables provided in the input with their values.
            - Evaluate the arithmetic expression step-by-step using the addition, subtraction, multiplication, and division tools provided to you, following the PEMDAS order of operations (Parentheses, Exponents, Multiplication and Division, Addition and Subtraction).
            - Once you have calculated the value, output the result in the exact format: "var_name = calculated_value".
        """,  # noqa: E501
        backstory='You are given a math expression that needs to be decomposed',
        examples=[
            """
                Example Input:
                    E0 = 3
                    E1 = 4
                    E2 = (1 + E0 * 5) - E1 / 2
                Expected Output:
                    E2 = 14
            """
        ],
        llm=azure_llm,
        allow_delegation=True,
        tools=tools
    )

    clac_E0 = Task(
        description='Calculate E0=1+2',
        expected_output="A result of the calculation",
        agent=calculator,
        tools=tools
    )

    calc_E1 = Task(
        description='Calculate E1=2+2',
        expected_output="The result of the subtraction opperatioin.",
        agent=calculator,
        tools=tools
    )

    calc_E2 = Task(
        description='Calculate E2 = (1 + E0 * 5) - E1 / 2',
        expected_output="The result of the subtraction opperatioin.",
        agent=calculator,
        tools=tools,
        context=[clac_E0, calc_E1]
    )

    # Create the Crew and execute TaskA
    crew = Crew(
        agents=[calculator],
        tasks=[clac_E0, calc_E1, calc_E2],
        verbose=False,
        process=Process.sequential,
        tools=tools
    )

    # Start the Crew's work
    _ = crew.kickoff()


# Run CrewAI outside of the test class and set up logging
def setup_logging_and_run_crewai():
    """Initialize logging and run CrewAI."""
    config = LogExporterConfig(log_filename=LOG_FILENAME)
    agent_analytics_sdk.initialize_observability(
        config=config,
    )
    run_crewai()


# Unit Testing Class
class TestCrewAI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # This method runs once before all tests in this class.
        setup_logging_and_run_crewai()

    @classmethod
    def tearDownClass(cls):
        # This method runs once after all tests in this class.
        log_dir = os.path.dirname(LOG_FILE_PATH)
        if os.path.exists(log_dir):
            shutil.rmtree(log_dir)
        # Reset the tracing
        # Get the current tracer provider
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, "shutdown"):
            tracer_provider.shutdown()
            tracer_provider = trace.get_tracer_provider()
            pass

    def _load_spans(self):
        """"Load spans from log file."""
        # this method will be activated only we have validated log file generation
        # parse the spans from the log file only once
        if not hasattr(TestCrewAI, 'spans'):
            with open(LOG_FILE_PATH, 'r') as file:
                log_file_content = file.read()
            spans = []
            start = 0
            while start < len(log_file_content):
                try:
                    json_obj, end = json.JSONDecoder().raw_decode(log_file_content[start:].lstrip())
                    spans.append(json_obj)
                    start += end+1
                except json.JSONDecodeError:
                    break
            self.spans = spans

    def test_01_log_creation(self):
        """Verify log file creation and non-empty content."""
        self.assertTrue(
            os.path.exists(LOG_FILE_PATH) and os.path.getsize(LOG_FILE_PATH) > 0,
            "Log file was not created or is empty."
        )

    def test_02_crew_kickoff_span_created(self):
        """ Test if the 'Crew.kickoff' span was created and has the required attributes. """
        self._load_spans()
        # Find the 'Crew.kickoff' span
        crew_kickoff_span = None
        for span in self.spans:
            if span.get("name") == "Crew.kickoff":
                crew_kickoff_span = span
                break

        self.assertIsNotNone(crew_kickoff_span, "'Crew.kickoff' span not found in logs.")

        # Check required attributes
        attributes = crew_kickoff_span.get("attributes", {})
        self.assertIn("crew_tasks", attributes, "Missing 'crew_tasks' attribute in 'Crew.kickoff' span.")
        self.assertIn("crew_agents", attributes, "Missing 'crew_agents' attribute in 'Crew.kickoff' span.")
        self.assertIn("crew_number_of_agents", attributes,
                      "Missing 'crew_number_of_agents' attribute in 'Crew.kickoff' span.")
        self.assertIn("crew_number_of_tasks", attributes,
                      "Missing 'crew_number_of_tasks' attribute in 'Crew.kickoff' span.")
        self.assertIn("crew_process", attributes, "Missing 'crew_process' attribute in 'Crew.kickoff' span.")
        self.assertIn("crew_key", attributes, "Missing 'crew_key' attribute in 'Crew.kickoff' span.")
        self.assertIn("crew_id", attributes, "Missing 'crew_id' attribute in 'Crew.kickoff' span.")

        # Check that these attributes are not null or empty
        self.assertIsNotNone(attributes["crew_tasks"], "'crew_tasks' attribute is None in 'Crew.kickoff' span.")
        self.assertNotEqual(attributes["crew_tasks"], "", "'crew_tasks' attribute is empty in 'Crew.kickoff' span.")

        self.assertIsNotNone(attributes["crew_agents"], "'crew_agents' attribute is None in 'Crew.kickoff' span.")
        self.assertNotEqual(attributes["crew_agents"], "", "'crew_agents' attribute is empty in 'Crew.kickoff' span.")

        self.assertIsNotNone(attributes["crew_number_of_agents"],
                             "'crew_number_of_agents' attribute is None in 'Crew.kickoff' span.")
        self.assertIsInstance(attributes["crew_number_of_agents"], int, "'crew_number_of_agents' should be an int.")

        self.assertIsNotNone(attributes["crew_number_of_tasks"],
                             "'crew_number_of_tasks' attribute is None in 'Crew.kickoff' span.")
        self.assertIsInstance(attributes["crew_number_of_tasks"], int, "'crew_number_of_tasks' should be an int.")

        self.assertIsNotNone(attributes["crew_process"], "'crew_process' attribute is None in 'Crew.kickoff' span.")
        self.assertNotEqual(attributes["crew_process"], "", "'crew_process' attribute is empty in 'Crew.kickoff' span.")

        self.assertIsNotNone(attributes["crew_key"], "'crew_key' attribute is None in 'Crew.kickoff' span.")
        self.assertNotEqual(attributes["crew_key"], "", "'crew_key' attribute is empty in 'Crew.kickoff' span.")

        self.assertIsNotNone(attributes["crew_id"], "'crew_id' attribute is None in 'Crew.kickoff' span.")
        self.assertNotEqual(attributes["crew_id"], "", "'crew_id' attribute is empty in 'Crew.kickoff' span.")

    def test_02_task_execute_spans_and_context(self):
        """ Check for 'Task.execute' spans and ensure 'crewai.task.context' attribute presence. """
        self._load_spans()
        task_execute_spans = [span for span in self.spans if span.get("name") == "Task.execute"]

        # Ensure at least one Task.execute span was found
        self.assertTrue(len(task_execute_spans) > 0, "No 'Task.execute' spans found.")

        # Check 'crewai.task.context' attribute if expected
        # We'll check if at least one of the Task.execute spans has 'crewai.task.context'
        has_context_span = False
        for span in task_execute_spans:
            attributes = span.get("attributes", {})
            if "crewai.task.context" in attributes:
                has_context_span = True
                # 'crewai.task.context' should be a non-empty attribute
                self.assertIsNotNone(attributes["crewai.task.context"], "'crewai.task.context' is None.")
                self.assertNotEqual(attributes["crewai.task.context"], "", "'crewai.task.context' is empty.")
                break

        self.assertTrue(has_context_span, "No 'Task.execute' span with 'crewai.task.context' attribute found.")

    def test_03_tools_spans_created(self):
        """ Check for the creation of spans for all of the tools and includes BaseTool class """
        self._load_spans()
        tool_execute_spans = [span.get("name") for span in self.spans if span.get("name").endswith(".tool")]

        # Ensure All tool were used and a span was recorded for each one
        self.assertSetEqual(
            set(tool_execute_spans),
            {'division.tool', 'addition.tool', 'multiplication.tool', 'subtraction.tool'},
            "Not All tool spans were created")


if __name__ == "__main__":
    # Run CrewAI and generate logs
    # setup_logging_and_run_crewai()

    # Run the tests
    unittest.main()

    # clean
    # log_dir = os.path.dirname(LOG_FILE_PATH)
    # if os.path.exists(log_dir):
    #     shutil.rmtree(log_dir)
