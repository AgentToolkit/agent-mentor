
import json
from abc import ABC, ABCMeta
from datetime import datetime
from typing import Any, ClassVar, Literal

from ibm_agent_analytics_common.interfaces.metric import (
    AggregatedStats,
    BasicStatsMetric,
    DistributionMetric,
    HistogramMetric,
    Metric,
    MetricScope,
    MetricType,
    NumericInterval,
    NumericMetric,
    StringMetric,
    T,
    TimeSeriesMetric,
)
from pydantic import Field

from agent_analytics.core.data.metric_data import MetricData
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.relatable_element import RelatableElementComposite
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils


def serialize_histogram_data(value: dict[Any, float]) -> dict[str, float]:
    """
    Utility function to serialize histogram data by converting NumericInterval keys to string format.
    
    Args:
        value: Dictionary with NumericInterval or other keys
        
    Returns:
        Dictionary with string keys suitable for storage
    """
    serialized_value = {}
    for interval, val in value.items():
        # Convert NumericInterval to string format
        if isinstance(interval, NumericInterval):
            key = f"{interval.lower_bound}_{interval.upper_bound}"
            serialized_value[key] = val
        else:
            # If it's already a string or other type, convert to string to be safe
            serialized_value[str(interval)] = val
    return serialized_value

class MetricComposite(RelatableElementComposite[MetricData],metaclass=ABCMeta):
    """Composite representation of a Task with related Metrics"""
    # Specify the corresponding data class
    data_class: ClassVar[type[MetricData]] = MetricData

    def __init__(self, data_manager: "DataManager", metric_data: MetricData,*, _token: object = None):
        super().__init__(data_manager, metric_data, _token=_token)

    @property
    def value(self) -> Any:
        return self._data_object.value

    @property
    def units(self) -> str | None:
        return self._data_object.units


    @property
    def timestamp(self) -> str | None:
        return self._data_object.timestamp

    @classmethod
    async def get_by_id(cls, data_manager: "DataManager", id: str):
        """
        Overridden get_by_id method that returns the appropriate concrete Metric subclass
        based on the MetricType stored in the MetricData object.
        """
        data_object = await data_manager.get_by_id(id, cls.data_class)
        if data_object is None:
            return None

        # Determine which concrete class to instantiate based on metric type
        if data_object.type == MetricType.NUMERIC:
            return NumericMetricComposite(data_manager, data_object)
        elif data_object.type == MetricType.DISTRIBUTION:
            return DistributionMetricComposite(data_manager, data_object)
        elif data_object.type == MetricType.STRING:
            return StringMetricComposite(data_manager, data_object)
        elif data_object.metric_type == MetricType.TIME_SERIES:
            return TimeSeriesMetricComposite(data_manager, data_object)
        elif data_object.metric_type == MetricType.HISTOGRAM:
            return HistogramMetricComposite(data_manager, data_object)
        elif data_object.metric_type == MetricType.STATISTICS:
            return BasicStatsMetricComposite(data_manager, data_object)
        else:
            # Default fallback to base class if type is not recognized
            return cls(data_manager, data_object)

    @classmethod
    def get_element_class_for_data(cls, data_object: MetricData) -> type['MetricComposite']:
        """
        Return the appropriate Metric subclass based on the metric_type in the data object
        """
        if data_object.metric_type == MetricType.NUMERIC:
            return NumericMetricComposite
        elif data_object.metric_type == MetricType.STRING:
            return StringMetricComposite
        elif data_object.metric_type == MetricType.DISTRIBUTION:
            return DistributionMetricComposite
        elif data_object.metric_type == MetricType.TIME_SERIES:
            return TimeSeriesMetricComposite
        elif data_object.metric_type == MetricType.HISTOGRAM:
            return HistogramMetricComposite
        elif data_object.metric_type == MetricType.STATISTICS:
            return BasicStatsMetricComposite
        else:
            # Default fallback
            return cls


    @classmethod
    async def create(cls, data_manager: "DataManager",
                element_id: str,
                root: ElementComposite | str | None,
                name: str,
                description: str | None,
                units: str | None,
                value: Any,
                metric_type: MetricType,
                plugin_metadata_id: str | None = None,
                timestamp: str | None = None,
                scope: MetricScope | None = None,
                related_to: list[ElementComposite] | tuple[list[str], list[str]] = None,
                tags: list[str] | None = None,
                **kwargs) -> 'MetricComposite':
        """Factory method to create a new Metric of any type."""
        # Validate type-specific values
        if metric_type == MetricType.NUMERIC:
            value = float(value)
        elif metric_type == MetricType.STRING:
            value = str(value)
        elif metric_type == MetricType.DISTRIBUTION:
            if not isinstance(value, dict):
                raise ValueError("Distribution metrics require a dictionary value")
            value = dict(value)
        elif metric_type == MetricType.HISTOGRAM:
            if not isinstance(value, dict):
                raise ValueError("Histogram metrics require a dictionary value")
            # Validate the histogram keys are NumericInterval objects
            # Serialize NumericInterval keys for storage
            value = serialize_histogram_data(value)

        elif metric_type == MetricType.TIME_SERIES:
            if not isinstance(value, list):
                raise ValueError("Time series metrics require a list of tuples (datetime, value)")
            # No further validation as list can be complex
        elif metric_type == MetricType.STATISTICS:
            if not isinstance(value, dict):
                raise ValueError("Aggregated metrics require a dictionary value")
            # Ensure required keys are present for AggregatedStats
            if 'count' not in value or 'mean' not in value:
                raise ValueError("Aggregated metrics require at minimum 'count' and 'mean' fields")
            value = dict(value)

        else:
            raise ValueError(f"Unsupported metric type: {metric_type}")

        # Common processing for related elements and root
        related_to_ids = []
        related_to_types = []
        root_id = None
        if root is not None:
            if isinstance(root, ElementComposite):
                root_id = root.element_id
            elif isinstance(root, str):
                root_id = root
            else:
                raise TypeError("root must be either an Element object or a string ID")

        if related_to:
            # Check if related_to is a tuple of (ids, types)
            if isinstance(related_to, tuple) and len(related_to) == 2:
                related_to_ids = related_to[0]
                related_to_types = related_to[1]
            # Otherwise process as a list of composite elements
            elif isinstance(related_to, list):
                for element in related_to:
                    # Get the element_id from the element
                    related_to_ids.append(element.element_id)

                    # Get the type name from the element's data object
                    data_type = type(element._data_object)
                    type_name = TypeResolutionUtils.get_fully_qualified_type_name_for_type(data_type)
                    related_to_types.append(type_name)
            else:
                raise TypeError("related_to must be either a list of ElementComposite objects or a tuple of (ids, types) lists")

        # Default timestamp if not provided
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        # Create MetricData object
        metric_data = MetricData(
            element_id=element_id,
            name=name,
            root_id=root_id,
            plugin_metadata_id=plugin_metadata_id,
            description=description,
            units=units,
            value=value,
            metric_type=metric_type,
            timestamp=timestamp,
            scope=scope,
            related_to_ids=related_to_ids,
            related_to_types=related_to_types,
            tags=tags or [],
            attributes=kwargs.get("attributes", {})
        )

        # Get the appropriate concrete class
        concrete_class = cls.get_element_class_for_data(metric_data)

        # Create the metric instance
        metric = concrete_class(data_manager, metric_data, _token=_CREATION_TOKEN)

        # Store the data object
        await data_manager.store(metric)

        return metric



