import unittest
import os
import shutil
import json
import time
import random
from typing import TypedDict

from textwrap import dedent
import openai

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END, START

from agent_analytics.instrumentation import agent_analytics_sdk
from agent_analytics.instrumentation.configs import LogExporterConfig
from dotenv import load_dotenv
load_dotenv()

LOG_FILENAME = "test_langgraph"
# Global log file path
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "log", f"{LOG_FILENAME}.log")

# Langgraph globals
MODEL = "gpt-4o-2024-08-06"
AZURE_API_VERSION = "2024-08-01-preview"

MIN_DELAY_MSEC = 100
MAX_DELAY_MSEC = 700


# Langgraph clculator
class ExpressionGraphState(TypedDict):
    expression: str
    operations: list
    result_variable_name: str
    result: float
    iteration: int
    is_result_correct: bool
    calc_operations_agent: str


def is_valid_math_expression(expression: str) -> bool:
    """
    Checks if a given string is a valid mathematical expression.

    Parameters:
    expression (str): The string containing the mathematical expression to validate.

    Returns:
    bool: Returns True if the expression is valid, meaning it can be calculated
          without any errors such as SyntaxError, NameError, or ZeroDivisionError.
          Returns False if the expression is invalid.
    """
    try:
        # Evaluate the expression to check for validity
        eval(expression)
        return True
    except (SyntaxError, NameError, ZeroDivisionError):
        # If there's an error, the expression is not valid
        return False


def calculate_single_operation(operation: str):
    client = openai.AzureOpenAI(
        api_version=AZURE_API_VERSION,
    )
    PROMPT = '''
        You are a helpful mathematician. You will be provided with a simple math operation to solve,
        and your goal will be to output a final result for the calculation.
    '''
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": dedent(PROMPT)
            },
            {
                "role": "user",
                "content": operation
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "operation_evaluator",
                "schema": {
                    "type": "object",
                    "properties": {
                        "result": {"type": "number"}
                    },
                    "required": ["result"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
    )
    output = json.loads(response.choices[0].message.content)
    return float(output["result"])


def decompose(state: ExpressionGraphState):
    SYSTEM_PROMPT = """
        You are an expert mathematician tasked with breaking down complex mathematical expressions into simpler operations according to the correct mathematical order of operations: Parentheses, Multiplication, Division, Addition, Subtraction (PEMDAS).

        Your goal is to analyze the provided expression, decompose it into simple operations, and represent each operation in a list, adhering to the following JSON schema:
        {{
            "operations": [
                {{
                    "name": "string",  // A variable name assigned to the operation (e.g., V0, V1).
                    "operation": "string",  // One of the following: "parentheses", "multiplication", "division", "addition", "subtraction".
                    "op1": "number or string",  // The first operand, either a numerical value or a reference to a variable (e.g., V0, V1) or string expression within parentheses.
                    "op2": "number or string"  // The second operand, either a numerical value or a reference to a variable (e.g., V0, V1).
                }}
            ]
        }}

        Instructions:
            Identify Top-Level parentheses:
                - When scanning the expression, focus on finding only top-level parentheses—those that are not nested inside other parentheses.
                - Assign to 'parentheses' Operation: For each top-level set of parentheses, create a new operation object labeled as parentheses. This operation will contain:
                -- op1: The entire expression inside the parentheses as a string.
                -- op2: An empty string '' since there is no second operand in this operation.
                - Do Not Decompose Expressions Inside parentheses: The expression inside the parentheses should not be further decomposed at this stage. Treat it as a single unit, regardless of its complexity.             Multiplication and Division: Handle these operations next, from left to right.
            Addition and Subtraction: Handle these last, from left to right.
            For each operation, assign a unique variable name (e.g., V0, V1) and output it as part of the "operations" list.
            Operands (op1, op2) can be either numbers or previously defined variables (e.g., V0, V1).
            Return only the list of operations within a valid JSON object that follows the given schema.

        Example Input:
            Calculate the following expression: (2 + 3 * 5) * 4 / 2
        Expected Output:
            {{
                "operations": [
                    {{
                        "name": "E0",
                        "operation": "parentheses",
                        "op1": "2+3*5",
                        "op2": ""
                    }},
                    {{
                        "name": "E1",
                        "operation": "division",
                        "op1": 4,
                        "op2": 2
                    }},
                    {{
                        "name": "E2",
                        "operation": "multiplication",
                        "op1": "E0",
                        "op2": "E1"
                    }}
                ]
            }}

        Important Notes:
            Do not decompose any expression within top-level parentheses. Assign each expression inside top-level parentheses to its own 'parentheses' operation as a single unit            Do not calculate the expression, only decompose it into a list of operations.
            Ensure that all operations are represented as valid objects following the schema.
            Variable names (e.g., C0, C1) must be unique within the list.

        If the expression cannot be processed, return an empty JSON object.
    """  # noqa: E501

    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT),
         ("user", "{input}")])

    json_schema = {
        "title": "Operations",
        "description": "List of decomposed operations for the given math expression",
        "type": "object",
        "properties": {
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "A variable name assigned to the operation (e.g., V0, V1)."
                        },
                        "operation": {
                            "type": "string",
                            "enum": ["parentheses", "multiplication", "division", "addition", "subtraction"],
                            "description": "The type of operation to be performed."
                        },
                        "op1": {
                            "oneOf": [
                                {
                                    "type": "number",
                                    "description": "The first operand, a numerical value."
                                },
                                {
                                    "type": "string",
                                    "description": "A reference to another variable (e.g., V0, V1). Or string expression withn parentheses"  # noqa: E501
                                }
                            ]
                        },
                        "op2": {
                            "oneOf": [
                                {
                                    "type": "number",
                                    "description": "The second operand, a numerical value."
                                },
                                {
                                    "type": "string",
                                    "description": "A reference to another variable (e.g., V0, V1)."
                                }
                            ]
                        }
                    },
                    "required": ["name", "operation", "op1"],
                    "additionalProperties": False
                }
            }
        },
        "additionalProperties": False
    }
    llm = AzureChatOpenAI(
        api_version=AZURE_API_VERSION,
    )
    decomposer = prompt | llm.with_structured_output(json_schema)
    expression = state["expression"]
    result = decomposer.invoke({"input": f"Calculate the following expression: {expression}"})

    for obj in result["operations"]:
        # print(json.dumps(obj, separators=(',', ':')))
        pass
    return {"operations": result["operations"]}


