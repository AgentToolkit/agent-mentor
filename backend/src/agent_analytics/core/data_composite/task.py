import uuid
from datetime import datetime
from typing import Any, ClassVar, Dict, Optional, List

from agent_analytics.core.data_composite.element import ElementComposite,_CREATION_TOKEN
from agent_analytics.core.data_composite.issue import BaseIssue, IssueComposite
from agent_analytics.core.data_composite.metric import BaseMetric, MetricComposite
from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator
from agent_analytics_common.interfaces.graph import Graph
from agent_analytics_common.interfaces.metric import MetricType
from agent_analytics_common.interfaces.task import Task, TaskStatus, TaskTag
from pydantic import Field

from agent_analytics.core.data.task_data import TaskData
from agent_analytics.core.data_composite.action import ActionComposite
from agent_analytics.core.data_composite.annotation import AnnotationComposite
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.issue import BaseIssue, IssueComposite
from agent_analytics.core.data_composite.metric import BaseMetric, MetricComposite


class TaskComposite(ElementComposite[TaskData]):
    """Composite representation of a Task with related Metrics"""
    # Specify the corresponding data class
    data_class: ClassVar[type[TaskData]] = TaskData

    def __init__(self, data_manager: "DataManager", task_data: TaskData,*, _token: object = None):
        super().__init__(data_manager, task_data, _token=_token)

    #Factory method for creating logical Task objects
    #TODO: the parent and action - perhaps need to receive actual Elements instead ids?  Perhaps should support both?
    @classmethod
    async def create(cls,
               data_manager: "DataManager",
               id: str,
               element_id: str,
               root: ElementComposite | str | None,
               name: str,
               tags: list[str],
               input: Any,
               output: Any,
               events: list[Any],
               status: TaskStatus,
               attributes: dict[str, Any],
               metadata: dict[str, Any],
               start_time: datetime,
               log_reference: dict[str, Any] ,
               metrics: dict[str, Any],
               parent_id: str | None=None,
               dependent_ids: list[str]=[],
               graph_id: str | None=None,
               end_time: datetime | None=None,
               parent_name: str | None = None,
            #    input_resource_ids: Optional[List[str]] = None,
            #    created_resource_ids: Optional[List[str]] = None,
               plugin_metadata_id: str | None=None,
               action_id: str | None = None) -> 'TaskComposite':
        """
        Factory method to create a new Task with proper type checking.        
            
        Returns:
            A new Task instance
        """
        root_id = None
        if root is not None:
            if isinstance(root, ElementComposite):
                root_id = root.element_id
            elif isinstance(root, str):
                root_id = root
            else:
                raise TypeError("root must be either an Element object or a string ID")
        # Create a new task data object
        task_data = TaskData(
            id=id,
            element_id=element_id,
            name=name,
            root_id=root_id,
            plugin_metadata_id=plugin_metadata_id,
            tags=tags,
            input=input,
            output=output,
            status=status,
            attributes=attributes,
            metadata=metadata,
            start_time=start_time,
            log_reference=log_reference,
            end_time=end_time,
            events=events,
            metrics=metrics,
            parent_id=parent_id,
            dependent_ids=dependent_ids,
            graph_id=graph_id,
            parent_name=parent_name,
            action_id=action_id
        )

        # Create a task instance with the data
        task = cls(data_manager, task_data,_token=_CREATION_TOKEN)

        # Store the task using the data manager
        await data_manager.store(task)

        # Return the task instance
        return task

    @property
    def id(self) -> str:
        return self._data_object.id

    @property
    def dependent_ids(self) -> list[str]:
        return self._data_object.dependent_ids

    @property
    def tags(self) -> list[str]:
        return self._data_object.tags

    @property
    def input(self) -> Any:
        return self._data_object.input

    @property
    def output(self) -> Any:
        return self._data_object.output

    @property
    def status(self) -> TaskStatus:
        return self._data_object.status

    @property
    def attributes(self) -> dict[str, Any]:
        return self._data_object.attributes

    @property
    def metadata(self) -> dict[str, Any]:
        return self._data_object.metadata

    @property
    def start_time(self) -> datetime:
        return self._data_object.start_time

    @property
    def end_time(self) -> datetime | None:
        return self._data_object.end_time

    @property
    def log_reference(self)-> dict[str, Any]:
        return self._data_object.log_reference

    @property
    def parent_id(self)-> str | None:
        return self._data_object.parent_id

    @property
    def events(self) -> list[Any]:
        return self._data_object.events

    @property
    async def executor(self) -> Any | None:
        # Retrieve the Runable element that executes the task.
        if self._data_object.action_id:
            return await ActionComposite.get_by_id(self._data_manager,self._data_object.action_id)
        return None


    @property
    async def parent(self) -> 'TaskComposite | None':
        if self._data_object.parent_id:
            query = {
                "id": QueryFilter(operator=QueryOperator.EQUAL, value=self._data_object.parent_id)
            }

            composites = await self._data_manager.search(
                element_type=TaskComposite,
                query=query
            )
            if composites:
                return composites[0]
        return None
        # # Retrieve the Task composite element that represents the parent.
        # if self._data_object.parent_id:
        #     return await TaskComposite.get_by_id(self._data_manager,self._data_object.parent_id)
        # return None

    @property
    def metrics(self) -> dict[str, Any] | None:
        return self._data_object.metrics

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
    async def related_issues(self) -> list[IssueComposite]:
        """
        Get all issues related to this task.
        
        Returns:
            List of issues related to this task
        """
        # Use the data manager to retrieve elements related to this task
        related_elements = await self._data_manager.get_elements_related_to_artifact_and_type(self,IssueComposite)
        return related_elements

    # @property
    async def related_annotations(self) -> list[AnnotationComposite]:
        """
        Get all annotations related to this task.
        
        Returns:
            List of issues related to this task
        """
        # Use the data manager to retrieve elements related to this task
        related_elements = await self._data_manager.get_elements_related_to_artifact_and_type(self,AnnotationComposite)
        return related_elements


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

