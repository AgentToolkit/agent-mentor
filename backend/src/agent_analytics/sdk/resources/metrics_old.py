"""
Metrics resource for the AgentOps SDK

Provides methods for creating and querying metrics.
"""

from typing import Any

from agent_analytics_common.interfaces.metric import (
    MetricType as InternalMetricType,
)

from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.metric import (
    BaseDistributionMetric,
    BaseNumericMetric,
    BaseStringMetric,
    MetricComposite,
)
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.sdk.models import Metric, MetricType, Span


class MetricsResource:
    """
    API for working with metrics.

    This resource provides methods to create and query metrics
    associated with traces and spans.
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the metrics resource.

        Args:
            data_manager: The data manager instance
        """
        self._data_manager = data_manager

    async def create(
        self,
        trace_id: str,
        name: str,
        value: Any,
        metric_type: MetricType | None = None,
        span_id: Span | str | None = None,
        units: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        plugin_id: str | None = None
    ) -> Metric:
        """
        Create a new metric associated with a trace.

        The metric will be owned by the trace and optionally related
        to a specific span.

        Args:
            trace_id: ID of the trace this metric belongs to
            name: Display name for the metric
            value: The metric value (type depends on metric_type)
            metric_type: Type of metric. If not specified, will be inferred
                        from the value type.
            span_id: Optional Span object or span ID (as string) to relate this metric to.
                    Can pass either a Span object or just the span ID string.
            units: Units of measurement
            description: Description of what this metric measures
            tags: List of tags for categorization
            plugin_id: Optional identifier of the plugin that created this metric

        Returns:
            The created Metric object

        Example:
            # Create a numeric metric
            metric = await client.metrics.create(
                trace_id="trace-123",
                name="quality_score",
                value=0.95,
                units="score",
                description="Overall quality score for the trace"
            )

            # Create a metric related to a span (using span ID)
            metric = await client.metrics.create(
                trace_id="trace-123",
                span_id="span-456",  # Pass span ID as string
                name="span_duration",
                value=1.23,
                units="seconds"
            )

            # Or pass the Span object directly if you already have it
            spans = await client.spans.fetch(trace_id="trace-123")
            metric = await client.metrics.create(
                trace_id="trace-123",
                span_id=spans[0],  # Pass the Span object
                name="span_duration",
                value=1.23,
                units="seconds"
            )

            # Create a distribution metric
            metric = await client.metrics.create(
                trace_id="trace-123",
                name="tool_usage",
                value={"tool_a": 0.5, "tool_b": 0.3, "tool_c": 0.2},
                metric_type=MetricType.DISTRIBUTION
            )
        """
        # Get the trace
        trace = await BaseTraceComposite.get_by_id(
            data_manager=self._data_manager,
            id=trace_id
        )

        if trace is None:
            raise ValueError(f"Trace not found: {trace_id}")

        # Handle span_id parameter - can be Span object or span ID string
        related_to = None
        span_id_for_result = None

        if span_id is not None:
            from agent_analytics.core.data.span_data import BaseSpanData
            from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils

            if isinstance(span_id, Span):
                # User passed a Span object - extract the composite and use it directly
                span_composite = span_id._composite
                related_to = [span_composite]
                span_id_for_result = span_id.id
            elif isinstance(span_id, str):
                # User passed a span ID - use tuple format to avoid fetching
                span_type = TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseSpanData)
                related_to = ([span_id], [span_type])
                span_id_for_result = span_id
            else:
                raise TypeError(f"span_id must be a Span object or string ID, got {type(span_id)}")

        # Infer metric type if not specified
        if metric_type is None:
            metric_type = self._infer_metric_type(value)

        # Create the appropriate metric builder
        metric_builder = self._create_metric_builder(
            metric_type=metric_type,
            name=name,
            value=value,
            units=units,
            description=description,
            tags=tags or [],
            plugin_id=plugin_id
        )

        # Set the root and related_to
        metric_builder.root = trace
        if related_to is not None:
            metric_builder.related_to = related_to

        # Store the metric
        stored_metric = await metric_builder.store(self._data_manager)

        # Convert to SDK model
        return self._to_sdk_model(stored_metric, trace_id, span_id_for_result)

    async def create_many(
        self,
        trace_id: str,
        metrics: list[dict[str, Any]]
    ) -> list[Metric]:
        """
        Create multiple metrics at once for better performance.

        Args:
            trace_id: ID of the trace these metrics belong to
            metrics: List of metric definitions. Each dict should contain:
                    - name: str (required)
                    - value: Any (required)
                    - metric_type: MetricType (optional, inferred if not provided)
                    - span_id: Span | str (optional) - Span object or span ID
                    - units: str (optional)
                    - description: str (optional)
                    - tags: list[str] (optional)
                    - plugin_id: str (optional)

        Returns:
            List of created Metric objects

        Example:
            metrics = await client.metrics.create_many(
                trace_id="trace-123",
                metrics=[
                    {
                        "name": "metric1",
                        "value": 0.95,
                        "units": "score"
                    },
                    {
                        "name": "metric2",
                        "value": "SUCCESS",
                        "metric_type": MetricType.STRING
                    }
                ]
            )
        """
        # Get the trace
        trace = await BaseTraceComposite.get_by_id(
            data_manager=self._data_manager,
            id=trace_id
        )

        if trace is None:
            raise ValueError(f"Trace not found: {trace_id}")

        # Build all metric builders
        metric_builders = []
        span_ids = {}  # Track span_id for each metric

        for i, metric_def in enumerate(metrics):
            # Extract parameters
            name = metric_def.get("name")
            value = metric_def.get("value")
            metric_type = metric_def.get("metric_type")
            span_id_param = metric_def.get("span_id")  # Can be Span object or string ID
            units = metric_def.get("units")
            description = metric_def.get("description")
            tags = metric_def.get("tags", [])
            plugin_id = metric_def.get("plugin_id")

            if not name or value is None:
                raise ValueError(f"Metric at index {i} missing required fields: name, value")

            # Infer metric type if not specified
            if metric_type is None:
                metric_type = self._infer_metric_type(value)

            # Handle span_id parameter - can be Span object or span ID string
            related_to = None
            span_id_for_result = None

            if span_id_param is not None:
                from agent_analytics.core.data.span_data import BaseSpanData
                from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils

                if isinstance(span_id_param, Span):
                    # User passed a Span object - extract the composite
                    span_composite = span_id_param._composite
                    related_to = [span_composite]
                    span_id_for_result = span_id_param.id
                elif isinstance(span_id_param, str):
                    # User passed a span ID - use tuple format to avoid fetching
                    span_type = TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseSpanData)
                    related_to = ([span_id_param], [span_type])
                    span_id_for_result = span_id_param
                else:
                    raise TypeError(f"span_id at index {i} must be a Span object or string ID, got {type(span_id_param)}")

                span_ids[i] = span_id_for_result

            # Create metric builder
            metric_builder = self._create_metric_builder(
                metric_type=metric_type,
                name=name,
                value=value,
                units=units,
                description=description,
                tags=tags,
                plugin_id=plugin_id
            )

            metric_builder.root = trace
            if related_to is not None:
                metric_builder.related_to = related_to
            metric_builders.append(metric_builder)

        # Bulk store all metrics
        stored_metrics = await BaseNumericMetric.bulk_store(
            data_manager=self._data_manager,
            base_metrics=metric_builders
        )

        # Convert to SDK models
        return [
            self._to_sdk_model(m, trace_id, span_ids.get(i))
            for i, m in enumerate(stored_metrics)
        ]

    async def list_for_trace(self, trace_id: str) -> list[Metric]:
        """
        Get all metrics owned by a specific trace.

        Args:
            trace_id: The ID of the trace

        Returns:
            List of Metric objects

        Example:
            metrics = await client.metrics.list_for_trace("trace-123")
        """
        # Query metrics using the internal API
        metric_composites = await BaseTraceComposite.get_all_metrics_for_trace(
            data_manager=self._data_manager,
            trace_id=trace_id
        )

        # Convert to SDK models
        return [self._to_sdk_model(mc, trace_id) for mc in metric_composites]

    async def list_for_span(self, span_id: str) -> list[Metric]:
        """
        Get all metrics related to a specific span.

        Args:
            span_id: The ID of the span

        Returns:
            List of Metric objects

        Example:
            metrics = await client.metrics.list_for_span("span-123")
        """
        from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator

        # Query metrics by searching for those with this span_id in related_to_ids array
        # This avoids needing to fetch the span object (which would fail with JaegerStore)
        metric_composites = await self._data_manager.search(
            element_type=MetricComposite,
            query={"related_to_ids": QueryFilter(operator=QueryOperator.ARRAY_CONTAINS, value=span_id)}
        )

        # Get trace_id from the first metric if available
        # (all metrics related to the same span should have the same trace)
        trace_id = metric_composites[0].root_id if metric_composites else None

        # Convert to SDK models
        return [
            self._to_sdk_model(mc, trace_id or mc.root_id, span_id)
            for mc in metric_composites
        ]

    def _infer_metric_type(self, value: Any) -> MetricType:
        """
        Infer the metric type from the value.

        Args:
            value: The metric value

        Returns:
            The inferred MetricType
        """
        if isinstance(value, (int, float)):
            return MetricType.NUMERIC
        elif isinstance(value, str):
            return MetricType.STRING
        elif isinstance(value, dict):
            return MetricType.DISTRIBUTION
        else:
            # Default to string and convert
            return MetricType.STRING

    def _create_metric_builder(
        self,
        metric_type: MetricType,
        name: str,
        value: Any,
        units: str | None,
        description: str | None,
        tags: list[str],
        plugin_id: str | None
    ):
        """
        Create the appropriate metric builder based on type.

        Args:
            metric_type: The type of metric to create
            name: Metric name
            value: Metric value
            units: Units of measurement
            description: Metric description
            tags: List of tags
            plugin_id: Plugin identifier

        Returns:
            The appropriate metric builder instance
        """
        common_params = {
            "name": name,
            "value": value,
            "units": units,
            "description": description,
            "tags": tags,
            "plugin_metadata_id": plugin_id
        }

        if metric_type == MetricType.NUMERIC:
            return BaseNumericMetric(**common_params)
        elif metric_type == MetricType.STRING:
            return BaseStringMetric(**common_params)
        elif metric_type == MetricType.DISTRIBUTION:
            return BaseDistributionMetric(**common_params)
        else:
            # Default to string
            return BaseStringMetric(**{**common_params, "value": str(value)})

    def _to_sdk_model(
        self,
        composite: MetricComposite,
        trace_id: str,
        span_id: str | None = None
    ) -> Metric:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal metric composite object
            trace_id: The trace ID
            span_id: Optional span ID

        Returns:
            SDK Metric model
        """
        # Map internal metric type to SDK metric type
        metric_type_map = {
            InternalMetricType.NUMERIC: MetricType.NUMERIC,
            InternalMetricType.STRING: MetricType.STRING,
            InternalMetricType.DISTRIBUTION: MetricType.DISTRIBUTION,
            InternalMetricType.TIME_SERIES: MetricType.TIME_SERIES,
            InternalMetricType.HISTOGRAM: MetricType.HISTOGRAM,
            InternalMetricType.STATISTICS: MetricType.STATISTICS,
        }

        sdk_metric_type = metric_type_map.get(
            composite._data_object.metric_type,
            MetricType.STRING
        )

        return Metric(
            _composite=composite,
            _trace_id=trace_id,
            _span_id=span_id,
            _metric_type=sdk_metric_type
        )
