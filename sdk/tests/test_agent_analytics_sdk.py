import unittest
from unittest.mock import patch

from agent_analytics.instrumentation import agent_analytics_sdk
from agent_analytics.instrumentation.configs import CustomExporterConfig
from opentelemetry.sdk.trace.export import SpanExporter


class TestAgentAnalyticsSdk(unittest.TestCase):
    def test_custom_exporter(self):
        with self.assertRaises(ValueError) as ctx1:
            config = CustomExporterConfig()
            agent_analytics_sdk.initialize_observability(
                config=config,
                custom_exporter=None,
            )
        self.assertIn("custom_exporter must be provided", str(ctx1.exception))

        with self.assertRaises(ValueError) as ctx1:
            config = CustomExporterConfig()
            agent_analytics_sdk.initialize_logging(
                tracer_type=agent_analytics_sdk.SUPPORTED_TRACER_TYPES.CUSTOM,
                config=config,
                custom_exporter=None,
            )
        self.assertIn("custom_exporter must be provided", str(ctx1.exception))

        class MyCustomExporter(SpanExporter):
            pass

        with patch(
            "agent_analytics.instrumentation.agent_analytics_sdk.Traceloop"
        ) as mock_traceloop:
            custom_exporter = MyCustomExporter()
            config = CustomExporterConfig()
            agent_analytics_sdk.initialize_observability(
                config=config,
                custom_exporter=custom_exporter,
            )
            mock_traceloop.init.assert_called_once()
            args, kwargs = mock_traceloop.init.call_args
            self.assertEqual(kwargs["exporter"], custom_exporter)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
