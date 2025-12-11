import time
from typing import Any

from agent_analytics.extensions.spans_processing.span_traverser import SpanTreeTraverser


class SpanProcessingOrchestrator:
    """Main class that orchestrates the whole span processing."""

    def __init__(self):
        """Initialize the orchestrator."""
        self.traverser = SpanTreeTraverser()

    def register_processor(self, processor):
        """Registers different processors (visitors) for different missions. 
        Delegates the registration to traverser which will actually call the processors on each span"""
        self.traverser.register_processor(processor)

    def process_spans(self , spans):
        """
        Process a list of spans.
        
        Args:
            spans: The spans to process
            
        Returns:
            Context map with processing results and metadata
        """
        # Initialize context
        context: dict[str, Any] = {}

        # Record processing start time
        start_time = time.time()
        context["processing_start_time"] = start_time

        #TODO: add any kind of relevant information to the context if needed

        # Traverse spans
        context = self.traverser.traverse(spans, context)

        # Record processing end time and duration if needed
        end_time = time.time()
        context["processing_end_time"] = end_time
        context["processing_duration_ms"] = (end_time - start_time) * 1000

        return context
