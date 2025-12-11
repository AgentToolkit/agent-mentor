"""
TraceGroups resource for the AgentOps SDK

Provides methods for querying and creating trace groups.
"""

import logging
from typing import Any

from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.trace_group import BaseTraceGroup, TraceGroupComposite
from agent_analytics.runtime.api import TenantComponents
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator
from agent_analytics.sdk.models import MetricType, TraceGroup
from agent_analytics.sdk.resources.metrics import MetricsResource
from agent_analytics.server.analytics_utils import transform_workflow

logger = logging.getLogger(__name__)
class TraceGroupsResource:
    """
    API for working with trace groups.

    This resource provides methods to query, create, and retrieve trace group data
    from the analytics platform.
    """
    WORKFLOW_ANALYTICS = "workflow_analytics"

    def __init__(self, data_manager: AnalyticsDataManager, tenant_components: TenantComponents | None = None):
        """
        Initialize the trace groups resource.

        Args:
            data_manager: The data manager instance
        """
        self._data_manager = data_manager
        self._tenant_components = tenant_components

    async def process(self, trace_group_ids: list[str]) -> dict:
        """
        Process trace groups through the workflow analytics pipeline.

        This method executes the workflow analytics for the given trace groups,
        generating workflow visualizations and metrics. If a workflow already exists,
        it fetches and returns the existing workflow and metrics.

        Args:
            trace_group_ids: List of trace group IDs to process

        Returns:
            dict: Processing results with workflows, metrics, and status information

        Raises:
            ValueError: If tenant_components is not available

        Example:
            result = await client.trace_groups.process(["Group:my-group"])
        """
        if self._tenant_components is None:
            raise ValueError("TraceGroupsResource requires tenant_components to process trace groups")

        logger.info(f"Processing {len(trace_group_ids)} trace group(s) through workflow analytics pipeline")

        results = []

        for trace_group_id in trace_group_ids:
            try:
                logger.info(f"Processing trace group {trace_group_id}")

                # Check if workflow already exists
                workflow_objs = await BaseTraceComposite.get_all_workflows_for_trace(
                    self._tenant_components.data_manager, trace_group_id
                )

                workflow_already_existed = bool(workflow_objs)

                if not workflow_already_existed:
                    # Execute WORKFLOW_ANALYTICS
                    logger.info(f"Executing {self.WORKFLOW_ANALYTICS} for trace group {trace_group_id}")
                    input_model_class = await self._tenant_components.registry.get_pipeline_input_model(
                        self.WORKFLOW_ANALYTICS
                    )
                    workflow_result = await self._tenant_components.executor.execute_analytics(
                        self.WORKFLOW_ANALYTICS,
                        input_model_class(trace_group_id=trace_group_id)
                    )

                    if workflow_result.error is not None:
                        error_msg = f"Plugin {self.WORKFLOW_ANALYTICS} failed: {workflow_result.error.message}"
                        logger.error(error_msg)
                        logger.error(workflow_result.error.stacktrace)
                        results.append({
                            "trace_group_id": trace_group_id,
                            "status": "failed",
                            "error": error_msg,
                            "analytics_id": self.WORKFLOW_ANALYTICS
                        })
                        continue

                    logger.info(f"{self.WORKFLOW_ANALYTICS} completed for trace group {trace_group_id}")

                    # Re-fetch workflow objects after creation
                    workflow_objs = await BaseTraceComposite.get_all_workflows_for_trace(
                        self._tenant_components.data_manager, trace_group_id
                    )
                else:
                    logger.info(f"Workflow already exists for trace group {trace_group_id}, fetching existing data")

                # Retrieve workflow and metrics (same logic whether workflow was just created or already existed)
                if not workflow_objs:
                    results.append({
                        "trace_group_id": trace_group_id,
                        "status": "partial",
                        "error": "Workflow execution succeeded but no workflow found"
                    })
                    continue

                workflow_obj = workflow_objs[0]

                # Import transform_workflow here to avoid circular imports
                workflow = await transform_workflow(workflow_obj)

                # Get metrics from workflow nodes
                nodes = await workflow_obj.workflow_nodes
                nodes_metrics = [await node.metrics for node in nodes]
                flat_metric_list = [metric for metric_list in nodes_metrics for metric in metric_list]

                # Fetch trace group aggregate metrics
                trace_group = await TraceGroupComposite.get_by_id(
                    self._tenant_components.data_manager, trace_group_id
                )
                trace_group_metrics = await trace_group.related_metrics

                results.append({
                    "trace_group_id": trace_group_id,
                    "status": "success",
                    "workflow_already_existed": workflow_already_existed,
                    "metrics": [metric.model_dump() for metric in flat_metric_list],
                    "workflow": workflow,
                    "trace_group_aggregate_metrics": [metric.model_dump() for metric in trace_group_metrics]
                })

            except Exception as e:
                logger.error(f"SDK: Error processing trace group {trace_group_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                results.append({
                    "trace_group_id": trace_group_id,
                    "status": "error",
                    "error": str(e)
                })

        return {
            "total": len(trace_group_ids),
            "successful": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] in ["failed", "error"]]),
            "partial": len([r for r in results if r["status"] == "partial"]),
            "results": results
        }

    async def fetch(
        self,
        service_name: str,
        names: list[str] | None = None,
        min_duration: float | None = None,
        max_duration: float | None = None,
        min_success_rate: float | None = None,
        max_success_rate: float | None = None
    ) -> list[TraceGroup]:
        """
        List trace groups with optional filtering.

        Args:
            service_name: Name of the service to filter by
            names: Optional list of names to filter by (returns groups where name is in this list)
            min_duration: Optional minimum average duration filter (in seconds)
            max_duration: Optional maximum average duration filter (in seconds)
            min_success_rate: Optional minimum success rate filter (0.0 to 1.0)
            max_success_rate: Optional maximum success rate filter (0.0 to 1.0)

        Returns:
            List of filtered TraceGroup objects

        Example:
            # List all trace groups for a service
            trace_groups = await client.trace_groups.fetch(service_name="my-service")

            # Filter by names
            trace_groups = await client.trace_groups.fetch(
                service_name="my-service",
                names=["Group A", "Group B"]
            )

            # Filter by duration and success rate
            trace_groups = await client.trace_groups.fetch(
                service_name="my-service",
                min_duration=1.0,
                max_duration=10.0,
                min_success_rate=0.8
            )
        """
        # Build query filters
        has_filters = names or min_duration is not None or max_duration is not None or \
                     min_success_rate is not None or max_success_rate is not None

        if not has_filters:
            # No filters - use existing efficient method
            trace_group_composites = await TraceGroupComposite.get_trace_groups(
                data_manager=self._data_manager,
                service_name=service_name
            )
        else:
            # Use search with filters
            query = {
                "service_name": QueryFilter(operator=QueryOperator.EQUAL, value=service_name)
            }

            if names:
                query["name"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=names)

            if min_duration is not None:
                query["avg_duration"] = QueryFilter(operator=QueryOperator.GREATER_EQUAL, value=min_duration)

            if max_duration is not None:
                # If both min and max, we need to handle this differently
                if "avg_duration" in query:
                    # For now, we'll apply min first, then filter max in Python
                    pass
                else:
                    query["avg_duration"] = QueryFilter(operator=QueryOperator.LESS_EQUAL, value=max_duration)

            if min_success_rate is not None:
                query["success_rate"] = QueryFilter(operator=QueryOperator.GREATER_EQUAL, value=min_success_rate)

            if max_success_rate is not None:
                if "success_rate" not in query:
                    query["success_rate"] = QueryFilter(operator=QueryOperator.LESS_EQUAL, value=max_success_rate)

            trace_group_composites = await self._data_manager.search(
                element_type=TraceGroupComposite,
                query=query
            )

            # Apply additional filters in Python if needed (max_duration with min_duration, max_success_rate with min_success_rate)
            if min_duration is not None and max_duration is not None:
                trace_group_composites = [tg for tg in trace_group_composites if tg.avg_duration is not None and tg.avg_duration <= max_duration]

            if min_success_rate is not None and max_success_rate is not None:
                trace_group_composites = [tg for tg in trace_group_composites if tg.success_rate is not None and tg.success_rate <= max_success_rate]

        return [self._to_sdk_model(tg) for tg in trace_group_composites]

    async def fetch_by_owner(
        self,
        owner: Any,
        names: list[str] | None = None
    ) -> list[TraceGroup]:
        """
        Get all trace groups owned by a specific element.

        Args:
            owner: The owner element (wrapper, composite, or ID string)
            names: Optional list of names to filter by

        Returns:
            List of TraceGroup objects

        Example:
            # Get all trace groups owned by an element
            trace_groups = await client.trace_groups.fetch_by_owner(some_element)

            # Filter by names
            trace_groups = await client.trace_groups.fetch_by_owner(
                owner=some_element,
                names=["Group A", "Group B"]
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

        composites = await self._data_manager.search(
            element_type=TraceGroupComposite,
            query=query
        )

        return [self._to_sdk_model(comp) for comp in composites]

    async def create(
        self,
        service_name: str,
        name: str,
        trace_ids: list[str],
        description: str | None = None,
        tags: list[str] | None = None
    ) -> TraceGroup:
        """
        Create a new trace group.

        This method creates the trace group and automatically computes and stores
        aggregate metrics (avg_duration, success_rate, total_traces, failure_count)
        as separate Metric objects with owner=trace_group and related_to=trace_group.

        Args:
            service_name: Name of the service
            name: Display name for the trace group
            trace_ids: List of trace IDs to include in the group
            description: Optional description
            tags: Optional list of tags

        Returns:
            Created TraceGroup object

        Example:
            trace_group = await client.trace_groups.create(
                service_name="my-service",
                name="High Latency Traces",
                trace_ids=["trace-1", "trace-2", "trace-3"],
                description="Traces with latency above threshold",
                tags=["performance", "high_latency"]
            )
        """
        # Use TraceGroupComposite.create() following runtime_client pattern
        trace_group_composite = await TraceGroupComposite.create(
            data_manager=self._data_manager,
            element_id=f"Group:{name}",  # Following runtime_client pattern for consistency
            name=name,
            traces_ids=trace_ids,
            service_name=service_name,
            description=description,
            tags=tags
        )

        # Compute metrics from traces if trace_ids provided
        if trace_ids:
            computed_metrics = await TraceGroupComposite._compute_metrics_from_traces(
                self._data_manager,
                trace_ids
            )

            metrics_resource = MetricsResource(self._data_manager)

            # Create SDK wrapper for the trace group to use as owner
            trace_group_sdk = self._to_sdk_model(trace_group_composite)

            # Create separate metrics for each computed statistic
            metric_definitions = []

            if computed_metrics['avg_duration'] is not None:
                metric_definitions.append({
                    "name": "avg_duration",
                    "value": computed_metrics['avg_duration'],
                    "metric_type": MetricType.NUMERIC,
                    "units": "seconds",
                    "description": "Average duration across all traces in the group",
                    "tags": ["aggregate", "duration"]
                })

            if computed_metrics['success_rate'] is not None:
                metric_definitions.append({
                    "name": "success_rate",
                    "value": computed_metrics['success_rate'],
                    "metric_type": MetricType.NUMERIC,
                    "units": "ratio",
                    "description": "Success rate across all traces (0.0 to 1.0)",
                    "tags": ["aggregate", "success"]
                })

            metric_definitions.append({
                "name": "total_traces",
                "value": computed_metrics['total_traces'],
                "metric_type": MetricType.NUMERIC,
                "units": "count",
                "description": "Total number of traces in the group",
                "tags": ["aggregate", "count"]
            })

            metric_definitions.append({
                "name": "failure_count",
                "value": computed_metrics['failure_count'],
                "metric_type": MetricType.NUMERIC,
                "units": "count",
                "description": "Number of failed traces in the group",
                "tags": ["aggregate", "failure"]
            })

            # Create all metrics with owner and related_to set to the trace group
            await metrics_resource.create_many(
                owner=trace_group_sdk,
                metrics=[{**m, "related_to": [trace_group_sdk]} for m in metric_definitions]
            )

        return self._to_sdk_model(trace_group_composite)

    async def create_many(
        self,
        service_name: str,
        trace_groups: list[dict[str, Any]]
    ) -> list[TraceGroup]:
        """
        Create multiple trace groups at once for better performance.

        This method creates the trace groups and automatically computes and stores
        aggregate metrics (avg_duration, success_rate, total_traces, failure_count)
        as separate Metric objects with owner=trace_group and related_to=trace_group.

        Args:
            service_name: Name of the service
            trace_groups: List of trace group definitions, each containing:
                - name (str): Display name
                - trace_ids (list[str]): List of trace IDs
                - description (str, optional): Description
                - tags (list[str], optional): Tags

        Returns:
            List of created TraceGroup objects

        Example:
            trace_groups = await client.trace_groups.create_many(
                service_name="my-service",
                trace_groups=[
                    {
                        "name": "High Latency",
                        "trace_ids": ["trace-1", "trace-2"],
                        "description": "High latency traces",
                        "tags": ["performance"]
                    },
                    {
                        "name": "Low Latency",
                        "trace_ids": ["trace-3", "trace-4"],
                        "description": "Low latency traces",
                        "tags": ["performance"]
                    }
                ]
            )
        """
        # Build list of BaseTraceGroup objects
        builders = []
        for tg_dict in trace_groups:
            if "name" not in tg_dict:
                raise ValueError("Each trace group must have a 'name' field")

            builder = BaseTraceGroup(
                id=f"Group:{tg_dict['name']}",
                name=tg_dict["name"],
                service_name=service_name,
                traces_ids=tg_dict.get("trace_ids", [])
            )

            # Handle optional fields via attributes
            if "description" in tg_dict:
                builder.attributes["description"] = tg_dict["description"]
            if "tags" in tg_dict:
                builder.attributes["tags"] = tg_dict["tags"]

            builders.append(builder)

        # Use bulk_store for efficiency
        composites = await BaseTraceGroup.bulk_store(self._data_manager, builders)

        # Create metrics for each trace group
        metrics_resource = MetricsResource(self._data_manager)

        for composite, tg_dict in zip(composites, trace_groups, strict=True):
            trace_ids = tg_dict.get("trace_ids", [])
            if trace_ids:
                # Compute metrics for this trace group
                computed_metrics = await TraceGroupComposite._compute_metrics_from_traces(
                    self._data_manager,
                    trace_ids
                )

                # Create SDK wrapper for the trace group
                trace_group_sdk = self._to_sdk_model(composite)

                # Create separate metrics for each computed statistic
                metric_definitions = []

                if computed_metrics['avg_duration'] is not None:
                    metric_definitions.append({
                        "name": "avg_duration",
                        "value": computed_metrics['avg_duration'],
                        "metric_type": MetricType.NUMERIC,
                        "units": "seconds",
                        "description": "Average duration across all traces in the group",
                        "tags": ["aggregate", "duration"]
                    })

                if computed_metrics['success_rate'] is not None:
                    metric_definitions.append({
                        "name": "success_rate",
                        "value": computed_metrics['success_rate'],
                        "metric_type": MetricType.NUMERIC,
                        "units": "ratio",
                        "description": "Success rate across all traces (0.0 to 1.0)",
                        "tags": ["aggregate", "success"]
                    })

                metric_definitions.append({
                    "name": "total_traces",
                    "value": computed_metrics['total_traces'],
                    "metric_type": MetricType.NUMERIC,
                    "units": "count",
                    "description": "Total number of traces in the group",
                    "tags": ["aggregate", "count"]
                })

                metric_definitions.append({
                    "name": "failure_count",
                    "value": computed_metrics['failure_count'],
                    "metric_type": MetricType.NUMERIC,
                    "units": "count",
                    "description": "Number of failed traces in the group",
                    "tags": ["aggregate", "failure"]
                })

                # Create all metrics with owner and related_to set to the trace group
                await metrics_resource.create_many(
                    owner=trace_group_sdk,
                    metrics=[{**m, "related_to": [trace_group_sdk]} for m in metric_definitions]
                )

        return [self._to_sdk_model(c) for c in composites]

    async def get(self, trace_group_id: str) -> TraceGroup | None:
        """
        Get a specific trace group by ID.

        Args:
            trace_group_id: The unique identifier of the trace group

        Returns:
            TraceGroup object if found, None otherwise

        Example:
            trace_group = await client.trace_groups.get("Group:my-group")
        """
        # Get trace group using the internal API
        trace_group_composite = await TraceGroupComposite.get_by_id(
            data_manager=self._data_manager,
            id=trace_group_id
        )

        if trace_group_composite is None:
            return None

        return self._to_sdk_model(trace_group_composite)

    def _to_sdk_model(self, composite: TraceGroupComposite) -> TraceGroup:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal trace group composite object

        Returns:
            SDK TraceGroup model
        """
        return TraceGroup(_composite=composite)