class NumericMetricComposite(MetricComposite):
    """Metric implementation for numeric measurements"""

    @property
    def value(self) -> float:
        """Get the numeric value of this metric"""
        return float(self._data_object.value)






class DistributionMetricComposite(MetricComposite):
    """Metric implementation for distribution measurements (e.g., tool usage distribution)"""

    @property
    def value(self) -> dict[str, float]:
        """Get the distribution values dictionary"""
        return self._data_object.value

    @property
    def total(self) -> float:
        """Get the total sum of all distribution values"""
        return sum(self.value.values())



class TimeSeriesMetricComposite(MetricComposite):
    """Metric implementation for time series measurements"""

    @property
    def value(self) -> list[tuple[datetime, float]]:
        """Get the time series values"""
        return self._data_object.value

    def get_timeseries_values(self) -> list[float]:
        """Extract just the values from the time series"""
        return [point[1] for point in self.value]

    def get_timestamps(self) -> list[datetime]:
        """Extract just the timestamps from the time series"""
        return [point[0] for point in self.value]

class HistogramMetricComposite(MetricComposite):
    """Metric implementation for histogram measurements"""

    @property
    def value(self) -> dict[NumericInterval, float]:
        """Get the histogram values dictionary with deserialized NumericInterval keys"""
        # Get the raw value from the data object
        raw_value = self._data_object.value

        # Deserialize if needed and return the result
        if isinstance(raw_value, dict):
            deserialized_value = {}
            for key, val in raw_value.items():
                if isinstance(key, str) and '_' in key:
                    try:
                        # Try to parse as "lower_upper" format
                        lower, upper = map(float, key.split('_'))
                        interval = NumericInterval(lower_bound=lower, upper_bound=upper)
                        deserialized_value[interval] = val
                    except (ValueError, TypeError):
                        # If parsing fails, keep the original key
                        deserialized_value[key] = val
                else:
                    deserialized_value[key] = val
            return deserialized_value
        return raw_value

    @property
    def total(self) -> float:
        """Get the total sum of all histogram bin values"""
        return sum(self.value.values())  # Uses the deserialized value from the property

    def get_bin_centers(self) -> list[float]:
        """Calculate and return the centers of each histogram bin"""
        # Work with the deserialized value from the property
        return [(interval.lower_bound + interval.upper_bound) / 2
                for interval in self.value.keys()]

