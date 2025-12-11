"""
Traces resource for the AgentOps SDK

Provides methods for querying and managing trace data.
"""

import logging
from datetime import datetime

from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.runtime.api import TenantComponents
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator
from agent_analytics.sdk.models import Trace
from agent_analytics.sdk.resources.actions import ActionsResource
from agent_analytics.sdk.resources.metrics import MetricsResource
from agent_analytics.sdk.resources.task import TasksResource

logger = logging.getLogger(__name__)


class TracesResource:
    """
    API for working with traces.

    This resource provides methods to query and retrieve trace data
    from the analytics platform.
    """

    # Analytics IDs (copied from RuntimeClient for reference)
    TASK_ANALYTICS = "task_analytics"
    TASK_METRIC_ANALYTICS = "task_metrics_analytics"

    def __init__(self, data_manager: AnalyticsDataManager, tenant_components: TenantComponents | None = None):
        """
        Initialize the traces resource.

        Args:
            data_manager: The data manager instance
            tenant_components: Optional tenant components for analytics execution
        """
        self._data_manager = data_manager
        self._tenant_components = tenant_components
        self._tasks_resource = TasksResource(data_manager)
        self._metrics_resource = MetricsResource(data_manager)
        self._actions_resource = ActionsResource(data_manager)

    async def fetch(
        self,
        service_name: str,
        from_date: datetime,
        to_date: datetime | None = None,
        names: list[str] | None = None,
        min_duration: float | None = None,
        max_duration: float | None = None,
        agent_ids: list[str] | None = None
    ) -> list[Trace]:
        """
        List all traces for a service within a time window with optional filtering.

        Args:
            service_name: Name of the service to filter by
            from_date: Start of the time window
            to_date: End of the time window (defaults to now)
            names: Optional list of trace names to filter by
            min_duration: Optional minimum duration filter (in seconds)
            max_duration: Optional maximum duration filter (in seconds)
            agent_ids: Optional list of agent IDs to filter by

        Returns:
            List of Trace objects

        Example:
            # List all traces
            traces = await client.traces.fetch(
                service_name="my-service",
                from_date=datetime.now() - timedelta(days=7)
            )

            # Filter by names and duration
            traces = await client.traces.fetch(
                service_name="my-service",
                from_date=datetime.now() - timedelta(days=7),
                names=["trace-a", "trace-b"],
                min_duration=1.0,
                max_duration=10.0
            )
        """
        # Check if we have advanced filters
        has_filters = names or min_duration is not None or max_duration is not None or agent_ids

        if not has_filters:
            # Use existing optimized method
            trace_composites = await BaseTraceComposite.get_traces(
                data_manager=self._data_manager,
                service_name=service_name,
                from_date=from_date,
                to_date=to_date
            )
        else:
            # Use search with filters
            query = {
                "service_name": QueryFilter(operator=QueryOperator.EQUAL, value=service_name),
                "start_time": QueryFilter(operator=QueryOperator.GREATER_EQUAL, value=from_date)
            }

            if to_date:
                query["start_time_end"] = QueryFilter(operator=QueryOperator.LESS_EQUAL, value=to_date)

            if names:
                query["name"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=names)

            if min_duration is not None:
                query["duration"] = QueryFilter(operator=QueryOperator.GREATER_EQUAL, value=min_duration)

            if max_duration is not None:
                if "duration" not in query:
                    query["duration"] = QueryFilter(operator=QueryOperator.LESS_EQUAL, value=max_duration)

            if agent_ids:
                query["agent_ids"] = QueryFilter(operator=QueryOperator.ARRAY_CONTAINS, value=agent_ids[0])

            trace_composites = await self._data_manager.search(
                element_type=BaseTraceComposite,
                query=query
            )

            # Apply additional Python filters for range queries
            if min_duration is not None and max_duration is not None:
                trace_composites = [t for t in trace_composites if t.duration is not None and t.duration <= max_duration]

            # Filter by multiple agent_ids if provided
            if agent_ids and len(agent_ids) > 1:
                trace_composites = [t for t in trace_composites if t.agent_ids and any(aid in t.agent_ids for aid in agent_ids)]

        # Convert to SDK models
        return [self._to_sdk_model(tc) for tc in trace_composites]

    async def get(self, trace_id: str) -> Trace | None:
        """
        Get a specific trace by ID.

        Args:
            trace_id: The unique identifier of the trace

        Returns:
            Trace object if found, None otherwise

        Example:
            trace = await client.traces.get("trace-123")
        """
        # Get trace using the internal API
        trace_composite = await BaseTraceComposite.get_by_id(
            data_manager=self._data_manager,
            id=trace_id
        )

        if trace_composite is None:
            return None

        return self._to_sdk_model(trace_composite)

    async def process(self, trace_ids: list[str]) -> dict:
        """
        Process traces through the analytics pipeline.

        This method executes the analytics plugins for the given traces,
        generating tasks and metrics. It's designed for use by Celery workers
        processing trace completion events from Langfuse.

        Args:
            trace_ids: List of trace IDs to process

        Returns:
            dict: Processing results with status information

        Raises:
            ValueError: If tenant_components is not available
            Exception: If analytics execution fails

        Example:
            # Process a single trace
            result = await client.traces.process(["trace-123"])

            # Process multiple traces
            result = await client.traces.process(["trace-1", "trace-2"])
        """
        if self._tenant_components is None:
            raise ValueError("TracesResource requires tenant_components to process traces")

        logger.info(f"Processing {len(trace_ids)} trace(s) through analytics pipeline")

        results = []

        for trace_id in trace_ids:
            try:
                logger.info(f"Processing trace {trace_id}")

                # Check if tasks already exist for this trace
                tasks = await BaseTraceComposite.get_tasks_for_trace(
                    self._data_manager, trace_id
                )

                if tasks:
                    logger.info(f"Tasks already exist for trace {trace_id}, skipping creation")
                    results.append({
                        "trace_id": trace_id,
                        "status": "skipped",
                        "reason": "tasks_already_exist"
                    })
                    continue

                # Execute TASK_ANALYTICS
                logger.info(f"Executing {self.TASK_ANALYTICS} for trace {trace_id}")
                input_model_class = await self._tenant_components.registry.get_pipeline_input_model(
                    self.TASK_ANALYTICS
                )
                task_result = await self._tenant_components.executor.execute_analytics(
                    self.TASK_ANALYTICS,
                    input_model_class(trace_id=trace_id)
                )

                if task_result.error is not None:
                    error_msg = f"Plugin {self.TASK_ANALYTICS} failed: {task_result.error.message}"
                    logger.error(error_msg)
                    logger.error(task_result.error.stacktrace)
                    results.append({
                        "trace_id": trace_id,
                        "status": "failed",
                        "error": error_msg,
                        "analytics_id": self.TASK_ANALYTICS
                    })
                    continue

                logger.info(f"{self.TASK_ANALYTICS} pipeline completed for trace {trace_id}")

                # # Execute TASK_METRIC_ANALYTICS (triggered by TASK_ANALYTICS)
                # logger.info(f"Executing {self.TASK_METRIC_ANALYTICS} for trace {trace_id}")
                # metric_input_model_class = await self._tenant_components.registry.get_pipeline_input_model(
                #     self.TASK_METRIC_ANALYTICS
                # )
                # metric_result = await self._tenant_components.executor.execute_analytics(
                #     self.TASK_METRIC_ANALYTICS,
                #     metric_input_model_class(trace_id=trace_id)
                # )

                # if metric_result.error is not None:
                #     error_msg = f"Plugin {self.TASK_METRIC_ANALYTICS} failed: {metric_result.error.message}"
                #     logger.error(error_msg)
                #     logger.error(metric_result.error.stacktrace)
                #     results.append({
                #         "trace_id": trace_id,
                #         "status": "partial",
                #         "error": error_msg,
                #         "analytics_id": self.TASK_METRIC_ANALYTICS,
                #         "completed": [self.TASK_ANALYTICS]
                #     })
                #     continue

                # logger.info(f"{self.TASK_METRIC_ANALYTICS} completed for trace {trace_id}")

                results.append({
                    "trace_id": trace_id,
                    "status": "success",
                    "completed": [self.TASK_ANALYTICS, self.TASK_METRIC_ANALYTICS]
                })

            except Exception as e:
                logger.error(f"SDK: Error processing trace {trace_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                results.append({
                    "trace_id": trace_id,
                    "status": "error",
                    "error": str(e)
                })

        return {
            "total": len(trace_ids),
            "successful": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] in ["failed", "error"]]),
            "skipped": len([r for r in results if r["status"] == "skipped"]),
            "partial": len([r for r in results if r["status"] == "partial"]),
            "results": results
        }

    async def delete(self, trace_ids: list[str]) -> dict:
        """
        Delete all Tasks, Metrics, and Actions associated with the given trace IDs.
        
        Since we don't own the traces themselves (Langfuse does), this method
        only deletes the analytics objects we created during the 'process' step:
        tasks, metrics, and actions.
        
        Args:
            trace_ids: List of trace IDs whose analytics data should be deleted
        
        Returns:
            dict: Deletion results with counts:
                - tasks_deleted: Number of tasks deleted
                - metrics_deleted: Number of metrics deleted
                - actions_deleted: Number of actions deleted
        
        Example:
            # Delete analytics data for traces
            result = await client.traces.delete(["trace-123", "trace-456"])
            print(f"Deleted {result['tasks_deleted']} tasks, {result['metrics_deleted']} metrics, and {result['actions_deleted']} actions")
        """
        logger.info(f"Deleting analytics data for {len(trace_ids)} trace(s)")

        tasks_deleted = 0
        metrics_deleted = 0
        actions_deleted = 0

        for trace_id in trace_ids:
            tasks_deleted += await self._tasks_resource.delete_by_root_id(trace_id)
            metrics_deleted += await self._metrics_resource.delete_by_root_id(trace_id)
            actions_deleted += await self._actions_resource.delete_by_root_id(trace_id)

        logger.info(
            f"Deleted {tasks_deleted} tasks, {metrics_deleted} metrics, and {actions_deleted} actions "
            f"for {len(trace_ids)} traces"
        )

        return {
            "tasks_deleted": tasks_deleted,
            "metrics_deleted": metrics_deleted,
            "actions_deleted": actions_deleted
        }


    def _to_sdk_model(self, composite: BaseTraceComposite) -> Trace:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal trace composite object

        Returns:
            SDK Trace model
        """
        return Trace(_composite=composite)
