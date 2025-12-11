"""
Tasks resource for the AgentOps SDK

Provides methods for querying and creating tasks.
"""

from datetime import datetime
from typing import Any

from ibm_agent_analytics_common.interfaces.task import Task, TaskStatus
from agent_analytics.core.data.task_data import TaskData
from agent_analytics.core.data_composite.task import HierarchicalTask, TaskComposite
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator
from agent_analytics.sdk.models import Task


class TasksResource:
    """
    API for working with tasks.

    This resource provides methods to query, create, and retrieve task data
    from the analytics platform. Tasks represent executable units of work
    with input/output, status tracking, and relationships to other tasks.
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the tasks resource.

        Args:
            data_manager: The data manager instance
        """
        self._data_manager = data_manager

    async def fetch(
        self,
        names: list[str] | None = None,
        statuses: list[TaskStatus] | None = None,
        parent_id: str | None = None,
        action_id: str | None = None,
        root_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None
    ) -> list[Task]:
        """
        List tasks with optional filtering.

        Args:
            names: Optional list of task names to filter by
            statuses: Optional list of task statuses to filter by
            parent_id: Optional parent task ID to filter by
            action_id: Optional action ID to filter by  
            root_id: Optional root element ID to filter by
            from_date: Optional start date filter
            to_date: Optional end date filter

        Returns:
            List of filtered Task objects

        Example:
            # List all tasks
            tasks = await client.tasks.fetch()

            # Filter by names and status
            tasks = await client.tasks.fetch(
                names=["process_data", "validate_input"],
                statuses=[TaskStatus.SUCCESS, TaskStatus.FAILURE]
            )

            # Filter by parent task
            child_tasks = await client.tasks.fetch(parent_id="task-123")

            # Filter by date range
            recent_tasks = await client.tasks.fetch(
                from_date=datetime.now() - timedelta(days=7),
                to_date=datetime.now()
            )
        """
        # Check if we have any filters
        has_filters = (names or statuses or parent_id or action_id or
                      root_id or from_date or to_date)

        if not has_filters:
            # No filters - get all tasks
            query = {}
        else:
            # Build query filters
            query = {}

            if names:
                query["name"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=names)

            if statuses:
                # Convert enum values to strings if needed
                status_values = [status.value if hasattr(status, 'value') else str(status) for status in statuses]
                query["status"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=status_values)

            if parent_id:
                query["parent_id"] = QueryFilter(operator=QueryOperator.EQUAL, value=parent_id)

            if action_id:
                query["action_id"] = QueryFilter(operator=QueryOperator.EQUAL, value=action_id)

            if root_id:
                query["root_id"] = QueryFilter(operator=QueryOperator.EQUAL, value=root_id)

            if from_date:
                query["start_time"] = QueryFilter(operator=QueryOperator.GREATER_EQUAL, value=from_date)

            if to_date:
                if "start_time" not in query:
                    query["start_time"] = QueryFilter(operator=QueryOperator.LESS_EQUAL, value=to_date)

        task_composites = await self._data_manager.search(
            element_type=TaskComposite,
            query=query
        )

        # Apply additional Python filters for range queries
        if from_date and to_date:
            task_composites = [t for t in task_composites if t.start_time and from_date <= t.start_time <= to_date]

        return [self._to_sdk_model(tc) for tc in task_composites]

    async def fetch_by_name(
        self,
        name: str,
        root_id: str | None = None
    ) -> list[Task]:
        """
        Get tasks by name.

        Args:
            name: The task name to search for
            root_id: Optional root element ID to filter by

        Returns:
            List of Task objects with the specified name

        Example:
            tasks = await client.tasks.fetch_by_name("process_data")
            
            # Filter by root as well
            tasks = await client.tasks.fetch_by_name("process_data", root_id="trace-123")
        """
        query = {
            "name": QueryFilter(operator=QueryOperator.EQUAL, value=name)
        }

        if root_id:
            query["root_id"] = QueryFilter(operator=QueryOperator.EQUAL, value=root_id)

        composites = await self._data_manager.search(
            element_type=TaskComposite,
            query=query
        )

        return [self._to_sdk_model(comp) for comp in composites]

    async def fetch_by_owner(
        self,
        owner: Any,
        names: list[str] | None = None,
        statuses: list[TaskStatus] | None = None
    ) -> list[Task]:
        """
        Get all tasks owned by a specific element.

        Args:
            owner: The owner element (wrapper, composite, or ID string)
            names: Optional list of names to filter by
            statuses: Optional list of statuses to filter by

        Returns:
            List of Task objects

        Example:
            # Get all tasks owned by an element
            tasks = await client.tasks.fetch_by_owner(trace)

            # Filter by names and status
            tasks = await client.tasks.fetch_by_owner(
                owner=trace,
                names=["task-a", "task-b"],
                statuses=[TaskStatus.SUCCESS]
            )
        """
        # Extract ID from owner
        if hasattr(owner, "id"):
            root_id = owner.id
        elif hasattr(owner, "element_id"):
            root_id = owner.element_id
        elif isinstance(owner, str):
            root_id = owner
        else:
            raise TypeError("owner must be an Element object or string ID")

        # Build query
        query = {
            "root_id": QueryFilter(operator=QueryOperator.EQUAL, value=root_id)
        }

        if names:
            query["name"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=names)

        if statuses:
            status_values = [status.value if hasattr(status, 'value') else str(status) for status in statuses]
            query["status"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=status_values)

        composites = await self._data_manager.search(
            element_type=TaskComposite,
            query=query
        )

        return [self._to_sdk_model(comp) for comp in composites]

    async def fetch_by_parent(
        self,
        parent_task: Task | str
    ) -> list[Task]:
        """
        Get all child tasks of a specific parent task.

        Args:
            parent_task: Parent Task object or task ID string

        Returns:
            List of Task objects that are children of the specified parent

        Example:
            child_tasks = await client.tasks.fetch_by_parent(parent_task)
            child_tasks = await client.tasks.fetch_by_parent("task-123")
        """
        # Extract ID from parent task
        if hasattr(parent_task, "id"):
            parent_id = parent_task.id
        elif isinstance(parent_task, str):
            parent_id = parent_task
        else:
            raise TypeError("parent_task must be a Task object or string ID")

        query = {
            "parent_id": QueryFilter(operator=QueryOperator.EQUAL, value=parent_id)
        }

        composites = await self._data_manager.search(
            element_type=TaskComposite,
            query=query
        )

        return [self._to_sdk_model(comp) for comp in composites]

    async def fetch_by_status(
        self,
        status: TaskStatus,
        root_id: str | None = None
    ) -> list[Task]:
        """
        Get all tasks with a specific status.

        Args:
            status: The task status to filter by
            root_id: Optional root element ID to filter by

        Returns:
            List of Task objects with the specified status

        Example:
            failed_tasks = await client.tasks.fetch_by_status(TaskStatus.FAILURE)
            timeout_tasks = await client.tasks.fetch_by_status(TaskStatus.TIMEOUT, root_id="trace-123")
        """
        query = {
            "status": QueryFilter(operator=QueryOperator.EQUAL, value=status.value if hasattr(status, 'value') else str(status))
        }

        if root_id:
            query["root_id"] = QueryFilter(operator=QueryOperator.EQUAL, value=root_id)

        composites = await self._data_manager.search(
            element_type=TaskComposite,
            query=query
        )

        return [self._to_sdk_model(comp) for comp in composites]

    async def get(self, task_id: str) -> Task | None:
        """
        Get a specific task by ID.

        Args:
            task_id: The unique identifier of the task

        Returns:
            Task object if found, None otherwise

        Example:
            task = await client.tasks.get("task-123")
        """
        # Get task using the internal API
        task_composite = await TaskComposite.get_by_id(
            data_manager=self._data_manager,
            id=task_id
        )

        if task_composite is None:
            return None

        return self._to_sdk_model(task_composite)

    async def create(
        self,
        root: Any,
        name: str,
        input_data: Any,
        output_data: Any = None,
        status: TaskStatus = TaskStatus.UNKNOWN,
        element_id: str | None = None,
        task_id: str | None = None,
        tags: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        events: list[Any] | None = None,
        log_reference: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        parent_id: str | None = None,
        dependent_ids: list[str] | None = None,
        action_id: str | None = None,
        plugin_id: str | None = None
    ) -> Task:
        """
        Create a new task.

        Args:
            root: Root element this task belongs to
            name: Display name for the task
            input_data: Input data for the task
            output_data: Output data from the task (optional)
            status: Current status of the task
            element_id: Optional custom element ID
            task_id: Optional custom task ID 
            tags: Optional list of tags
            attributes: Optional additional attributes
            metadata: Optional metadata dictionary
            start_time: Optional start time (defaults to now)
            end_time: Optional end time
            events: Optional list of events
            log_reference: Optional log reference information
            metrics: Optional metrics dictionary
            parent_id: Optional parent task ID
            dependent_ids: Optional list of dependent task IDs
            action_id: Optional associated action ID
            plugin_id: Optional plugin identifier

        Returns:
            Created Task object

        Example:
            task = await client.tasks.create(
                root=trace,
                name="Process User Input",
                input_data={"user_query": "What is the weather?"},
                status=TaskStatus.SUCCESS,
                tags=["nlp", "processing"],
                action_id="process_input_v1"
            )
        """
        import uuid
        from datetime import UTC, datetime

        # Generate IDs if not provided
        if task_id is None:
            task_id = str(uuid.uuid4())
        if element_id is None:
            element_id = f"Task:{name}"
        if start_time is None:
            start_time = datetime.now(UTC)

        # Use TaskComposite.create()
        task_composite = await TaskComposite.create(
            data_manager=self._data_manager,
            id=task_id,
            element_id=element_id,
            root=root,
            name=name,
            tags=tags or [],
            input=input_data,
            output=output_data,
            status=status,
            attributes=attributes or {},
            metadata=metadata or {},
            start_time=start_time,
            end_time=end_time,
            events=events or [],
            log_reference=log_reference or {},
            metrics=metrics or {},
            parent_id=parent_id,
            dependent_ids=dependent_ids or [],
            action_id=action_id,
            plugin_metadata_id=plugin_id
        )

        return self._to_sdk_model(task_composite)

    async def create_many(
        self,
        root: Any,
        tasks: list[dict[str, Any]]
    ) -> list[Task]:
        """
        Create multiple tasks at once for better performance.

        Args:
            root: Root element these tasks belong to
            tasks: List of task definitions, each containing:
                - name (str): Display name
                - input (Any): Input data
                - output (Any, optional): Output data
                - status (TaskStatus, optional): Task status
                - And other optional fields

        Returns:
            List of created Task objects

        Example:
            tasks = await client.tasks.create_many(
                root=trace,
                tasks=[
                    {
                        "name": "Parse Input",
                        "input": {"text": "Hello world"},
                        "status": TaskStatus.SUCCESS,
                        "tags": ["parsing"]
                    },
                    {
                        "name": "Generate Response",
                        "input": {"parsed_data": "..."},
                        "status": TaskStatus.SUCCESS,
                        "tags": ["generation"]
                    }
                ]
            )
        """
        # Build list of HierarchicalTask objects
        builders = []
        for task_dict in tasks:
            if "name" not in task_dict:
                raise ValueError("Each task must have a 'name' field")
            if "input" not in task_dict:
                raise ValueError("Each task must have an 'input' field")

            import uuid
            from datetime import UTC, datetime

            builder = HierarchicalTask(
                id=task_dict.get("task_id") or str(uuid.uuid4()),
                element_id=task_dict.get("element_id") or f"Task:{task_dict['name']}",
                root_id=root.element_id if hasattr(root, 'element_id') else str(root),
                name=task_dict["name"],
                input=task_dict["input"],
                output=task_dict.get("output"),
                status=task_dict.get("status", TaskStatus.UNKNOWN),
                tags=task_dict.get("tags", []),
                attributes=task_dict.get("attributes", {}),
                metadata=task_dict.get("metadata", {}),
                start_time=task_dict.get("start_time") or datetime.now(UTC),
                end_time=task_dict.get("end_time"),
                events=task_dict.get("events", []),
                log_reference=task_dict.get("log_reference", {}),
                metrics=task_dict.get("metrics", {}),
                parent_id=task_dict.get("parent_id"),
                dependent_ids=task_dict.get("dependent_ids", []),
                action_id=task_dict.get("action_id"),
                plugin_metadata_id=task_dict.get("plugin_id")
            )

            builders.append(builder)

        # Use bulk_store for efficiency
        composites = await HierarchicalTask.bulk_store(self._data_manager, builders)

        return [self._to_sdk_model(c) for c in composites]

    def _to_sdk_model(self, composite: TaskComposite) -> Task:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal task composite object

        Returns:
            SDK Task model
        """
        return Task.from_composite(composite)

    async def delete(self, task_id: str) -> bool:
        """
        Delete a task by its ID.
        
        Args:
            task_id: The unique identifier of the task to delete
        
        Returns:
            True if deleted successfully, False if task not found
        
        Example:
            success = await client.tasks.delete("task-123")
        """
        return await self._data_manager._persistent_manager.delete(
            element_id=task_id,
            artifact_type=TaskData
        )

    async def delete_by_root_id(self, root_id: str) -> int:
        """
        Delete all tasks with the given root_id.
        
        Args:
            root_id: The root_id (trace_id) to delete tasks for
        
        Returns:
            Number of tasks deleted
        
        Example:
            count = await client.tasks.delete_by_root_id("trace-123")
        """
        # Get all tasks with this root_id
        query = {
            "root_id": QueryFilter(operator=QueryOperator.EQUAL, value=root_id)
        }

        task_composites = await self._data_manager.search(
            element_type=TaskComposite,
            query=query
        )

        # Delete each task
        deleted_count = 0
        for task in task_composites:
            try:
                await self._data_manager._persistent_manager.delete(
                    element_id=task.element_id,
                    artifact_type=TaskData
                )
                deleted_count += 1
            except Exception:
                # Log but continue deleting other tasks
                pass

        return deleted_count