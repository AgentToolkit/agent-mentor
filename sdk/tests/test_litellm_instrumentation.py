import unittest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from agent_analytics.instrumentation import agent_analytics_sdk
from agent_analytics.instrumentation.configs import CustomExporterConfig
from dotenv import load_dotenv
import os

load_dotenv()


class TestLiteLLMInstrumentation(unittest.TestCase):
    """Test LiteLLM instrumentation to verify suppression logic for OpenAI/Azure."""

    @classmethod
    def setUpClass(cls):
        # Set up in-memory span exporter
        cls.exporter = InMemorySpanExporter()
        config = CustomExporterConfig(
            resource_attributes={"service.name": "test-litellm-service"},
        )
        agent_analytics_sdk.initialize_observability(
            config=config,
            custom_exporter=cls.exporter,
        )

    def tearDown(self):
        # Clear the exporter after each test
        self.exporter.clear()

    def _call_litellm_with_azure(self):
        """Call LiteLLM with Azure OpenAI using azure/ prefix."""
        import litellm

        response = litellm.completion(
            model="azure/gpt-4o",
            base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            messages=[
                {"role": "user", "content": "Say 'Hello' and nothing else."}
            ]
        )
        return response

    def _call_litellm_with_watsonx(self):
        """Call LiteLLM with WatsonX (should NOT be suppressed)."""
        import litellm

        response = litellm.completion(
            model="watsonx/ibm/granite-3-8b-instruct",
            messages=[
                {"role": "user", "content": "Say hello"}
            ]
        )
        return response

    def test_01_litellm_spans_suppressed_with_azure_prefix(self):
        """Verify LiteLLM spans are suppressed when using azure/ model prefix."""
        # Make the call
        self._call_litellm_with_azure()

        # Get all spans
        spans = self.exporter.get_finished_spans()

        # Look for LiteLLM spans (should not exist)
        litellm_spans = [
            span for span in spans
            if span.name == "chat.completions.create"
            and span.attributes.get("gen_ai.system") == "litellm"
        ]

        # LiteLLM spans should be suppressed
        self.assertEqual(
            len(litellm_spans), 0,
            f"Found {len(litellm_spans)} LiteLLM spans, but they should be suppressed for Azure calls."
        )

        # OpenAI spans should exist
        openai_spans = [
            span for span in spans
            if span.name == "openai.chat"
        ]

        self.assertGreater(
            len(openai_spans), 0,
            "Expected at least one OpenAI span for Azure call."
        )

    def test_02_no_duplicate_spans(self):
        """Verify there are no duplicate LLM spans for the same request."""
        # Make a call
        self._call_litellm_with_azure()

        # Get all spans
        spans = self.exporter.get_finished_spans()

        # Get all LLM-related spans
        llm_spans = [
            span for span in spans
            if "gen_ai.prompt.0.content" in span.attributes
        ]

        # Group spans by their prompt content
        prompts = {}
        for span in llm_spans:
            prompt = span.attributes.get("gen_ai.prompt.0.content", "")
            if prompt not in prompts:
                prompts[prompt] = []
            prompts[prompt].append(span)

        # Each unique prompt should have exactly one span
        for prompt, span_list in prompts.items():
            self.assertEqual(
                len(span_list), 1,
                f"Found {len(span_list)} spans for the same prompt. Expected only 1. Prompt: {prompt[:50]}..."
            )

    def test_03_litellm_spans_created_for_watsonx(self):
        """Verify LiteLLM spans ARE created when using WatsonX (not suppressed)."""
        # Make a call to WatsonX through LiteLLM
        # This will fail the test if WatsonX is not configured
        self._call_litellm_with_watsonx()

        # Get all spans
        spans = self.exporter.get_finished_spans()

        # Look for LiteLLM spans (should exist for WatsonX)
        litellm_spans = [
            span for span in spans
            if span.name == "chat.completions.create"
            and span.attributes.get("gen_ai.system") == "litellm"
        ]

        # LiteLLM spans should NOT be suppressed for WatsonX
        self.assertGreater(
            len(litellm_spans), 0,
            "Expected at least one LiteLLM span for WatsonX calls (suppression should NOT apply)."
        )


if __name__ == "__main__":
    unittest.main()
