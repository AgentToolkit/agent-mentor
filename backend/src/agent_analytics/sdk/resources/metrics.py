"""
Metrics resource for the AgentOps SDK

Provides methods for creating and querying metrics.
"""

from typing import Any

from ibm_agent_analytics_common.interfaces.metric import (
    MetricType as InternalMetricType,
)

from agent_analytics.core.data_composite.metric import (
    BaseDistributionMetric,
    BaseNumericMetric,
    BaseStringMetric,
    MetricComposite,
)
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.sdk.models import Metric, MetricType
from agent_analytics.sdk.resources.base_relatable import RelatableElementsResource


class MetricsResource(RelatableElementsResource[MetricComposite, Metric]):
    """
    API for working with metrics.

    This resource provides methods to create and query metrics
    associated with traces, trace groups, or any other element.
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the metrics resource.

        Args:
            data_manager: The data manager instance
        """
        super().__init__(data_manager)

    def _get_composite_class(self) -> type[MetricComposite]:
        """Get the MetricComposite class"""
        return MetricComposite

    def _get_builder_class(self) -> type:
        """Get the BaseNumericMetric class (used for bulk_store)"""
        return BaseNumericMetric

    def _get_bulk_store_param_name(self) -> str:
        """Override to return correct parameter name for bulk_store"""
        return "base_metrics"

    def _validate_create_params(self, **kwargs):
        """
        Validate metric creation parameters.

        Args:
            **kwargs: Parameters including name, description, value

        Raises:
            ValueError: If required parameters are missing
        """
        if not kwargs.get("name"):
            raise ValueError("Metric name is required")

        if "value" not in kwargs:
            raise ValueError("Metric value is required")

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

    def _create_builder(self, **kwargs) -> Any:
        """
        Create a metric builder instance.

        Args:
            **kwargs: Parameters including name, value, units, etc.

        Returns:
            Metric builder instance
        """
        metric_type = kwargs.get("metric_type")
        value = kwargs["value"]

        # Infer metric type if not specified
        if metric_type is None:
            metric_type = self._infer_metric_type(value)

        return self._create_metric_builder(
            metric_type=metric_type,
            name=kwargs["name"],
            value=value,
            units=kwargs.get("units"),
            description=kwargs.get("description"),
            tags=kwargs.get("tags", []),
            plugin_id=kwargs.get("plugin_metadata_id")
        )

    def _to_sdk_model(self, composite: MetricComposite, **kwargs) -> Metric:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal metric composite object
            **kwargs: Additional parameters (root, related_to, etc.)

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

        # Extract root_id and related IDs
        root_id = composite.root_id
        related_ids = composite.related_to_ids

        # Try to determine span_id from related elements (for backward compatibility)
        span_id = None
        if related_ids and len(related_ids) > 0:
            # Check if first related element is a span
            related_types = composite.related_to_types
            if related_types and "span" in related_types[0].lower():
                span_id = related_ids[0]

        return Metric(
            _composite=composite,
            _trace_id=root_id or "",
            _span_id=span_id,
            _metric_type=sdk_metric_type
        )

    # Convenience methods for backward compatibility

    async def create(
        self,
        owner: Any,
        name: str,
        value: Any,
        metric_type: MetricType | None = None,
        related_to: list[Any] | tuple[list[str], list[str]] | None = None,
        units: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        plugin_id: str | None = None
    ) -> Metric:
        """
        Create a new metric associated with an owner element.

        The metric will be owned by the owner (trace, trace group, etc.) and optionally
        related to other specific elements.

        Args:
            owner: Owner element this metric belongs to (Trace, TraceGroup, or any Element)
            name: Display name for the metric
            value: The metric value (type depends on metric_type)
            metric_type: Type of metric. If not specified, will be inferred from value type.
            related_to: Optional elements to relate this metric to (e.g., Span, Task).
                       Can be list of Element objects or tuple of ([ids], [types])
            units: Units of measurement
            description: Description of what this metric measures
            tags: List of tags for categorization
            plugin_id: Optional identifier of the plugin that created this metric

        Returns:
            The created Metric object

        Example:
            # Create a numeric metric for a trace
            metric = await client.metrics.create(
                owner=trace,
                name="quality_score",
                value=0.95,
                units="score",
                description="Overall quality score for the trace"
            )

            # Create a metric related to a span
            metric = await client.metrics.create(
                owner=trace,
                name="span_duration",
                related_to=[span],
                value=1.23,
                units="seconds"
            )

            # Create a metric for a trace group
            metric = await client.metrics.create(
                owner=trace_group,
                name="avg_latency",
                value=250.5,
                units="ms"
            )

            # Create a distribution metric
            metric = await client.metrics.create(
                owner=trace,
                name="tool_usage",
                value={"tool_a": 0.5, "tool_b": 0.3, "tool_c": 0.2},
                metric_type=MetricType.DISTRIBUTION
            )
        """
        return await super().create(
            owner=owner,
            name=name,
            description=description,
            related_to=related_to,
            tags=tags,
            plugin_id=plugin_id,
            value=value,
            metric_type=metric_type,
            units=units
        )

    async def create_many(
        self,
        owner: Any,
        metrics: list[dict[str, Any]]
    ) -> list[Metric]:
        """
        Create multiple metrics at once for better performance.

        Args:
            owner: Owner element these metrics belong to
            metrics: List of metric definitions. Each dict should contain:
                    - name: str (required)
                    - value: Any (required)
                    - metric_type: MetricType (optional, inferred if not provided)
                    - related_to: list[Element] or tuple[list[str], list[str]] (optional)
                    - units: str (optional)
                    - description: str (optional)
                    - tags: list[str] (optional)
                    - plugin_id: str (optional)

        Returns:
            List of created Metric objects

        Example:
            metrics = await client.metrics.create_many(
                owner=trace,
                metrics=[
                    {"name": "metric1", "value": 0.95, "units": "score"},
                    {"name": "metric2", "value": "SUCCESS", "metric_type": MetricType.STRING}
                ]
            )
        """
        return await super().create_many(owner=owner, elements=metrics)

    # Backward-compatible method names

    async def list_for_trace(self, trace: Any) -> list[Metric]:
        """
        Get all metrics owned by a specific trace.

        Args:
            trace: The trace (wrapper, composite, or ID string)

        Returns:
            List of Metric objects

        Example:
            metrics = await client.metrics.list_for_trace(trace)
            metrics = await client.metrics.list_for_trace("trace-123")
        """
        return await self.fetch_by_owner(trace)

    async def list_for_span(self, span: Any) -> list[Metric]:
        """
        Get all metrics related to a specific span.

        Args:
            span: The span (wrapper, composite, or ID string)

        Returns:
            List of Metric objects

        Example:
            metrics = await client.metrics.list_for_span(span)
            metrics = await client.metrics.list_for_span("span-456")
        """
        return await self.fetch_by_related(span)