def create_operation_function(operations_graph_state_class, variable_name, operation, op1, op2):
    def operation_function(state: operations_graph_state_class):  # type: ignore
        # print(f"Calculate {variable_name} by {operation}({op1},{op2})")

        if operation == "parentheses":
            result = calculate_expression(op1)
        else:
            operand1 = state[op1] if isinstance(op1, str) else op1
            operand2 = state[op2] if isinstance(op2, str) else op2

            if operation == "addition":
                # result = operand1 + operand2
                result = calculate_single_operation(f"{operand1}+{operand2}")
            elif operation == "subtraction":
                result = calculate_single_operation(f"{operand1}-{operand2}")
                # result = operand1 - operand2
            elif operation == "multiplication":
                result = operand1 * operand2
            elif operation == "division":
                if operand2 == 0:
                    raise ValueError("Division by zero is not allowed.")
                result = operand1 / operand2
            else:
                raise ValueError(f"Unknown operation: {operation}")
        time.sleep(random.uniform(MIN_DELAY_MSEC, MAX_DELAY_MSEC) / 1000)
        # print(f"The value of {variable_name} is {result}")
        return {variable_name: result}

    # Set the name of the function dynamically
    operation_function.__name__ = f"calc_{variable_name}"

    return operation_function


def create_claculation_agent(operations):
    fields = {operation['name']: float for operation in operations}
    OperationsGraphState = TypedDict('OperationsGraphState', fields)
    workflow = StateGraph(OperationsGraphState)
    for operation in operations:
        variable_name = operation["name"]
        op1 = operation["op1"]
        op2 = operation["op2"]
        if operation["operation"] != "parentheses":
            if isinstance(op1, str) and not op1.startswith("E"):
                op1 = float(op1) if '.' in op1 else int(op1)
            if isinstance(op2, str) and not op2.startswith("E"):
                op2 = float(op2) if '.' in op2 else int(op2)
        node_function = create_operation_function(OperationsGraphState, variable_name, operation["operation"], op1, op2)
        workflow.add_node(node_function.__name__, node_function)
        operation_has_no_dependencies = True
        if operation["operation"] != "parentheses":
            if isinstance(op1, str) and isinstance(op2, str):
                workflow.add_edge([f"calc_{op1}", f"calc_{op2}"], node_function.__name__)
                operation_has_no_dependencies = False
            else:
                if isinstance(op1, str):
                    workflow.add_edge(f"calc_{op1}", node_function.__name__)
                    operation_has_no_dependencies = False
                if isinstance(op2, str):
                    workflow.add_edge(f"calc_{op2}", node_function.__name__)
                    operation_has_no_dependencies = False
        if operation_has_no_dependencies:
            workflow.add_edge(START, node_function.__name__)
    calc_operations_agent = workflow.compile()
    return calc_operations_agent


