import json
import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.trace_group_data import TraceGroupData
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.metric import MetricComposite


class TraceGroupComposite(ElementComposite[TraceGroupData]):
    """
    Logical representation of a group of related traces
    
    This class provides a logical view of trace group data and methods
    for working with collections of traces belonging to the same service.
    """

    # Specify the corresponding data class
    data_class: ClassVar[type[TraceGroupData]] = TraceGroupData

    def __init__(self, data_manager: DataManager, trace_group_data: TraceGroupData,*, _token: object = None):
        super().__init__(data_manager, trace_group_data, _token=_token)

    # Basic properties that reflect the underlying data object

    @classmethod
    async def get_trace_groups(cls,data_manager: "DataManager",service_name: str) -> list['TraceGroupComposite']:
        return await data_manager.get_trace_groups(service_name)

    @property
    def service_name(self) -> str:
        """Get the service name this trace group belongs to"""
        return self._data_object.service_name

    @property
    def traces_ids(self) -> list[str]:
        """Get the list of trace IDs in this group"""
        return self._data_object.traces_ids

    @property
    def avg_duration(self) -> float | None:
        """Get the average duration across all traces in seconds"""
        return self._data_object.avg_duration

    @property
    def success_rate(self) -> float | None:
        """Get the success rate across all traces (0.0 to 1.0)"""
        return self._data_object.success_rate

    @property
    def total_traces(self) -> int:
        """Get the total number of traces in the group"""
        return self._data_object.total_traces

    @property
    def failure_count(self) -> int:
        """Get the number of failed traces"""
        return self._data_object.failure_count

    # Relationship properties that use the data manager

    @property
    async def traces(self) -> list['BaseTraceComposite']:
        """
        Get all traces in this group

        Returns a list of logical BaseTrace objects corresponding to the trace IDs in this group.
        """
        return await self._data_manager.get_traces_for_trace_group(self.element_id)

    @property
    async def owned_metrics(self) -> list[MetricComposite]:
        """
        Get all metrics owned by this trace group.

        Returns metrics where this trace group is the owner (root).
        This includes automatically-generated aggregate metrics like avg_duration, success_rate, etc.

        Returns:
            List of MetricComposite objects owned by this trace group
        """
        return await self._data_manager.get_children(self.element_id, MetricComposite)

    @property
    async def related_metrics(self) -> list[MetricComposite]:
        """
        Get all metrics owned by this trace group.

        Returns metrics where this trace group is the owner (root).
        This includes automatically-generated aggregate metrics like avg_duration, success_rate, etc.

        Returns:
            List of MetricComposite objects owned by this trace group
        """
        related_elements = await self._data_manager.get_elements_related_to_artifact_and_type(self,MetricComposite)
        return related_elements

    # Factory method for creating trace groups

    @classmethod
    async def _compute_metrics_from_traces(cls, data_manager: DataManager, traces_ids: list[str]) -> dict[str, Any]:
        """
        Compute aggregate metrics from a list of trace IDs.

        Args:
            data_manager: The data manager to fetch traces
            traces_ids: List of trace IDs to compute metrics for

        Returns:
            Dictionary with computed metrics: avg_duration, success_rate, total_traces, failure_count
        """
        if not traces_ids:
            return {
                'avg_duration': None,
                'success_rate': None,
                'total_traces': 0,
                'failure_count': 0
            }

        # Fetch all traces
        durations = []
        failure_count = 0

        for trace_id in traces_ids:
            try:
                trace = await data_manager.get_trace(trace_id)

                # Compute duration if both start_time and end_time are available
                if trace.start_time and trace.end_time:
                    duration = (trace.end_time - trace.start_time).total_seconds()
                    durations.append(duration)

                # Check if trace has failures
                if trace.failures and len(trace.failures) > 0:
                    failure_count += 1
            except Exception:
                # If we can't fetch a trace, skip it
                pass

        # Compute metrics
        total_traces = len(traces_ids)
        avg_duration = sum(durations) / len(durations) if durations else None
        success_rate = (total_traces - failure_count) / total_traces if total_traces > 0 else None

        return {
            'avg_duration': avg_duration,
            'success_rate': success_rate,
            'total_traces': total_traces,
            'failure_count': failure_count
        }

    @classmethod
    async def create(cls,
                    data_manager: DataManager,
                    service_name: str,
                    name: str | None = None,
                    traces_ids: list[str] = None,
                    element_id: str | None = None,
                    **kwargs) -> 'TraceGroupComposite':
        """
        Factory method to create a new trace group

        Args:
            data_manager: The data manager to use for storage
            service_name: The name of the service this trace group belongs to
            name: Optional name for the trace group
            traces_ids: List of trace IDs to include in the group
            element_id: Optional ID for the trace group (auto-generated if not provided)
            **kwargs: Additional fields for the trace group

        Returns:
            A new TraceGroup instance

        Note:
            This method no longer computes and stores metrics within the trace group.
            Metrics should be created separately using the MetricsResource with
            owner=trace_group and related_to=trace_group.
        """
        import uuid

        # Generate ID if not provided
        if element_id is None:
            element_id = f"trace-group-{service_name}-{uuid.uuid4()}"

        # Set default name if not provided
        if name is None:
            name = f"Trace Group for {service_name}"

        # Create trace group data without computing metrics
        traces_ids = traces_ids or []
        trace_group_data = TraceGroupData(
            element_id=element_id,
            name=name,
            service_name=service_name,
            traces_ids=traces_ids,
            **kwargs
        )

        trace_group = cls(data_manager, trace_group_data,_token=_CREATION_TOKEN)

        # Store trace group data
        await data_manager.store(trace_group)

        # Return trace group
        return trace_group


