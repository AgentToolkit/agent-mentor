from datetime import datetime
from typing import ClassVar

from agent_analytics_common.interfaces.metric import MetricType

from agent_analytics.core.data.trace_data import BaseTraceData
from agent_analytics.core.data_composite.annotation import AnnotationComposite
from agent_analytics.core.data_composite.element import ElementComposite
from agent_analytics.core.data_composite.issue import BaseIssue, IssueComposite
from agent_analytics.core.data_composite.metric import BaseMetric, MetricComposite
from agent_analytics.core.data_composite.task import TaskComposite
from agent_analytics.core.data_composite.trace_workflow import TraceWorkflowComposite


class BaseTraceComposite(ElementComposite[BaseTraceData]):
    """Composite representation of a Task with related Metrics"""
    # Specify the corresponding data class
    data_class: ClassVar[type[BaseTraceData]] = BaseTraceData

    def __init__(self, data_manager: "DataManager", base_trace_data: BaseTraceData,*, _token: object = None):
        super().__init__(data_manager, base_trace_data, _token=_token)

    @classmethod
    async def get_tasks_for_trace(cls,data_manager: "DataManager",trace_id:str) -> list[TaskComposite]:
        return await data_manager.get_children(trace_id,TaskComposite)

    @classmethod
    async def get_spans_for_trace(cls,data_manager: "DataManager",trace_id:str) -> list['BaseSpanComposite']:
        return await data_manager.get_spans(trace_id)

    @classmethod
    async def get_all_issues_for_trace(cls,data_manager: "DataManager",trace_id:str) -> list[IssueComposite]:
        return await data_manager.get_children(trace_id,IssueComposite)

    @classmethod
    async def get_all_metrics_for_trace(cls,data_manager: "DataManager",trace_id:str) -> list[MetricComposite]:
        return await data_manager.get_children(trace_id,MetricComposite)

    @classmethod
    async def get_all_metrics_for_traces(cls,data_manager: "DataManager",trace_ids:list[str]) -> dict[str, list[MetricComposite]]:
        raw_metrics = await data_manager.get_children_for_list(trace_ids, MetricComposite)
        results = {}
        for metric in raw_metrics:
            metric: MetricComposite = metric
            if metric.root_id not in results:
                results[metric.root_id] = []
            results[metric.root_id].append(metric)
        return results

    @classmethod
    async def get_all_annotations_for_trace(cls,data_manager: "DataManager",trace_id:str) -> list[AnnotationComposite]:
        return await data_manager.get_children(trace_id,AnnotationComposite)

    @classmethod
    async def get_all_workflows_for_trace(cls,data_manager: "DataManager",trace_id:str) -> list[TraceWorkflowComposite]:
        return await data_manager.get_children(trace_id,TraceWorkflowComposite)

    @classmethod
    async def get_traces(cls,data_manager: "DataManager",service_name: str, from_date: datetime, to_date: datetime | None) -> list['BaseTraceComposite']:
        return await data_manager.get_traces(service_name,from_date,to_date)


    @classmethod
    async def get_by_id(cls, data_manager: "DataManager", id: str) -> 'BaseTraceComposite':
        """Get an element by its ID"""
        obj = await data_manager.get_trace(id)
        return obj

    @property
    def start_time(self) -> datetime | None:
         return self._data_object.start_time
    @property
    def end_time(self) -> datetime | None:
         return self._data_object.end_time
    @property
    def service_name(self) -> str | None:
         return self._data_object.service_name

    @property
    def num_of_spans(self) -> int | None:
        return self._data_object.num_of_spans

    @property
    def agent_ids(self) -> list[str] | None:
        return self._data_object.agent_ids

    @property
    def failures(self)-> dict[str, int] | None:
        return self._data_object.failures

    @property
    def duration(self) -> float | None:
        """Duration of the trace in seconds"""
        if self._data_object.end_time and self._data_object.start_time:
            return (self._data_object.end_time - self._data_object.start_time).total_seconds()
        return None

    @property
    async def spans(self) -> list['BaseSpanComposite']:
        """
        Retrieves all logical BaseSpanComposite objects associated with this trace.
        """
        return await self._data_manager.get_spans(self.element_id)

    @property
    async def tasks(self) -> list['TaskComposite']:
        """
        Retrieves all logical TaskComposite objects associated with this trace.
        """
        return await self._data_manager.get_children(self.element_id,TaskComposite)


    @property
    async def related_issues(self) -> list[IssueComposite]:
        """
        Get all issues related to this task.
        
        Returns:
            List of issues related to this task
        """
        # Use the data manager to retrieve elements related to this task
        related_elements = await self._data_manager.get_elements_related_to_artifact_and_type(self,IssueComposite)
        return related_elements

    @property
    async def owned_metrics(self) -> list[MetricComposite]:
        """
        Retrieves all logical TaskComposite objects associated with this trace.
        """
        return await self._data_manager.get_children(self.element_id,MetricComposite)

    @property
    async def related_metrics(self) -> list[MetricComposite]:
        """
        Get all metrics related to this task.
        
        Returns:
            List of metrics related to this task
        """
        # Use the data manager to retrieve elements related to this task
        related_elements = await self._data_manager.get_elements_related_to_artifact_and_type(self,MetricComposite)
        return related_elements

    @property
    async def owned_issues(self) -> list[IssueComposite]:
        """
        Retrieves all logical TaskComposite objects associated with this trace.
        """
        return await self._data_manager.get_children(self.element_id,IssueComposite)

    @property
    async def workflow(self) -> list[TraceWorkflowComposite]:
        """
        Retrieves all logical workflow objects associated with this trace.
        """
        return await self._data_manager.get_children(self.element_id,TraceWorkflowComposite)

    @property
    async def annotations(self) -> list[AnnotationComposite]:
        """
        Retrieves all logical annotation objects associated with this trace.
        """
        return await self._data_manager.get_children(self.element_id,AnnotationComposite)

    async def add_metric(self,
                    metric: BaseMetric) -> MetricComposite:
        """
        Add a metric to this task with the specified type.
        
        Args:
            name: Display name for the metric
            value: The value of the metric (type depends on metric_type)
            metric_type: The type of metric to create (NUMERIC, STRING, DISTRIBUTION)
            units: Units of measurement (meaning depends on metric_type)
            description: Description of what this metric measures            
            tags: List of tags for categorization
            
        Returns:
            The created Metric
        """
        if metric.root is None:
                metric.root = self
        if not metric.element_id:
                metric.element_id = f"metric-{self.element_id}-{metric.name.lower().replace(' ', '-')}"

        # Add this task to related_to if not already there
        if not any(getattr(related, 'element_id', None) == self.element_id for related in metric.related_to):
                metric.related_to.append(self)

        # Build and return the metric
        return await metric.store(self._data_manager)

    async def add_metrics(self, metrics: list[BaseMetric]) -> list[MetricComposite]:
        """
        Add multiple metrics to this task at once.
        
        Args:
            metrics: List of metric builders to add to this task
                
        Returns:
            List of created Metric objects
        """
        # Set default values for all metrics if not provided
        for metric in metrics:
            if metric.root is None:
                metric.root = self
            if not metric.element_id:
                metric.element_id = f"Metric-{self.element_id}-{metric.name.lower().replace(' ', '-')}"

            # Add this task to related_to if not already there
            if not any(getattr(related, 'element_id', None) == self.element_id for related in metric.related_to):
                metric.related_to.append(self)

        # Use the appropriate bulk_store method based on the first metric's type
        # Note: All metrics in the list should be of the same type
        if not metrics:
            return []

        # Determine which bulk_store method to use based on the first metric's type
        first_metric = metrics[0]
        metric_type = first_metric.metric_type

        # Group metrics by their type
        numeric_metrics = []
        string_metrics = []
        distribution_metrics = []

        for metric in metrics:
            if metric.metric_type == MetricType.NUMERIC:
                numeric_metrics.append(metric)
            elif metric.metric_type == MetricType.STRING:
                string_metrics.append(metric)
            elif metric.metric_type == MetricType.DISTRIBUTION:
                distribution_metrics.append(metric)

        # Store metrics of each type using the appropriate bulk_store method
        result_metrics = []

        if numeric_metrics:
            from agent_analytics.core.data_composite.metric import BaseNumericMetric
            result_metrics.extend(await BaseNumericMetric.bulk_store(self._data_manager, numeric_metrics))

        if string_metrics:
            from agent_analytics.core.data_composite.metric import BaseStringMetric
            result_metrics.extend(await BaseStringMetric.bulk_store(self._data_manager, string_metrics))

        if distribution_metrics:
            from agent_analytics.core.data_composite.metric import BaseDistributionMetric
            result_metrics.extend(await BaseDistributionMetric.bulk_store(self._data_manager, distribution_metrics))

        return result_metrics

    async def add_issue(self, issue: BaseIssue) -> IssueComposite:
        """
        Add an issue to this task using an issue builder.
        
        Args:
            builder: A fully configured issue builder
                
        Returns:
            The created Issue
        """
        # Set default values if not provided
        if issue.root is None:
            issue.root = self
        if not issue.element_id:
            issue.element_id = f"Issue-{self.element_id}-{issue.name.lower().replace(' ', '-')}"

        # Add this task to related_to if not already there
        if not any(getattr(related, 'element_id', None) == self.element_id for related in issue.related_to):
            issue.related_to.append(self)

        # Build and return the issue
        return await issue.store(self._data_manager)

    async def add_issues(self, issues: list[BaseIssue]) -> list[IssueComposite]:
        """
        Add multiple issues to this task at once.
        
        Args:
            issues: List of issue builders to add to this task
                
        Returns:
            List of created Issue objects
        """
        # Set default values for all issues if not provided
        for issue in issues:
            if issue.root is None:
                issue.root = self
            if not issue.element_id:
                issue.element_id = f"Issue-{self.element_id}-{issue.name.lower().replace(' ', '-')}"

            # Add this task to related_to if not already there
            if not any(getattr(related, 'element_id', None) == self.element_id for related in issue.related_to):
                issue.related_to.append(self)

        # Use the bulk_store method to store all issues at once
        return await BaseIssue.bulk_store(self._data_manager, issues)