def plan(state: ExpressionGraphState):
    operations = state["operations"]
    calc_operations_agent = create_claculation_agent(operations)
    last_variable_index = len(operations)-1
    result_variable_name = f"E{last_variable_index}"
    time.sleep(random.uniform(MIN_DELAY_MSEC, MAX_DELAY_MSEC) / 1000)
    return {"calc_operations_agent": str(id(calc_operations_agent)), "result_variable_name": result_variable_name}


def execute(state: ExpressionGraphState):
    operations = state["operations"]
    calc_operations_agent = create_claculation_agent(operations)

    output = calc_operations_agent.invoke(input={"E0": None})
    result = output[state["result_variable_name"]]
    return {"result": result, "iteration": state["iteration"]+1}


def validate(state: ExpressionGraphState):
    try:
        # Evaluate the mathematical expression
        calculated_result = eval(state["expression"])

        # Compare the calculated result to the provided number
        is_result_correct = (calculated_result == state["result"])
    except (SyntaxError, ZeroDivisionError, NameError):
        # Handle invalid expressions or errors during evaluation
        is_result_correct = False
    time.sleep(random.uniform(MIN_DELAY_MSEC, MAX_DELAY_MSEC) / 1000)
    return {"is_result_correct": is_result_correct}


def should_finish(state: ExpressionGraphState):
    iteration = state["iteration"]
    if state["is_result_correct"]:
        return "finish"
    if iteration > 2:
        raise Exception("Unable to calculate expression")
    # print(f"Iteration {iteration}: failed to create correct result")
    return "continue"


def calculate_expression(expression: str) -> float:
    # print("Calculate the following expression: " + expression)
    if is_valid_math_expression(expression):
        workflow = StateGraph(ExpressionGraphState)
        workflow.add_node("decompose", decompose)
        workflow.add_node("plan", plan)
        workflow.add_node("execute", execute)
        workflow.add_node("validate", validate)
        workflow.add_edge(START, "decompose")
        workflow.add_edge("decompose", "plan")
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", "validate")
        workflow.add_conditional_edges(
            "validate",
            should_finish,
            {
                "finish": END,
                "continue": "decompose",
            },
        )
        langgraph = workflow.compile()
        output = langgraph.invoke(
            input={"expression": expression, "iteration": 0}
        )
        result = output["result"]
        time.sleep(random.uniform(MIN_DELAY_MSEC, MAX_DELAY_MSEC) / 1000)
        # print(f"The result of {expression} is: {result}")
        return result
    raise Exception("Invalid math expression")


# Function to run Langgraph
def run_langgraph():
    expression = "3+(1+2+3/3)*5+6/(2*5-7)"
    calculate_expression(expression)


# Run outside of the test class and set up logging
def setup_logging_and_run_langgraph():
    """Initialize logging and run Langgraph test."""
    agent_analytics_sdk.initialize_observability(
        config=LogExporterConfig(log_filename=LOG_FILENAME)
    )
    run_langgraph()


