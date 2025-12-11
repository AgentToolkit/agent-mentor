from typing import Any

from pydantic import BaseModel, Field

from agent_analytics.core.data_composite.action import BaseAction
from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.data_composite.metric import BaseMetric

# Import the master pipeline function and output model from our utils file
from agent_analytics.core.data_composite.trace_workflow import (
    BaseTraceWorkflow,
)
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from agent_analytics.extensions.causal_discovery.utils import discover_process_workflow


class CausalDiscoveryLightInput(BaseModel):
    """Input model for the Causal Discovery Light plugin."""
    trace_id: str | None = Field(None, description="A single trace ID to analyze.")
    trace_group_id: str | None = Field(None, description="An ID for a group of traces to analyze together.")
    trace_ids: list[str] | None = Field(None, description="An explicit list of trace IDs to analyze.")
    use_agent_in_analysis: bool = Field(False, description="If True, the discovered workflow will be grouped by agent.")


class CausalDiscoveryLightOutput(BaseModel):
    trace_id: str | None = Field(description="Id of the trace this analytic was run on", default=None)
    trace_group_id: str | None = Field(description="Id of the trace group this analytic was run on", default=None)
    trace_workflow: dict[str, Any] = Field(..., description="List of analyzed tasks")


class CausalDiscoveryLightPlugin(BaseAnalyticsPlugin):
    """
    A lightweight plugin that uses the Alpha Miner algorithm to discover a 
    hierarchical process workflow from task execution data.
    """

    @classmethod
    def get_input_model(cls) -> type[CausalDiscoveryLightInput]:
        return CausalDiscoveryLightInput

    @classmethod
    def get_output_model(cls) -> type[CausalDiscoveryLightOutput]:
        return CausalDiscoveryLightOutput

    async def _execute(
        self,
        analytics_id: str,
        data_manager: DataManager,
        input_data: CausalDiscoveryLightInput,
        config: dict[str, Any]
    ) -> ExecutionResult:
        trace_id = input_data.trace_id
        trace_group_id = input_data.trace_group_id
        if trace_group_id:
            id = trace_group_id
        else:
            id = trace_id
            
        # Step 1: Validate input and determine which traces to fetch
        input_count = sum(1 for v in [input_data.trace_id, input_data.trace_group_id, input_data.trace_ids] if v)
        if input_count != 1:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="Exactly one of trace_id, trace_group_id, or trace_ids must be provided."
                )
            )

        try:
            trace_ids_to_process = []
            if input_data.trace_group_id:
                trace_group = await TraceGroupComposite.get_by_id(data_manager, id=input_data.trace_group_id)
                if not trace_group or not trace_group.traces_ids:
                    return ExecutionResult(
                        analytics_id=analytics_id,
                        status=ExecutionStatus.FAILURE,
                        error=ExecutionError(
                            error_type="DataError",
                            message="Trace group not found or is empty."
                        )
                    )
                trace_ids_to_process = trace_group.traces_ids
            elif input_data.trace_ids:
                trace_ids_to_process = input_data.trace_ids
            else:
                trace_ids_to_process = [input_data.trace_id]

            # Step 2: Fetch all tasks from the specified traces
            all_tasks = []
            for trace_id_item in trace_ids_to_process:
                tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager, trace_id=trace_id_item)
                if tasks:
                    all_tasks.extend(tasks)

            if not all_tasks:
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=ExecutionError(
                        error_type="DataError",
                        message="No tasks found for the provided trace ID(s)."
                    )
                )

            # Step 3: Run the discovery pipeline - NOW RETURNS TUPLE WITH METRICS!
            trace_workflow_obj, new_actions, workflow_metrics, workflow_metric_ids = await discover_process_workflow(
                tasks=all_tasks,
                id=id,
                use_agent_in_analysis=input_data.use_agent_in_analysis,
                analytics_id=analytics_id  # Pass the analytics_id
            )
            
            # Step 4: PERSIST THE NEW ACTIONS FIRST (using bulk_store for efficiency)
            # This is critical - actions must be saved before the workflow
            persisted_actions = await BaseAction.bulk_store(
                data_manager=data_manager,
                base_actions=new_actions
            )
            
            # Step 4.5: Set workflow's related_to with persisted composites
            # The workflows were created WITHOUT related_to (because BaseAction isn't a composite)
            # Now we need to SET the related_to with the persisted actionComposite objects
            action_id_to_composite = {r.element_id: r for r in persisted_actions}
            
            # Set related_to for each workflow based on its owner_id
            for workflow in trace_workflow_obj.workflows:
                if workflow.owner_id and workflow.owner_id in action_id_to_composite:
                    # Set the workflow's related_to to the persisted composite that owns it
                    workflow.related_to = [action_id_to_composite[workflow.owner_id]]
            
            # Also update the actions list in trace_workflow_obj
            trace_workflow_obj.actions = persisted_actions
            
            # Step 5: NOW persist the workflow (with references to persisted actions)
            trace_workflow_composite = await trace_workflow_obj.store(data_manager=data_manager)
            
            # Step 6: PERSIST THE WORKFLOW NODE METRICS
            if workflow_metrics:
                await BaseMetric.bulk_store(data_manager=data_manager, base_metrics=workflow_metrics)
            
            # Step 7: Format and return the successful result
            workflow_dict = trace_workflow_composite.model_dump()

            output = CausalDiscoveryLightOutput(
                trace_id=trace_id if not trace_group_id else None,
                trace_group_id=trace_group_id if trace_group_id else None,
                trace_workflow=workflow_dict
            )
            return ExecutionResult(analytics_id=analytics_id, status=ExecutionStatus.SUCCESS, output=output)

        except Exception as e:
            import traceback
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="ProcessingError",
                    message=f"Failed to discover workflow: {e}",
                    stacktrace=traceback.format_exc()
                )
            )