class BasicStatsMetricComposite(MetricComposite):
    """Metric implementation for aggregated metrics"""

    @property
    def value(self) -> AggregatedStats:
        """Get the aggregated statistics"""
        return self._data_object.value

    @property
    def count(self) -> int:
        """Get the count from the aggregated stats"""
        return self.value['count']

    @property
    def mean(self) -> float:
        """Get the mean from the aggregated stats"""
        return self.value['mean']

    @property
    def std(self) -> float | None:
        """Get the standard deviation from the aggregated stats"""
        return self.value.get('std')

    @property
    def min(self) -> float | None:
        """Get the minimum value from the aggregated stats"""
        return self.value.get('min')

    @property
    def max(self) -> float | None:
        """Get the maximum value from the aggregated stats"""
        return self.value.get('max')

    @property
    def scope(self) -> MetricScope | None:
        """Get the scope for aggregated metrics"""
        if self._data_object.scope is None:
            return None

        # If it's already a MetricScope object, return it
        if isinstance(self._data_object.scope, MetricScope):
            return self._data_object.scope

        # If it's a dict (from storage), convert it back to MetricScope
        if isinstance(self._data_object.scope, dict):
            time_interval = self._data_object.scope.get('time_interval')
            if time_interval:
                # Extract time_interval and other fields
                other_fields = {k: v for k, v in self._data_object.scope.items() if k != 'time_interval'}
                return MetricScope(time_interval=time_interval, **other_fields)

        return None

class StringMetricComposite(MetricComposite):
    """Metric implementation for string-based measurements"""

    @property
    def value(self) -> str:
        """Get the string value of this metric"""
        return str(self._data_object.value)




 # Type variable for value
