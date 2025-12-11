from typing import Any

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.extensions.spans_processing.span_processor import SpanProcessor, VisitPhase


class SpanTreeTraverser:
    """Core traversal engine that walks the span tree and applies processors."""
    """Traversal Algorithm:

        Builds a map of parent IDs to child spans
        Identifies root spans (those without parents in our span set)
        Performs depth-first traversal of each root span
        Processes spans in two phases: before and after children
        Handles cycling in the span graph using a visited set ? (is it needed or no cycles can exist?)
        
        context is for any shared information - if needed
    """

    def __init__(self):
        """Initialize a new traverser."""
        self.processors: list[SpanProcessor] = []
        self.visited_span_ids: set[str] = set()

    def register_processor(self, processor):
        """
        Register a processor to be applied during traversal.
        
        Args:
            processor: The processor to register
        """
        self.processors.append(processor)

    def traverse(self, spans: list[BaseSpanComposite], context: dict[str, Any]):
        """
        Traverse a list of spans as a tree, applying all registered processors.
        
        Args:
            spans: The list of spans to traverse
            context: Optional initial context (will be created if None)
            
        Returns:
            The final context after traversal
        """
        # Initialize context if not provided
        if context is None:
            context = {}

        # Reset visited set
        self.visited_span_ids.clear()

        # Build a map of spans by ID for easy lookup
        span_map = {span.context.span_id: span for span in spans}

        # Add span map to context
        context["span_map"] = span_map

        # Build parent-child relationships
        children_map = self._build_children_map(spans)

        # Find root spans (those without a parent in our span set)
        root_spans = [span for span in spans
                      if span.parent_id is None or span.parent_id not in span_map]

        # Sort root spans by start time - in case we traverse ordered by time
        root_spans.sort(key=lambda span: span.start_time)

        # Traverse each root span
        for root_span in root_spans:
            self._traverse_span(root_span, children_map, context)

        # Call after_traversal on all processors
        self._finish_traversal(context)

        return context

    def _build_children_map(self, spans: list[BaseSpanComposite]):
        """
        Build a map of parent span ID to list of child spans.
        
        Args:
            spans: The list of spans
            
        Returns:
            Map of parent ID to list of child spans
        """
        children_map: dict[str, list[Any]] = {}

        for span in spans:
            if span.parent_id is not None:
                if span.parent_id not in children_map:
                    children_map[span.parent_id] = []
                children_map[span.parent_id].append(span)

        return children_map

    def _traverse_span(self, span: BaseSpanComposite, children_map, context: dict[str, Any]):
        """
        Recursively traverse a span and its children, applying processors.
        
        Args:
            span: The span to traverse
            children_map: Map of parent span ID to list of child spans
            context: Shared context
        """
        # Skip if already visited
        if span.context.span_id in self.visited_span_ids:
            return

        # Mark as visited
        self.visited_span_ids.add(span.context.span_id)

        # Apply processors before children
        for processor in self.processors:
            if processor.should_process(span, context):
                try:
                    processor.process(span, VisitPhase.BEFORE_CHILDREN, context)
                except Exception as e:
                    # Log exception but continue processing
                    # print(f"Error processing span {span.context.span_id} (before children): {str(e)}")
                    print(f"Error processing span {span.name} (before children): {str(e)}")

        # Get children for this span
        children = children_map.get(span.context.span_id, [])

        # Sort children by start time - assuming this is the order we want to traverse among children - might need more complex logic?
        children.sort(key=lambda s: s.start_time)

        # Process children
        for child in children:
            self._traverse_span(child, children_map, context)

        # Apply processors after children
        for processor in self.processors:
            if processor.should_process(span, context):
                try:
                    processor.process(span, VisitPhase.AFTER_CHILDREN, context)
                except Exception as e:
                    # Log exception but continue processing
                    print(f"Error processing span {span.name} (after children): {str(e)}")

    def _finish_traversal(self, context: dict[str, Any]):
        """
        Call after_traversal on all processors as needed/if needed.
        
        Args:
            context: Shared context
        """
        for processor in self.processors:
            try:
                processor.after_traversal(context)
            except Exception as e:
                # Log exception but continue processing
                import traceback
                traceback.print_exc()
                print(f"Error in after_traversal for processor {processor.__class__.__name__}: {str(e)}")
