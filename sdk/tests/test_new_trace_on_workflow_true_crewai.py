import unittest
import os
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from agent_analytics.instrumentation import agent_analytics_sdk
from agent_analytics.instrumentation.configs import CustomExporterConfig
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

try:
    from crewai import Agent, Task, Crew, Process
    from crewai.llm import LLM
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


class TestNewTraceOnWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Skip all tests if CrewAI is not available
        if not CREWAI_AVAILABLE:
            raise unittest.SkipTest("CrewAI not available, skipping tests")
        cls.exporter = InMemorySpanExporter()
        config = CustomExporterConfig(
            resource_attributes={"service.name": "test-service"},
            new_trace_on_workflow=True
        )
        agent_analytics_sdk.initialize_observability(
            config=config,
            custom_exporter=cls.exporter,
        )

    def tearDown(self):
        # Clear the exporter
        self.exporter.clear()

    def _create_and_execute_graph(self):
        """Create a simple CrewAI workflow with two execute_tasks invokess."""

        class JsonOutput(BaseModel):
            agent: str
            expected_output: str
            total_tokens: int
            prompt_tokens: int
            completion_tokens: int
            successful_requests: int

        llm = LLM(
            model="azure/gpt-4o",
            base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"]
        )

        # Buiding the crewAI Agent
        data_analyst = Agent(
            role="Data Analyst",
            goal="Analyze market data and extract key insights.",
            backstory="An AI-powered expert in data processing, trend analysis, and forecasting.",
            verbose=False,
            allow_delegation=False,
            llm=llm,
        )

        # Buiding the crewAI Agent
        strategy_advisor = Agent(
            role="Strategy Advisor",
            goal="Develop strategic business recommendations based on data insights.",
            backstory="An AI-driven consultant that translates market trends into actionable strategies.",
            verbose=False,
            allow_delegation=False,
            llm=llm,
        )

        task1 = Task(
            description="Analyze the following market data and summarize key insights:\t{market_data}",
            expected_output="summarized insights in a structured format.",
            agent=data_analyst,
        )

        task2 = Task(
            description="Develop a business strategy based on the analyzed market data.",
            expected_output="Generate actionable business strategies and an implementation plan based on the analyzed trends.",  # noqa: E501
            agent=strategy_advisor,
            output_json=JsonOutput,
        )

        # Running the crewAI
        crew = Crew(
            agents=[data_analyst, strategy_advisor],
            tasks=[task1, task2],
            verbose=False,
            process=Process.sequential,
        )
        data = "Companies are investing more in AI-driven automation for efficiency."
        result = crew.kickoff(inputs={"market_data": data})

        return result

    def test_with_new_trace_on_workflow(self):
        # Run workflow
        self._create_and_execute_graph()

        # Get all spans
        spans = self.exporter.get_finished_spans()

        # Find all spans related to graph invocation
        invoke_spans = [span for span in spans if span.name == "Agent.execute_task"]

        # We should have at least 2 invocation spans from our two invoke calls
        self.assertEqual(
            len(invoke_spans), 2,
            "Expected at least 2 spans for Agent.execute_task"
        )

        # With new_trace_on_workflow=True, each invocation should have its own trace ID
        trace_ids = {span.context.trace_id for span in spans}
        self.assertEqual(
            len(trace_ids), len(invoke_spans) + 1,
            "With new_trace_on_workflow=True, each invoke of agent span should have a unique trace ID"
        )


if __name__ == "__main__":
    unittest.main()