class BaseMetric(Metric[T],ABC):
    """
    Base builder class for all Metric types.
    """
    model_config = {"arbitrary_types_allowed": True}

    # ---Additional platform fields
    plugin_metadata_id: str | None = Field(
        description='The identifier of the analytics which created this object', default=None
    )

    # --- Relationship fields ---
    related_to: list[ElementComposite] | tuple[list[str], list[str]] = Field(default_factory=list)
    root: ElementComposite | str | None = None

    # --- Scope field for time series and aggregated metrics ---
    scope: MetricScope | None = Field(default=None,
        description="The scope for this metric calculation")

    #Override the default id generation of interfaces - since it is based on the class name, to ensure it is always 'metric' and not inheriting class names
    def generate_id_prefix(self) -> str:
        """Override to use the parent interface class name."""
        # Call the generate_id_prefix on the Issue class directly
        prefix = Metric.generate_class_name()  # This will return "Metric"
        return prefix

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseMetric':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseMetric':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def _serialize_value(self, value: Any) -> Any:
        """
        Serialize the metric value for storage if needed.
        Subclasses can override this to handle special serialization needs.
        """
        # Default implementation - no serialization
        return value

    async def store(self, data_manager: "DataManager") -> MetricComposite:
        """Build and store the Metric logical object."""
        # Common validation
        if not self.name:
            raise ValueError("Metric name must be set before building")

        # Type-specific validation
        if not self.value:
            raise ValueError("Values must be set before building")
        # Serialize the value if needed
        serialized_value = self._serialize_value(self.value)

        # Create the metric using the centralized create method
        return await MetricComposite.create(
            data_manager=data_manager,
            element_id=self.element_id,
            root=self.root,
            plugin_metadata_id=self.plugin_metadata_id,
            name=self.name,
            description=self.description,
            units=self.units,
            value=serialized_value,
            metric_type=self.metric_type,
            scope=self.scope,
            timestamp=self.timestamp,
            related_to=self.related_to,
            tags=self.tags,
            **self.attributes
        )

    @classmethod
    async def bulk_store(cls, data_manager: "DataManager", base_metrics: list['BaseMetric']) -> list[MetricComposite]:
        """Efficiently store multiple BaseMetric objects at once."""
        # Common validation for all metric types
        for base_metric in base_metrics:
            if not base_metric.name:
                raise ValueError(f"Metric name must be set before building (id: {base_metric.element_id})")

            # Type-specific validation
            if base_metric.value is None:
                raise ValueError(f"Metric value must be set before building (id: {base_metric.element_id})")

            # Set timestamp if not provided
            if base_metric.timestamp is None:
                base_metric.timestamp = datetime.now().isoformat()

        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_metric in base_metrics:
            # Common processing logic
            related_to_ids = []
            related_to_types = []
            root_id = None

            if base_metric.root is not None:
                if isinstance(base_metric.root, ElementComposite):
                    root_id = base_metric.root.element_id
                elif isinstance(base_metric.root, str):
                    root_id = base_metric.root
                else:
                    raise TypeError("root must be either an Element object or a string ID")

            if base_metric.related_to:
                # Check if related_to is a tuple of (ids, types)
                if isinstance(base_metric.related_to, tuple) and len(base_metric.related_to) == 2:
                    related_to_ids = base_metric.related_to[0]
                    related_to_types = base_metric.related_to[1]
                # Otherwise process as a list of composite elements
                elif isinstance(base_metric.related_to, list):
                    for elem in base_metric.related_to:
                        related_to_ids.append(elem.element_id)
                        type_name = TypeResolutionUtils.get_fully_qualified_type_name_for_type(type(elem._data_object))
                        related_to_types.append(type_name)
                else:
                    raise TypeError("related_to must be either a list of ElementComposite objects or a tuple of (ids, types) lists")

            serialized_value = base_metric._serialize_value(base_metric.value)
            # Create metric data
            metric_data = MetricData(
                element_id=base_metric.element_id,
                name=base_metric.name,
                root_id=root_id,
                plugin_metadata_id=base_metric.plugin_metadata_id,
                description=base_metric.description,
                units=base_metric.units,
                value=serialized_value,
                metric_type=base_metric.metric_type,
                timestamp=base_metric.timestamp,
                scope=base_metric.scope,
                related_to_ids=related_to_ids,
                related_to_types=related_to_types,
                tags=base_metric.tags or [],
                attributes=base_metric.attributes or {}
            )

            # Get appropriate concrete class
            concrete_class = MetricComposite.get_element_class_for_data(metric_data)

            # Create metric instance without storing it
            composite = concrete_class(data_manager, metric_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects


class BaseNumericMetric(BaseMetric[float],NumericMetric):
    """Builder for NumericMetric logical objects"""
    metric_type: Literal[MetricType.NUMERIC] = MetricType.NUMERIC


class BaseStringMetric(BaseMetric[str],StringMetric):
    """Builder for StringMetric logical objects"""
    metric_type: Literal[MetricType.STRING] = MetricType.STRING


class BaseDistributionMetric(BaseMetric[dict[str, float]],DistributionMetric):
    """Builder for DistributionMetric logical objects"""
    metric_type: Literal[MetricType.DISTRIBUTION] = MetricType.DISTRIBUTION

class BaseTimeSeriesMetric(BaseMetric[list[tuple[datetime, float]]], TimeSeriesMetric):
    """Builder for TimeSeriesMetric logical objects"""
    metric_type: Literal[MetricType.TIME_SERIES] = MetricType.TIME_SERIES


class BaseHistogramMetric(BaseMetric[dict[NumericInterval, float]], HistogramMetric):
    """Builder for HistogramMetric logical objects"""
    metric_type: Literal[MetricType.HISTOGRAM] = MetricType.HISTOGRAM

    def _serialize_value(self, value: dict[NumericInterval, float]) -> dict[str, float]:
        """
        Serialize the histogram data by converting NumericInterval keys to string format.
        """
        return serialize_histogram_data(value)



class BaseBasicStatsMetric(BaseMetric[AggregatedStats], BasicStatsMetric):
    """Builder for BasicStatsMetric logical objects"""
    metric_type: Literal[MetricType.STATISTICS] = MetricType.STATISTICS


# Factory function to create the appropriate MetricBuilder based on metric type
def create_metric_model(metric_type: MetricType, **kwargs):
    """
    Factory function to create the appropriate MetricBuilder based on metric type.
    
    Args:
        metric_type: The type of metric to create
        **kwargs: Additional fields to set on the builder
        
    Returns:
        The appropriate MetricBuilder instance
    """
    if metric_type == MetricType.NUMERIC:
        return BaseNumericMetric(**kwargs)
    elif metric_type == MetricType.STRING:
        return BaseStringMetric(**kwargs)
    elif metric_type == MetricType.DISTRIBUTION:
        return BaseDistributionMetric(**kwargs)
    elif metric_type == MetricType.TIME_SERIES:
        return BaseTimeSeriesMetric(**kwargs)
    elif metric_type == MetricType.HISTOGRAM:
        return BaseHistogramMetric(**kwargs)
    elif metric_type == MetricType.STATISTICS:
        return BaseBasicStatsMetric(**kwargs)
    else:
        raise ValueError(f"Unsupported metric type: {metric_type}")