class HierarchicalTask(Task):
    """
    Builder class for Task logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable Task logical object.
    """
    id: str = Field(description='') 
    model_config = {"arbitrary_types_allowed": True}

    # ---Additional platform fields
    plugin_metadata_id: str | None = Field(
        description='The identifier of the analytics which created this object', default=None
    )

    action_id: str | None = Field(
        default=None, description="Action ID"
    )
    events: List[Any] = Field(
        default_factory=list, 
        description="A list containing information about exceptions/events during task execution"
    )
    #-----Hierarchichal graph fields
    children_node_graph: Graph = Field(description='The corresponding Graph flow for children task', default=None)
    dependees: list['HierarchicalTask'] = Field(description='List of tasks that depends on this task', default_factory=list)
    dependent: list['HierarchicalTask'] = Field(description='List of dependent tasks', default_factory=list)
    children: list['HierarchicalTask'] = Field(description='List of child tasks', default_factory=list)
    parent: Optional['HierarchicalTask'] = Field(description='Parent task if it exists', default=None)
    prefix: str = Field(description='Prefix indicating the position of the task in the hierarchy', default='')

    #----root field
    root_id: ElementComposite | str | None = None

    # Regular fields for relationship IDs, not populated by default
    # TODO: dependent_ids convert to dependencies_ids
    dependent_ids: list[str] = Field(default_factory=list, description="List of dependent task IDs")

    #TODO: check if needed - backward compatability
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="A dictionary for additional metadata associated with the task"
    )

    def __init__(self, base_task: Task | None = None, **data):
        if base_task:
            data.update(base_task.model_dump())
        data['id'] = data.get('id', str(uuid.uuid4()))
        super().__init__(**data)

    def set_status(self, status: TaskStatus):
        self.status = status
        if status in [TaskStatus.CREATED, TaskStatus.RUNNING]:
            self.start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + 'Z'
        else:
            self.end_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f") + 'Z'

    @property
    def BASIC_TAGS(self) -> List[str]:
        """Compatibility property for BaseTask.Tag.BASIC_TAGS"""
        return [TaskTag.LLM_CALL, TaskTag.COMPLEX, TaskTag.TOOL_CALL, TaskTag.DB_CALL]
    
    def add_tag(self, tags: List[str]) -> None:
        """
        Add tags to the task with special logic for COMPLEX and LLM_CALL tags.
        Maintains compatibility with BaseTask behavior.
        """
        # Convert to list if tags is None
        if self.tags is None:
            self.tags = []
        
        # Special logic: if COMPLEX or LLM_CALL is added, remove TOOL_CALL
        if TaskTag.COMPLEX in tags or TaskTag.LLM_CALL in tags:
            self.remove_tag([TaskTag.TOOL_CALL])
        
        # Add new tags (avoiding duplicates)
        self.tags = list(set(self.tags + tags))
    
    def remove_tag(self, tags: List[str]) -> None:
        """
        Remove tags from the task.
        Maintains compatibility with BaseTask behavior.
        """
        if self.tags is None:
            return
        
        for tag in tags:
            if tag in self.tags:
                self.tags.remove(tag)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'HierarchicalTask':
        """Create a builder from a dictionary"""
        # Handle id/element_id mapping if needed
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'HierarchicalTask':
        """Create a builder from a JSON string"""
        import json
        data = json.loads(json_str)
        return cls.from_dict(data)

    def flatten(self) -> 'HierarchicalTask':
        """
        Creates a new HierarchicalTask instance with relationship IDs calculated and preserved
        but without the deep nested fields to reduce memory usage.
        
        Returns:
            A new HierarchicalTask instance with flattened structure
        """
        # Extract base task fields directly
        base_fields = {
            # Task fields
            'id': self.id,
            'name': self.name,
            'tags': self.tags if self.tags is not None else [],
            'input': self.input if self.input is not None else {},
            'output': self.output if self.output is not None else {},
            'log_reference': self.log_reference,
            'status': self.status,
            'attributes': self.attributes if self.attributes is not None else {},
            'metadata': self.metadata if self.metadata is not None else {},
            'start_time': self.start_time,
            'end_time': self.end_time,
            'events': self.events if self.events is not None else [],

            # HierarchicalTask additional fields (excluding nested structures)
            'element_id': self.element_id,
            'plugin_metadata_id': self.plugin_metadata_id,
            'action_id': self.action_id,
            'prefix': self.prefix,
            'root_id': self.root_id,

            # Calculate relationship IDs explicitly
            'parent_id': self.parent.id if self.parent else None,
            'dependent_ids': [dep.id for dep in self.dependent]

            # input_resource_ids and created_resource_ids are commented out in original code
            # 'input_resource_ids': self.input_resource_ids.copy() if self.input_resource_ids else None,
            # 'created_resource_ids': self.created_resource_ids.copy() if self.created_resource_ids else None,
        }

        # Create a new instance with just the fields we need
        return HierarchicalTask(**base_fields)

    async def store(self, data_manager: "DataManager") -> TaskComposite:
        """
        Build the Task logical object.
        
        Args:
            data_manager: The data manager to use for creating the Task
            
        Returns:
            The created Task logical object
        """
        # Call the Task.create method with all the gathered data


        return await TaskComposite.create(
            data_manager=data_manager,
            plugin_metadata_id=self.plugin_metadata_id,
            id=self.id,
            element_id=self.element_id,
            root=self.root_id,
            name=self.name,
            tags=self.tags,
            input=self.input,
            output=self.output,
            parent_id=self.parent_id,
            dependent_ids=self.dependent_ids,
            log_reference=self.log_reference,
            status=self.status,
            attributes=self.attributes,
            metadata=self.metadata,
            start_time=self.start_time,
            end_time=self.end_time,
            metrics=self.metrics,
            events=self.events,
            # input_resource_ids=self.input_resource_ids,
            # created_resource_ids=self.created_resource_ids,
            action_id=self.action_id
        )







    @classmethod
    async def bulk_store(cls, data_manager: "DataManager", tasks: list['HierarchicalTask']) -> list[TaskComposite]:
        """
        Efficiently store multiple HierarchicalTask objects at once.
        
        Args:
            data_manager: The data manager to use for storage
            tasks: List of HierarchicalTask objects to store
            
        Returns:
            List of created TaskComposite objects
        """
        # Create all composite objects but don't store them individually
        composite_objects = []
        for task in tasks:
            # Process root information
            root_id = None
            if task.root_id is not None:
                if isinstance(task.root_id, ElementComposite):
                    root_id = task.root_id.element_id
                elif isinstance(task.root_id, str):
                    root_id = task.root_id
                else:
                    raise TypeError("root must be either an Element object or a string ID")

            # Create task data
            task_data = TaskData(
                id=task.id,
                element_id=task.element_id,
                name=task.name,
                root_id=root_id,
                plugin_metadata_id=task.plugin_metadata_id,
                tags=task.tags,
                input=task.input,
                output=task.output,
                status=task.status,
                attributes=task.attributes,
                metadata=task.metadata,
                start_time=task.start_time,
                end_time=task.end_time,
                events=task.events,
                #metrics=task.metrics,
                parent_id=task.parent_id,
                dependent_ids=task.dependent_ids,
                log_reference=task.log_reference,
                # input_resource_ids=task.input_resource_ids,
                # created_resource_ids=task.created_resource_ids,
                action_id=task.action_id
            )

            # Create task instance without storing it
            composite = TaskComposite(data_manager, task_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects


class HierarchicalTaskNamingUtils:
    """
    Utility class for managing hierarchical task naming and prefixing.
    """

    @classmethod
    def assign_hierarchical_prefixes(cls, tasks: list[HierarchicalTask]) -> None:
        """
        Assign hierarchical prefixes to a list of root tasks.

        Args:
            tasks: List of root tasks to assign prefixes to
        """
        for i, task in enumerate(tasks):
            cls._assign_task_prefix(task, str(i))

    @classmethod
    def _assign_task_prefix(cls, task: HierarchicalTask, prefix: str) -> None:
        """
        Recursively assign a prefix to a task and its children.

        Args:
            task: The task to assign a prefix to
            prefix: The prefix to assign
        """
        # Update task prefix
        task.prefix = prefix

        # Only update name if it doesn't already have a prefix
        if ":" not in task.name:
            task.name = f"{prefix}:{task.name}"

        # Sort children by start time to ensure consistent ordering
        sorted_children = sorted(task.children, key=lambda t: t.start_time)

        # Recursively assign prefixes to children
        for i, child in enumerate(sorted_children):
            cls._assign_task_prefix(child, f"{prefix}.{i}")
