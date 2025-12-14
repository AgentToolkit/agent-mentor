"""
Simplified data models for the AgentOps SDK

These models provide a developer-friendly interface while automatically
proxying to internal composite objects, minimizing maintenance burden.

The wrapper hierarchy mirrors the composite hierarchy:
- Element (wraps ElementComposite)
  - RelatableElement (wraps RelatableElementComposite)
    - Metric, Issue, Workflow, Recommendation, Annotation
  - Trace, Span, Task, Action, TraceGroup, etc.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Union

from agent_analytics.core.data_composite.annotation import AnnotationComposite
from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.element import ElementComposite
from agent_analytics.core.data_composite.issue import IssueComposite
from agent_analytics.core.data_composite.metric import (
    DistributionMetricComposite,
    HistogramMetricComposite,
    MetricComposite,
    NumericMetricComposite,
    StringMetricComposite,
    TimeSeriesMetricComposite,
)
from agent_analytics.core.data_composite.recommendation import RecommendationComposite
from agent_analytics.core.data_composite.relatable_element import RelatableElementComposite
from agent_analytics.core.data_composite.action import ActionComposite
from agent_analytics.core.data_composite.task import TaskComposite
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.data_composite.trace_workflow import TraceWorkflowComposite
from agent_analytics.core.data_composite.workflow import WorkflowComposite
from agent_analytics.core.data_composite.workflow_edge import WorkflowEdgeComposite
from agent_analytics.core.data_composite.workflow_node import WorkflowNodeComposite
from agent_analytics.core.data_composite.workflow_node_gateway import WorkflowNodeGatewayComposite


class MetricType(str, Enum):
    """Types of metrics supported by the platform"""
    NUMERIC = "numeric"
    STRING = "string"
    DISTRIBUTION = "distribution"
    TIME_SERIES = "time_series"
    HISTOGRAM = "histogram"
    STATISTICS = "statistics"


# =============================================================================
# Base Wrapper Classes
# =============================================================================

@dataclass(repr=False)
class Element:
    """
    Base SDK wrapper for ElementComposite.

    Provides automatic property proxying to the underlying composite object.
    All subclasses inherit this behavior, minimizing code duplication.

    The _FIELD_MAPPING class variable allows renaming fields at the SDK level
    (e.g., element_id -> id) while maintaining compatibility with composites.
    """
    _composite: ElementComposite

    # Define field remappings (SDK name -> Composite name)
    # Subclasses can extend this mapping
    _FIELD_MAPPING = {
        "id": "element_id",
    }

    def __getattr__(self, name: str) -> Any:
        """
        Automatically proxy attribute access to the underlying composite.

        This allows all composite properties to be accessed without
        explicitly defining them in the wrapper class.

        Args:
            name: The attribute name to access

        Returns:
            The attribute value from the composite

        Raises:
            AttributeError: If the attribute doesn't exist on the composite
        """
        composite_name = self._FIELD_MAPPING.get(name, name)
        return getattr(self._composite, composite_name)


    async def related_elements(self, element_type: type["RelatableElement"] | None = None) -> list["RelatableElement"]:
        """
        Get all relatable elements (or elements of a specific type) that are related to this element.

        This is a convenience method that allows querying related elements directly
        from an element object, rather than going through the client.

        Args:
            element_type: Optional type of relatable element to filter by (Metric, Issue, Workflow, etc.)
                         If None, returns all related elements.

        Returns:
            List of related elements as SDK wrappers (optionally filtered by type)

        Raises:
            ValueError: If element_type is not a valid RelatableElement type

        Example:
            # Get all metrics related to a span
            metrics = await span.related_elements(element_type=Metric)

            # Get all related elements of any type
            all_related = await span.related_elements()

            # Get all issues related to a task
            issues = await task.related_elements(element_type=Issue)
        """

        if element_type is not None:
            # Validate the type
            composite_class = _type_to_composite.get(element_type)
            if composite_class is None:
                raise ValueError(
                    f"Invalid type: {element_type}. Must be one of: Metric, Issue, Workflow, "
                    "Recommendation, Annotation"
                )

            # Delegate to composite's data manager to get filtered composites
            composites = await self._composite._data_manager.get_elements_related_to_artifact_and_type(
                self._composite, composite_class
            )

        else:
            # Get all related elements - delegate to composite
            composites = await self._composite.related_elements

        # Convert composites to SDK wrappers using from_composite
        results = []
        for comp in composites:
            wrapper_class = _composite_to_type.get(type(comp))
            if wrapper_class:
                results.append(wrapper_class.from_composite(comp))

        return results

    def __repr__(self) -> str:
        """Default string representation"""
        return f"{self.__class__.__name__}(id={self.id!r})"


@dataclass(repr=False)
class RelatableElement(Element):
    """
    Base SDK wrapper for RelatableElementComposite.

    Extends Element to inherit all base functionality.
    RelatableElementComposite adds relationship tracking properties
    which are automatically available through the proxy pattern:
    - related_to
    - related_to_ids
    - related_to_types
    """
    _composite: RelatableElementComposite

    # Inherits _FIELD_MAPPING and __getattr__ from Element


# =============================================================================
# Concrete Element Wrappers (non-relatable)
# =============================================================================

@dataclass(repr=False)
class Trace(Element):
    """
    SDK representation of a trace.

    Wraps BaseTraceComposite and provides a cleaner interface by:
    - Renaming element_id -> id
    - Adding convenience properties like duration
    - Hiding internal implementation details

    All properties from BaseTraceComposite are automatically available.
    """
    _composite: BaseTraceComposite

    @property
    def duration(self) -> float | None:
        """Duration of the trace in seconds"""
        if self._composite.end_time and self._composite.start_time:
            return (self._composite.end_time - self._composite.start_time).total_seconds()
        return None

    def __repr__(self) -> str:
        return f"Trace(id={self.id!r}, service_name={self.service_name!r})"


@dataclass(repr=False)
class Span(Element):
    """
    SDK representation of a span.

    Wraps BaseSpanComposite and provides a cleaner interface by:
    - Renaming element_id -> id
    - Adding convenience properties like duration
    - Hiding internal implementation details

    All properties from BaseSpanComposite are automatically available.
    """
    _composite: BaseSpanComposite

    @property
    def duration(self) -> float | None:
        """Duration of the span in seconds"""
        if self._composite.end_time and self._composite.start_time:
            return (self._composite.end_time - self._composite.start_time).total_seconds()
        return None

    def __repr__(self) -> str:
        return f"Span(id={self.id!r}, name={self.name!r})"


@dataclass(repr=False)
class Task(Element):
    """
    SDK representation of a task.

    Wraps TaskComposite and provides a cleaner interface.
    All properties from TaskComposite are automatically available.
    """
    _composite: TaskComposite

    @property
    def duration(self) -> float | None:
        """Duration of the task in seconds"""
        if self._composite.end_time and self._composite.start_time:
            return (self._composite.end_time - self._composite.start_time).total_seconds()
        return None

    @property
    async def metrics(self):
        """Get all metrics related to this task."""
        metric_composites = await self._composite.related_metrics
        from agent_analytics.sdk.models import Metric
        return [Metric.from_composite(mc) for mc in metric_composites]

    @property
    async def issues(self):
        """Get all issues related to this task."""
        issue_composites = await self._composite.related_issues
        from agent_analytics.sdk.models import Issue
        return [Issue.from_composite(ic) for ic in issue_composites]

    @property
    async def annotations(self):
        """Get all annotations related to this task."""
        annotation_composites = await self._composite.related_annotations()
        from agent_analytics.sdk.models import Annotation
        return [Annotation.from_composite(ac) for ac in annotation_composites]

    @property
    async def executor(self):
        """Get the action/action that executes this task."""
        executor_composite = await self._composite.executor
        if executor_composite:
            from agent_analytics.sdk.models import Action
            return Action.from_composite(executor_composite)
        return None

    @property
    async def parent(self):
        """Get the parent task."""
        parent_id = self._composite.parent_id
        if parent_id:
            parent = await self._composite.parent
            if parent:
                return Task.from_composite(parent)
        return None

    @property
    async def dependent_tasks(self):
        """Get all tasks that this task depends on."""
        if not self._composite.dependent_ids:
            return []

        from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator
        query = {
            "element_id": QueryFilter(operator=QueryOperator.EQUALS_MANY, value=self._composite.dependent_ids)
        }

        task_composites = await self._composite._data_manager.search(element_type=TaskComposite, query=query)

        from agent_analytics.sdk.models import Task
        composite_by_id = {tc.element_id: tc for tc in task_composites}
        return [Task.from_composite(composite_by_id[dep_id]) for dep_id in self._composite.dependent_ids if dep_id in composite_by_id]

    @classmethod
    def from_composite(cls, composite: TaskComposite) -> "Task":
        """
        Create a Task wrapper from a TaskComposite.
        
        Args:
            composite: The TaskComposite to wrap
            
        Returns:
            A Task SDK wrapper
        """
        return cls(_composite=composite)

    def __repr__(self) -> str:
        return f"Task(id={self.id!r}, name={self.name!r})"


@dataclass(repr=False)
class Action(Element):
    """
    SDK representation of a action.

    Wraps ActionComposite and provides a cleaner interface.
    All properties from ActionComposite are automatically available.
    """
    _composite: ActionComposite

    def __repr__(self) -> str:
        return f"Action(id={self.id!r}, name={self.name!r})"

    @classmethod
    def from_composite(cls, composite: ActionComposite) -> "Action":
        """
        Create a Action wrapper from a ActionComposite.
        
        Args:
            composite: The TaskComposite to wrap
            
        Returns:
            An Action SDK wrapper
        """
        return cls(_composite=composite)

    @property
    async def workflow(self):
        """
        Get the workflow associated with this action.
        
        Returns:
            WorkflowComposite object if found, None otherwise
        """
        workflow = await self._composite.workflow
        return Workflow(_composite=workflow)



@dataclass(repr=False)
class TraceGroup(Element):
    """
    SDK representation of a trace group.

    Wraps TraceGroupComposite and provides a cleaner interface.
    All properties from TraceGroupComposite are automatically available.
    """
    _composite: TraceGroupComposite

    @property
    async def traces(self) -> list["Trace"]:
        """
        Get all traces in this group as SDK Trace wrappers.

        Returns:
            List of Trace objects (SDK wrappers)
        """
        trace_composites = await self._composite.traces
        return [Trace(_composite=tc) for tc in trace_composites]

    @property
    async def metrics(self) -> list["Metric"]:
        """
        Get all metrics owned by this trace group.

        This includes automatically-generated aggregate metrics (avg_duration,
        success_rate, total_traces, failure_count) that are created when the
        trace group is instantiated.

        Returns:
            List of Metric objects (SDK wrappers)

        Example:
            metrics = await trace_group.metrics
            for metric in metrics:
                print(f"{metric.name}: {metric.value} {metric.units}")
        """
        metric_composites = await self._composite.owned_metrics
        return [Metric.from_composite(mc) for mc in metric_composites]

    async def get_metric(self, name: str) -> "Metric | None":
        """
        Get a specific metric by name.

        Convenience method to fetch a single metric without retrieving all metrics.

        Args:
            name: The name of the metric (e.g., "avg_duration", "success_rate")

        Returns:
            Metric object if found, None otherwise

        Example:
            avg_duration_metric = await trace_group.get_metric("avg_duration")
            if avg_duration_metric:
                print(f"Average duration: {avg_duration_metric.value} {avg_duration_metric.units}")
        """
        metrics = await self.metrics
        for metric in metrics:
            if metric.name == name:
                return metric
        return None

    async def get_metric_value(self, name: str, default=None):
        """
        Get the value of a specific metric by name.

        Convenience method to get just the value without the full Metric object.

        Args:
            name: The name of the metric (e.g., "avg_duration", "success_rate")
            default: Default value to return if metric is not found

        Returns:
            The metric value if found, default value otherwise

        Example:
            avg_duration = await trace_group.get_metric_value("avg_duration")
            success_rate = await trace_group.get_metric_value("success_rate", default=0.0)
        """
        metric = await self.get_metric(name)
        return metric.value if metric else default

    def __repr__(self) -> str:
        return f"TraceGroup(id={self.id!r}, name={self.name!r})"


@dataclass(repr=False)
class TraceWorkflow(Element):
    """
    SDK representation of a trace workflow.

    Wraps TraceWorkflowComposite and provides a cleaner interface.
    All properties from TraceWorkflowComposite are automatically available.
    """
    _composite: TraceWorkflowComposite

    @property
    async def nodes(self) -> list["WorkflowNode"]:
        """
        Get all workflow nodes belonging to this workflow

        Returns:
            List of WorkflowNode objects (SDK wrappers)

        Example:
            nodes = await workflow.nodes
        """
        node_composites = await self._composite.workflow_nodes
        return [WorkflowNode(_composite=nc) for nc in node_composites]

    @property
    async def edges(self) -> list["WorkflowEdge"]:
        """
        Get all workflow edges belonging to this workflow

        Returns:
            List of WorkflowEdge objects (SDK wrappers)

        Example:
            edges = await workflow.edges
        """
        edge_composites = await self._composite.workflow_edges
        return [WorkflowEdge(_composite=ec) for ec in edge_composites]

    async def get_node(self, name: str) -> "WorkflowNode | None":
        """
        Get a specific node by name.

        Convenience method to fetch a single node with given name.

        Args:
            name: The node name to filter by (e.g., "DecisionNode")

        Returns:
            A WorkflowNode objects that match the specified name, if found


        Example:
            # Get a node named "DecisionNode" 
            decision_node = await workflow.get_node("DecisionNode")
        """
        nodes = await self.nodes
        for node in nodes:
            if node.name == name:
                return node
        return None

    async def get_nodes_by_type(self, type: str) -> list["WorkflowNode"]:
        """
        Get all nodes of a specific type in this workflow.

        This method provides a convenient way to filter workflow nodes by their type,
        avoiding the need to retrieve all nodes and filter manually.

        Args:
            type: The node type to filter by (e.g., "WorkflowNode", "XOR")

        Returns:
            List of WorkflowNode objects that match the specified type


        Example:
            # Get all XOR nodes in the workflow
            xor_nodes = await workflow.get_nodes_by_type("XOR")

            # Get all regular nodes
            regular_nodes = await workflow.get_nodes_by_type("WorkflowNode")


        """
        nodes = await self.nodes
        return [node for node in nodes if node.type == type]


    async def get_incoming_edges_for_node(self, node: Union["WorkflowNode", str]) -> list["WorkflowEdge"]:
        """
        Get all incoming edges for a specific workflow node.
        
        An incoming edge is one where the node appears in the destination_ids list.
        
        Args:
            node: WorkflowNode object or node ID string
            
        Returns:
            List of WorkflowEdge objects that point to this node

        Example:
        # Get incoming edges for a specific node object
        incoming_edges = await workflow.get_incoming_edges_for_node(decision_node)
        
        # Get incoming edges using node ID string
        incoming_edges = await workflow.get_incoming_edges_for_node("node-123")
        """
        # Get node ID - handle both node objects and ID strings
        if hasattr(node, 'id'):
            node_id = node.id
        elif isinstance(node, str):
            node_id = node
        else:
            raise ValueError("Node must be a WorkflowNode object or node ID string")

        # Get all edges in this workflow
        all_edges = await self.edges

        # Filter for edges where this node appears in destination_ids
        return [edge for edge in all_edges if node_id in edge.destination_ids]

    async def get_outgoing_edges_for_node(self, node: Union["WorkflowNode", str]) -> list["WorkflowEdge"]:
        """
        Get all outgoing edges for a specific workflow node.
        
        An outgoing edge is one where the node appears in the source_ids list.
        
        Args:
            node: WorkflowNode object or node ID string
            
        Returns:
            List of WorkflowEdge objects that originate from this node

        Example:
        # Get outgoing edges for a specific node object  
        outgoing_edges = await workflow.get_outgoing_edges_for_node(decision_node)
        
        # Get outgoing edges using node ID string
        outgoing_edges = await workflow.get_outgoing_edges_for_node("node-123")
        """
        # Get node ID - handle both node objects and ID strings
        if hasattr(node, 'id'):
            node_id = node.id
        elif isinstance(node, str):
            node_id = node
        else:
            raise ValueError("Node must be a WorkflowNode object or node ID string")

        # Get all edges in this workflow
        all_edges = await self.edges

        # Filter for edges where this node appears in source_ids
        return [edge for edge in all_edges if node_id in edge.source_ids]

    def __repr__(self) -> str:
        return f"TraceWorkflow(id={self.id!r})"




@dataclass(repr=False)
class WorkflowNode(Element):
    """
    SDK representation of a workflow node.

    Wraps WorkflowNodeComposite and provides a cleaner interface.
    All properties from WorkflowNodeComposite are automatically available.
    """
    _composite: WorkflowNodeComposite

    def __repr__(self) -> str:
        return f"WorkflowNode(id={self.id!r})"


@dataclass(repr=False)
class WorkflowNodeGateway(Element):
    """
    SDK representation of a workflow node gateway.

    Wraps WorkflowNodeGatewayComposite and provides a cleaner interface.
    All properties from WorkflowNodeGatewayComposite are automatically available.
    """
    _composite: WorkflowNodeGatewayComposite

    def __repr__(self) -> str:
        return f"WorkflowNodeGateway(id={self.id!r})"


@dataclass(repr=False)
class WorkflowEdge(Element):
    """
    SDK representation of a workflow edge.

    Wraps WorkflowEdgeComposite and provides a cleaner interface.
    All properties from WorkflowEdgeComposite are automatically available.
    """
    _composite: WorkflowEdgeComposite

    def __repr__(self) -> str:
        return f"WorkflowEdge(id={self.id!r})"


# =============================================================================
# Concrete RelatableElement Wrappers
# =============================================================================

@dataclass(repr=False)
class Metric(RelatableElement):
    """
    SDK representation of a metric.

    Wraps MetricComposite and provides a cleaner interface by:
    - Renaming element_id -> id
    - Exposing trace_id and span_id at the top level
    - Converting internal MetricType to SDK MetricType
    - Hiding internal implementation details

    All properties from MetricComposite are automatically available,
    including relatable properties (related_to, related_to_ids, related_to_types).
    """
    _composite: MetricComposite
    _trace_id: str
    _span_id: str | None = None
    _metric_type: MetricType | None = None

    @property
    def trace_id(self) -> str:
        """ID of the trace this metric belongs to"""
        return self._trace_id

    @property
    def span_id(self) -> str | None:
        """ID of the span this metric is related to (if any)"""
        return self._span_id

    @property
    def metric_type(self) -> MetricType:
        """Type of this metric"""
        return self._metric_type

    @classmethod
    def from_composite(cls, composite: MetricComposite) -> "Metric":
        """
        Create a Metric wrapper from a MetricComposite.

        Args:
            composite: The MetricComposite to wrap

        Returns:
            A Metric SDK wrapper
        """
        from agent_analytics_common.interfaces.metric import (
            MetricType as InternalMetricType,
        )

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

        root_id = composite.root_id
        related_ids = composite.related_to_ids

        # Try to determine span_id from related elements
        span_id = None
        if related_ids and len(related_ids) > 0:
            related_types = composite.related_to_types
            if related_types and "span" in related_types[0].lower():
                span_id = related_ids[0]

        return cls(
            _composite=composite,
            _trace_id=root_id or "",
            _span_id=span_id,
            _metric_type=sdk_metric_type
        )

    def __repr__(self) -> str:
        return f"Metric(id={self.id!r}, name={self.name!r}, value={self.value!r})"


@dataclass(repr=False)
class Issue(RelatableElement):
    """
    SDK representation of an issue.

    Wraps IssueComposite and provides a cleaner interface.
    All properties from IssueComposite are automatically available,
    including relatable properties.
    """
    _composite: IssueComposite

    @classmethod
    def from_composite(cls, composite: IssueComposite) -> "Issue":
        """Create an Issue wrapper from an IssueComposite."""
        return cls(_composite=composite)

    def __repr__(self) -> str:
        return f"Issue(id={self.id!r}, name={self.name!r})"


@dataclass(repr=False)
class Workflow(RelatableElement):
    """
    SDK representation of a workflow.

    Wraps WorkflowComposite and provides a cleaner interface.
    All properties from WorkflowComposite are automatically available,
    including relatable properties.
    """
    _composite: WorkflowComposite

    @classmethod
    def from_composite(cls, composite: WorkflowComposite) -> "Workflow":
        """Create a Workflow wrapper from a WorkflowComposite."""
        return cls(_composite=composite)

    def __repr__(self) -> str:
        return f"Workflow(id={self.id!r}, name={self.name!r})"


@dataclass(repr=False)
class Recommendation(RelatableElement):
    """
    SDK representation of a recommendation.

    Wraps RecommendationComposite and provides a cleaner interface.
    All properties from RecommendationComposite are automatically available,
    including relatable properties.
    """
    _composite: RecommendationComposite

    @classmethod
    def from_composite(cls, composite: RecommendationComposite) -> "Recommendation":
        """Create a Recommendation wrapper from a RecommendationComposite."""
        return cls(_composite=composite)

    def __repr__(self) -> str:
        return f"Recommendation(id={self.id!r}, name={self.name!r})"


@dataclass(repr=False)
class Annotation(RelatableElement):
    """
    SDK representation of an annotation.

    Wraps AnnotationComposite and provides a cleaner interface.
    All properties from AnnotationComposite are automatically available,
    including relatable properties.
    """
    _composite: AnnotationComposite

    @classmethod
    def from_composite(cls, composite: AnnotationComposite) -> "Annotation":
        """Create an Annotation wrapper from an AnnotationComposite."""
        return cls(_composite=composite)

    def __repr__(self) -> str:
        return f"Annotation(id={self.id!r}, name={self.name!r})"


# Map SDK wrapper type to composite type
_type_to_composite = {
    Metric: MetricComposite,
    Issue: IssueComposite,
    Workflow: WorkflowComposite,
    Recommendation: RecommendationComposite,
    Annotation: AnnotationComposite,
    Task: TaskComposite,
    Action: ActionComposite
}

_composite_to_type = {
    NumericMetricComposite: Metric,
    DistributionMetricComposite: Metric,
    StringMetricComposite: Metric,
    TimeSeriesMetricComposite: Metric,
    HistogramMetricComposite: Metric,
    MetricComposite: Metric,
    IssueComposite: Issue,
    WorkflowComposite: Workflow,
    RecommendationComposite: Recommendation,
    AnnotationComposite: Annotation,
    TaskComposite: Task,
    ActionComposite: Action
}