# Unit Testing Class
class TestLangGraph(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # This method runs once before all tests in this class.
        setup_logging_and_run_langgraph()

    @classmethod
    def tearDownClass(cls):
        # This method runs once after all tests in this class.
        log_dir = os.path.dirname(LOG_FILE_PATH)
        if os.path.exists(log_dir):
            shutil.rmtree(log_dir)

    def _load_spans(self):
        """"Load spans from log file."""
        # This method will be activated only we have validated log file generation
        # Parse the spans from the log file only once
        if not hasattr(TestLangGraph, 'spans'):
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

    def test_01_workflow_span_exists(self):
        """Verify at least one LangGraph.workflow span exists."""
        self._load_spans()
        workflow_spans = [span for span in self.spans if span['name'] == 'LangGraph.workflow']
        self.assertGreaterEqual(len(workflow_spans), 1, "No LangGraph.workflow spans found.")

    def test_02_task_span_count(self):
        """Check if there are 5 LangGraph.task spans."""
        self._load_spans()
        task_span_count = sum(1 for span in self.spans if span['name'] == 'LangGraph.task')
        self.assertEqual(task_span_count, 5, f"Expected 5 LangGraph.task spans, found {task_span_count}.")

    def test_03_graph_structure_in_task_spans(self):
        """Ensure all LangGraph.task spans contain a valid graph_structure attribute."""
        self._load_spans()
        task_spans = [span for span in self.spans if span['name'] == 'LangGraph.task']
        for task_span in task_spans:
            self.assertIn(
                'graph_structure', task_span['attributes'],
                f"Missing graph_structure in LangGraph.task span: {task_span}"
            )
            graph_structure = task_span['attributes']['graph_structure']
            try:
                json.loads(graph_structure)  # Check if it's a valid JSON string
            except json.JSONDecodeError:
                self.fail(f"Invalid JSON in graph_structure for span: {task_span}")


class TestLangGraphUtils(unittest.TestCase):
    def test__get_action_from_func(self):
        from typing import Optional
        from datetime import datetime
        from agent_analytics_common.interfaces.action import ActionKind, ActionCode
        from agent_analytics.instrumentation.reportable import ReportableAction
        from agent_analytics.instrumentation.utils.common import _get_action_from_func

        def my_mynode_func(
            a1: datetime,
            /,
            a2: int,
            a3: Optional[int],
            a4: int = 42,
            *a5: str,
            a6,
            **a7,
        ) -> int:
            """Test function for action creation."""
            pass

        action = _get_action_from_func(my_mynode_func, kind=ActionKind.TOOL)

        # Verify it's a ReportableAction
        self.assertIsInstance(action, ReportableAction)

        # Verify action properties
        self.assertEqual(action.kind, ActionKind.TOOL)
        self.assertEqual(action.name, "my_mynode_func")
        self.assertEqual(action.description, "Test function for action creation.")

        # Verify code is an ActionCode instance
        self.assertIsInstance(action.code, ActionCode)
        self.assertEqual(action.code.language, "python")

        # Line number will vary based on where function is defined
        self.assertIn("my_mynode_func", action.code.id)
        self.assertIn("test_langgraph_instrumentation", action.code.id)

        # Verify input schema (stored as JSON string in ActionCode)
        expected_input_schema = {
            "a1": {
                "annotation": "<class 'datetime.datetime'>",
                "default": None,
                "kind": "POSITIONAL_ONLY"
            },
            "a2": {
                "annotation": "<class 'int'>",
                "default": None,
                "kind": "POSITIONAL_OR_KEYWORD"
            },
            "a3": {
                "annotation": "typing.Optional[int]",
                "default": None,
                "kind": "POSITIONAL_OR_KEYWORD"
            },
            "a4": {
                "annotation": "<class 'int'>",
                "default": "42",
                "kind": "POSITIONAL_OR_KEYWORD"
            },
            "a5": {
                "annotation": "<class 'str'>",
                "default": None,
                "kind": "VAR_POSITIONAL"
            },
            "a6": {
                "annotation": None,
                "default": None,
                "kind": "KEYWORD_ONLY"
            },
            "a7": {
                "annotation": None,
                "default": None,
                "kind": "VAR_KEYWORD"
            }
        }

        # Parse the JSON string from ActionCode
        actual_input_schema = json.loads(action.code.input_schema)
        self.assertEqual(actual_input_schema, expected_input_schema)

        # Verify output schema
        expected_output_schema = "<class 'int'>"
        self.assertEqual(action.code.output_schema, expected_output_schema)

        # Verify OTEL attributes can be generated
        otel_attributes = action.to_otel_attributes()
        self.assertIn("gen_ai.action.kind", otel_attributes)
        self.assertIn("gen_ai.action.code.id", otel_attributes)
        self.assertIn("gen_ai.action.code.language", otel_attributes)
        self.assertIn("gen_ai.action.code.input_schema", otel_attributes)
        self.assertIn("gen_ai.action.code.output_schema", otel_attributes)
        self.assertIn("gen_ai.action.name", otel_attributes)
        self.assertIn("gen_ai.action.description", otel_attributes)
        self.assertIn("gen_ai.action.id", otel_attributes)

        self.assertEqual(otel_attributes["gen_ai.action.kind"], "tool")
        self.assertEqual(otel_attributes["gen_ai.action.name"], "my_mynode_func")
        self.assertEqual(otel_attributes["gen_ai.action.code.language"], "python")

        # Verify it has ReportableElement methods
        self.assertTrue(hasattr(action, 'prepare_attribute_value'))
        self.assertTrue(hasattr(action, 'report'))


if __name__ == "__main__":
    # Run the tests
    unittest.main()
