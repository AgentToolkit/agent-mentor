"""
Spans resource for the AgentOps SDK

Provides methods for querying span data.
"""

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator
from agent_analytics.sdk.models import Span


class SpansResource:
    """
    API for working with spans.

    This resource provides methods to query and retrieve span data
    from the analytics platform.
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the spans resource.

        Args:
            data_manager: The data manager instance
        """
        self._data_manager = data_manager

    async def fetch(
        self,
        trace_id: str,
        names: list[str] | None = None,
        min_duration: float | None = None,
        max_duration: float | None = None
    ) -> list[Span]:
        """
        List all spans for a specific trace with optional filtering.

        Args:
            trace_id: The ID of the trace to get spans for
            names: Optional list of span names to filter by
            min_duration: Optional minimum duration filter (in seconds)
            max_duration: Optional maximum duration filter (in seconds)

        Returns:
            List of Span objects

        Example:
            # List all spans
            spans = await client.spans.fetch(trace_id="trace-123")

            # Filter by names
            spans = await client.spans.fetch(
                trace_id="trace-123",
                names=["span-a", "span-b"]
            )

            # Filter by duration
            spans = await client.spans.fetch(
                trace_id="trace-123",
                min_duration=0.5,
                max_duration=5.0
            )
        """
        has_filters = names or min_duration is not None or max_duration is not None

        if not has_filters:
            # Use existing optimized method
            span_composites = await self._data_manager.get_spans(trace_id)
        else:
            # Use search with filters
            query = {
                "trace_id": QueryFilter(operator=QueryOperator.EQUAL, value=trace_id)
            }

            if names:
                query["name"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=names)

            if min_duration is not None:
                query["duration"] = QueryFilter(operator=QueryOperator.GREATER_EQUAL, value=min_duration)

            if max_duration is not None:
                if "duration" not in query:
                    query["duration"] = QueryFilter(operator=QueryOperator.LESS_EQUAL, value=max_duration)

            span_composites = await self._data_manager.search(
                element_type=BaseSpanComposite,
                query=query
            )

            # Apply max_duration filter in Python if both min and max are specified
            if min_duration is not None and max_duration is not None:
                span_composites = [s for s in span_composites if s.duration is not None and s.duration <= max_duration]

        # Convert to SDK models
        return [self._to_sdk_model(sc) for sc in span_composites]

    async def get(self, span_id: str) -> Span | None:
        """
        Get a specific span by ID.

        Args:
            span_id: The unique identifier of the span

        Returns:
            Span object if found, None otherwise

        Example:
            span = await client.spans.get("span-123")
        """
        # Get span using the internal API
        span_composite = await BaseSpanComposite.get_by_id(
            data_manager=self._data_manager,
            id=span_id
        )

        if span_composite is None:
            return None

        return self._to_sdk_model(span_composite)

    def _to_sdk_model(self, composite: BaseSpanComposite) -> Span:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal span composite object

        Returns:
            SDK Span model
        """
        return Span(_composite=composite)
