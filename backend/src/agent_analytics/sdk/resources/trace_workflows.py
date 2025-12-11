"""
TraceWorkflows resource for the AgentOps SDK

Provides methods for querying trace workflows.
"""

from agent_analytics.core.data_composite.trace_workflow import TraceWorkflowComposite
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator
from agent_analytics.sdk.models import TraceWorkflow


class TraceWorkflowsResource:
    """
    API for working with trace workflows.

    This resource provides methods to query and retrieve trace workflow data
    from the analytics platform.
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the trace workflows resource.

        Args:
            data_manager: The data manager instance
        """
        self._data_manager = data_manager

    async def fetch_by_owner(
        self,
        owner: any,
        names: list[str] | None = None
    ) -> list[TraceWorkflow]:
        """
        Get all trace workflows owned by a specific element.

        Args:
            owner: The owner element (wrapper, composite, or ID string)
            names: Optional list of names to filter by

        Returns:
            List of TraceWorkflow objects

        Example:
            # Get all trace workflows for a trace
            trace_workflows = await client.trace_workflows.fetch_by_owner(trace)

            # Filter by names
            trace_workflows = await client.trace_workflows.fetch_by_owner(
                owner=trace,
                names=["workflow-a", "workflow-b"]
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
            element_type=TraceWorkflowComposite,
            query=query
        )

        return [self._to_sdk_model(comp) for comp in composites]

    async def get(self, trace_workflow_id: str) -> TraceWorkflow | None:
        """
        Get a specific trace workflow by ID.

        Args:
            trace_workflow_id: The unique identifier of the trace workflow

        Returns:
            TraceWorkflow object if found, None otherwise

        Example:
            trace_workflow = await client.trace_workflows.get("workflow-123")
        """
        # Get trace workflow using the internal API
        trace_workflow_composite = await TraceWorkflowComposite.get_by_id(
            data_manager=self._data_manager,
            id=trace_workflow_id
        )

        if trace_workflow_composite is None:
            return None

        return self._to_sdk_model(trace_workflow_composite)

    def _to_sdk_model(self, composite: TraceWorkflowComposite) -> TraceWorkflow:
        """
        Convert internal composite to SDK model.

        Args:
            composite: Internal trace workflow composite object

        Returns:
            SDK TraceWorkflow model
        """
        return TraceWorkflow(_composite=composite)