class BaseTraceGroup(BaseModel):
    """
    Builder class for TraceGroup logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable TraceGroup logical object.
    
    """
    model_config = {"arbitrary_types_allowed": True
    }

    # --- Fields from TraceGroup ---
    id: str = Field(default_factory=lambda: f"trace-group-{uuid.uuid4()}")
    name: str | None = None
    service_name: str = ""
    traces_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    # --- Owner-related fields ---
    root: ElementComposite | str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseTraceGroup':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseTraceGroup':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    async def store(self, data_manager: DataManager) -> TraceGroupComposite:
        """
        Build the TraceGroup logical object.
        
        Args:
            data_manager: The data manager to use for creating the TraceGroup
            
        Returns:
            The created TraceGroup logical object
        """
        # Validate required fields
        if not self.service_name:
            raise ValueError("Service name must be set before building")

        # Set default name if not provided
        if self.name is None:
            self.name = f"Trace Group for {self.service_name}"

        # Prepare kwargs for additional parameters
        kwargs = dict(self.attributes)
        if self.root is not None:
            kwargs['root'] = self.root

        # Create the trace group
        return await TraceGroupComposite.create(
            data_manager=data_manager,
            element_id=self.id,
            service_name=self.service_name,
            name=self.name,
            traces_ids=self.traces_ids,
            **kwargs
        )

    @classmethod
    async def bulk_store(cls, data_manager: DataManager, base_trace_groups: list['BaseTraceGroup']) -> list[TraceGroupComposite]:
        """
        Efficiently store multiple BaseTraceGroup objects at once.

        Args:
            data_manager: The data manager to use for storage
            base_trace_groups: List of BaseTraceGroup objects to store

        Returns:
            List of created TraceGroupComposite objects

        Note:
            This method no longer computes and stores metrics within the trace groups.
            Metrics should be created separately using the MetricsResource with
            owner=trace_group and related_to=trace_group.
        """
        # Validate all builders before proceeding
        for base_trace_group in base_trace_groups:
            if not base_trace_group.service_name:
                raise ValueError(f"Service name must be set before building (id: {base_trace_group.id})")

            # Set default name if not provided
            if base_trace_group.name is None:
                base_trace_group.name = f"Trace Group for {base_trace_group.service_name}"

        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_trace_group in base_trace_groups:
            # Prepare kwargs for additional parameters
            kwargs = dict(base_trace_group.attributes or {})

            if base_trace_group.root is not None:
                if isinstance(base_trace_group.root, ElementComposite):
                    kwargs['root_id'] = base_trace_group.root.id
                elif isinstance(base_trace_group.root, str):
                    kwargs['root_id'] = base_trace_group.root
                else:
                    raise TypeError("root must be either an Element object or a string ID")

            # Create trace group data without computing metrics
            trace_group_data = TraceGroupData(
                element_id=base_trace_group.id,
                name=base_trace_group.name,
                service_name=base_trace_group.service_name,
                traces_ids=base_trace_group.traces_ids or [],
                **kwargs
            )

            # Create trace group instance without storing it
            composite = TraceGroupComposite(data_manager, trace_group_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects
